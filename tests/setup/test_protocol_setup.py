"""Tests for setup_protocol: load all configs, validate, return ready-to-run protocol."""

from __future__ import annotations

import importlib
import os
import tempfile

import pytest

from src.board.errors import BoardLoaderError
from src.deck.errors import DeckLoaderError
from src.machine.errors import MachineLoaderError
from src.machine.machine_config import MachineConfig
from src.protocol_engine.errors import ProtocolLoaderError
from src.protocol_engine.protocol import Protocol, ProtocolContext
from src.protocol_engine.registry import CommandRegistry
from src.protocol_engine.setup import setup_protocol
from src.validation.errors import SetupValidationError


@pytest.fixture(autouse=True)
def _ensure_commands_registered():
    """Ensure protocol commands are registered (may be cleared by other test fixtures)."""
    if not CommandRegistry.instance().command_names:
        import src.protocol_engine.commands.move
        import src.protocol_engine.commands.pipette
        import src.protocol_engine.commands.scan
        importlib.reload(src.protocol_engine.commands.move)
        importlib.reload(src.protocol_engine.commands.pipette)
        importlib.reload(src.protocol_engine.commands.scan)


# ── YAML templates ──────────────────────────────────────────────────────

MACHINE_YAML = """\
serial_port: /dev/ttyUSB0
cnc:
  homing_strategy: standard
working_volume:
  x_min: -300.0
  x_max: 0.0
  y_min: -200.0
  y_max: 0.0
  z_min: -80.0
  z_max: 0.0
"""

DECK_YAML = """\
labware:
  vial_1:
    type: vial
    name: test_vial
    model_name: standard_vial
    height_mm: 66.75
    diameter_mm: 28.0
    location:
      x: -30.0
      y: -40.0
      z: -20.0
    capacity_ul: 1500.0
    working_volume_ul: 1200.0
"""

BOARD_YAML = """\
instruments:
  pipette:
    type: mock_pipette
    offset_x: -5.0
    offset_y: 0.0
    depth: 0.0
    measurement_height: 0.0
"""

PROTOCOL_YAML = """\
protocol:
  - move:
      instrument: pipette
      position: vial_1
"""


def _write_temp_yaml(content: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(content)
    f.close()
    return f.name


class _TempYamlFiles:
    """Context manager that creates temp YAML files and cleans them up."""

    def __init__(
        self,
        machine: str = MACHINE_YAML,
        deck: str = DECK_YAML,
        board: str = BOARD_YAML,
        protocol: str = PROTOCOL_YAML,
    ):
        self._machine = machine
        self._deck = deck
        self._board = board
        self._protocol = protocol
        self.paths: list[str] = []

    def __enter__(self):
        self.machine_path = _write_temp_yaml(self._machine)
        self.deck_path = _write_temp_yaml(self._deck)
        self.board_path = _write_temp_yaml(self._board)
        self.protocol_path = _write_temp_yaml(self._protocol)
        self.paths = [self.machine_path, self.deck_path, self.board_path, self.protocol_path]
        return self

    def __exit__(self, *args):
        for p in self.paths:
            if os.path.exists(p):
                os.unlink(p)


# ── Tests ────────────────────────────────────────────────────────────────


class TestSetupProtocol:

    def test_setup_returns_protocol_and_context(self):
        with _TempYamlFiles() as f:
            protocol, context = setup_protocol(
                f.machine_path, f.deck_path, f.board_path, f.protocol_path,
            )
            assert isinstance(protocol, Protocol)
            assert isinstance(context, ProtocolContext)

    def test_context_has_board_with_instruments(self):
        with _TempYamlFiles() as f:
            _, context = setup_protocol(
                f.machine_path, f.deck_path, f.board_path, f.protocol_path,
            )
            assert "pipette" in context.board.instruments

    def test_context_has_deck_with_labware(self):
        with _TempYamlFiles() as f:
            _, context = setup_protocol(
                f.machine_path, f.deck_path, f.board_path, f.protocol_path,
            )
            assert "vial_1" in context.deck

    def test_context_has_machine_config(self):
        with _TempYamlFiles() as f:
            _, context = setup_protocol(
                f.machine_path, f.deck_path, f.board_path, f.protocol_path,
            )
            assert isinstance(context.machine, MachineConfig)
            assert context.machine.working_volume.x_min == -300.0

    def test_protocol_has_expected_steps(self):
        with _TempYamlFiles() as f:
            protocol, _ = setup_protocol(
                f.machine_path, f.deck_path, f.board_path, f.protocol_path,
            )
            assert len(protocol) == 1
            assert protocol.steps[0].command_name == "move"

    def test_raises_on_deck_position_out_of_bounds(self):
        out_of_bounds_deck = """\
labware:
  vial_1:
    type: vial
    name: test_vial
    model_name: standard_vial
    height_mm: 66.75
    diameter_mm: 28.0
    location:
      x: -301.0
      y: -40.0
      z: -20.0
    capacity_ul: 1500.0
    working_volume_ul: 1200.0
"""
        with _TempYamlFiles(deck=out_of_bounds_deck) as f:
            with pytest.raises(SetupValidationError) as exc_info:
                setup_protocol(
                    f.machine_path, f.deck_path, f.board_path, f.protocol_path,
                )
            assert len(exc_info.value.violations) >= 1

    def test_raises_on_gantry_position_out_of_bounds(self):
        # vial at x=-2.0, pipette offset_x=-5.0 -> gantry_x = -2 - (-5) = 3.0 > x_max=0
        near_edge_deck = """\
labware:
  vial_1:
    type: vial
    name: test_vial
    model_name: standard_vial
    height_mm: 66.75
    diameter_mm: 28.0
    location:
      x: -2.0
      y: -40.0
      z: -20.0
    capacity_ul: 1500.0
    working_volume_ul: 1200.0
"""
        with _TempYamlFiles(deck=near_edge_deck) as f:
            with pytest.raises(SetupValidationError) as exc_info:
                setup_protocol(
                    f.machine_path, f.deck_path, f.board_path, f.protocol_path,
                )
            assert any(v.coordinate_type == "gantry" for v in exc_info.value.violations)

    def test_raises_on_missing_machine_file(self):
        with _TempYamlFiles() as f:
            with pytest.raises(MachineLoaderError):
                setup_protocol(
                    "/nonexistent/machine.yaml", f.deck_path, f.board_path, f.protocol_path,
                )

    def test_raises_on_missing_deck_file(self):
        with _TempYamlFiles() as f:
            with pytest.raises(DeckLoaderError):
                setup_protocol(
                    f.machine_path, "/nonexistent/deck.yaml", f.board_path, f.protocol_path,
                )

    def test_raises_on_missing_board_file(self):
        with _TempYamlFiles() as f:
            with pytest.raises(BoardLoaderError):
                setup_protocol(
                    f.machine_path, f.deck_path, "/nonexistent/board.yaml", f.protocol_path,
                )

    def test_raises_on_missing_protocol_file(self):
        with _TempYamlFiles() as f:
            with pytest.raises(ProtocolLoaderError):
                setup_protocol(
                    f.machine_path, f.deck_path, f.board_path, "/nonexistent/protocol.yaml",
                )

    def test_uses_mock_gantry_by_default(self):
        with _TempYamlFiles() as f:
            _, context = setup_protocol(
                f.machine_path, f.deck_path, f.board_path, f.protocol_path,
            )
            # Board should have a gantry (mock) — verify it exists
            assert context.board.gantry is not None
