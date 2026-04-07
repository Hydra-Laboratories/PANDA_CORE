"""Tests for digital twin pre-validation."""

from __future__ import annotations

from pathlib import Path

from board.loader import load_board_from_yaml
from deck.loader import load_deck_from_yaml
from gantry.gantry import Gantry
from gantry.loader import load_gantry_from_yaml
from protocol_engine.loader import load_protocol_from_yaml
from validation.digital_twin import run_digital_twin_validation


GANTRY_YAML = """\
serial_port: /dev/ttyUSB0
cnc:
  homing_strategy: standard
working_volume:
  x_min: -100.0
  x_max: 0.0
  y_min: -100.0
  y_max: 0.0
  z_min: -100.0
  z_max: 0.0
"""

DECK_YAML = """\
labware:
  vial_1:
    type: vial
    name: test_vial
    model_name: test_vial
    height_mm: 10.0
    diameter_mm: 10.0
    location:
      x: -20.0
      y: -20.0
      z: -20.0
    capacity_ul: 1000.0
    working_volume_ul: 500.0
  plate_1:
    type: well_plate
    name: test_plate
    model_name: test_plate
    rows: 2
    columns: 2
    length_mm: 18.0
    width_mm: 18.0
    height_mm: 10.0
    calibration:
      a1:
        x: -40.0
        y: -40.0
        z: -20.0
      a2:
        x: -40.0
        y: -49.0
        z: -20.0
    x_offset_mm: 9.0
    y_offset_mm: -9.0
    capacity_ul: 200.0
    working_volume_ul: 150.0
"""

BOARD_YAML = """\
instruments:
  pipette:
    type: pipette
    vendor: opentrons
    offset_x: -5.0
    offset_y: 0.0
    depth: 0.0
"""

PROTOCOL_OK = """\
protocol:
  - move:
      instrument: pipette
      position: vial_1
"""

PROTOCOL_BAD = """\
protocol:
  - move:
      instrument: pipette
      position: plate_1.B2
"""

PROTOCOL_UNSUPPORTED = """\
protocol:
  - aspirate:
      position: vial_1
      volume_ul: 10.0
"""


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _load_all(tmp_path: Path, protocol_yaml: str, board_yaml: str = BOARD_YAML):
    gantry_path = tmp_path / "gantry.yaml"
    deck_path = tmp_path / "deck.yaml"
    board_path = tmp_path / "board.yaml"
    protocol_path = tmp_path / "protocol.yaml"

    _write(gantry_path, GANTRY_YAML)
    _write(deck_path, DECK_YAML)
    _write(board_path, board_yaml)
    _write(protocol_path, protocol_yaml)

    gantry = load_gantry_from_yaml(gantry_path)
    deck = load_deck_from_yaml(deck_path)
    board = load_board_from_yaml(board_path, Gantry(offline=True), mock_mode=True)
    protocol = load_protocol_from_yaml(protocol_path)
    return gantry, deck, board, protocol


def test_digital_twin_generates_artifacts_and_passes(tmp_path: Path):
    gantry, deck, board, protocol = _load_all(tmp_path, PROTOCOL_OK)
    json_out = tmp_path / "twin.json"
    image_out = tmp_path / "twin.svg"

    result = run_digital_twin_validation(
        gantry=gantry,
        deck=deck,
        board=board,
        protocol=protocol,
        json_path=json_out,
        image_path=image_out,
    )

    assert result.passed is True
    assert result.violations == []
    assert json_out.exists()
    assert image_out.exists()


def test_digital_twin_flags_unreachable_target(tmp_path: Path):
    board_bad = """\
instruments:
  pipette:
    type: pipette
    vendor: opentrons
    offset_x: -200.0
    offset_y: 0.0
    depth: 0.0
"""
    gantry, deck, board, protocol = _load_all(
        tmp_path, PROTOCOL_BAD, board_yaml=board_bad,
    )

    result = run_digital_twin_validation(
        gantry=gantry, deck=deck, board=board, protocol=protocol,
    )

    assert result.passed is False
    assert any("outside reachable workspace" in v.message for v in result.violations)


def test_digital_twin_flags_unsupported_commands(tmp_path: Path):
    gantry, deck, board, protocol = _load_all(tmp_path, PROTOCOL_UNSUPPORTED)

    result = run_digital_twin_validation(
        gantry=gantry, deck=deck, board=board, protocol=protocol,
    )

    assert result.passed is False
    assert result.step_trace[0]["status"] == "unsupported"
