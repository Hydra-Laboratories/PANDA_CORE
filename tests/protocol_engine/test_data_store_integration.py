"""Tests for DataStore + VolumeTracker integration with protocol setup."""

from __future__ import annotations

import importlib
import os
import tempfile

import pytest

from data.data_store import DataStore
from deck.labware.vial import Vial
from deck.labware.labware import Coordinate3D
from deck.labware.well_plate import WellPlate
from protocol_engine.protocol import ProtocolContext
from protocol_engine.registry import CommandRegistry
from protocol_engine.setup import setup_protocol
from protocol_engine.volume_tracker import VolumeTracker


@pytest.fixture(autouse=True)
def _ensure_commands_registered():
    if not CommandRegistry.instance().command_names:
        import protocol_engine.commands.move
        import protocol_engine.commands.pipette
        import protocol_engine.commands.scan
        importlib.reload(protocol_engine.commands.move)
        importlib.reload(protocol_engine.commands.pipette)
        importlib.reload(protocol_engine.commands.scan)


GANTRY_YAML = """\
serial_port: /dev/ttyUSB0
cnc:
  homing_strategy: standard
  total_z_height: 90.0
working_volume:
  x_min: 0.0
  x_max: 300.0
  y_min: 0.0
  y_max: 200.0
  z_min: 0.0
  z_max: 80.0
"""

DECK_YAML = """\
labware:
  reagent_vial:
    type: vial
    name: reagent_vial
    model_name: standard_vial
    height_mm: 66.75
    diameter_mm: 28.0
    location:
      x: 30.0
      y: 40.0
      z: 20.0
    capacity_ul: 1500.0
    working_volume_ul: 1200.0
    initial_volume_ul: 1000.0
"""

BOARD_YAML = """\
instruments:
  pipette:
    type: mock_pipette
    offset_x: 5.0
    offset_y: 0.0
    depth: 0.0
    measurement_height: 0.0
"""

PROTOCOL_YAML = """\
protocol:
  - move:
      instrument: pipette
      position: reagent_vial
"""

TRANSFER_PROTOCOL_YAML = """\
protocol:
  - aspirate:
      position: reagent_vial
      volume_ul: 100.0
"""


def _write_temp_yaml(content: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(content)
    f.close()
    return f.name


class _TempYamlFiles:
    def __init__(self, gantry=GANTRY_YAML, deck=DECK_YAML,
                 board=BOARD_YAML, protocol=PROTOCOL_YAML):
        self._gantry = gantry
        self._deck = deck
        self._board = board
        self._protocol = protocol
        self.paths: list[str] = []

    def __enter__(self):
        self.gantry_path = _write_temp_yaml(self._gantry)
        self.deck_path = _write_temp_yaml(self._deck)
        self.board_path = _write_temp_yaml(self._board)
        self.protocol_path = _write_temp_yaml(self._protocol)
        self.paths = [self.gantry_path, self.deck_path,
                      self.board_path, self.protocol_path]
        return self

    def __exit__(self, *args):
        for p in self.paths:
            if os.path.exists(p):
                os.unlink(p)


@pytest.fixture
def tmp_db():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    yield f.name
    os.unlink(f.name)


class TestSetupProtocolWithDataStore:

    def test_setup_creates_data_store_when_db_path_given(self, tmp_db):
        with _TempYamlFiles() as f:
            protocol, context = setup_protocol(
                f.gantry_path, f.deck_path, f.board_path, f.protocol_path,
                db_path=tmp_db,
            )
            assert context.data_store is not None
            assert isinstance(context.data_store, DataStore)

    def test_setup_creates_campaign(self, tmp_db):
        with _TempYamlFiles() as f:
            protocol, context = setup_protocol(
                f.gantry_path, f.deck_path, f.board_path, f.protocol_path,
                db_path=tmp_db,
            )
            assert context.campaign_id is not None
            assert context.campaign_id > 0

    def test_setup_creates_volume_tracker(self, tmp_db):
        with _TempYamlFiles() as f:
            protocol, context = setup_protocol(
                f.gantry_path, f.deck_path, f.board_path, f.protocol_path,
                db_path=tmp_db,
            )
            assert context.volume_tracker is not None
            assert isinstance(context.volume_tracker, VolumeTracker)

    def test_volume_tracker_has_registered_labware(self, tmp_db):
        with _TempYamlFiles() as f:
            protocol, context = setup_protocol(
                f.gantry_path, f.deck_path, f.board_path, f.protocol_path,
                db_path=tmp_db,
            )
            vol = context.volume_tracker.get_volume("reagent_vial")
            assert vol == 1000.0

    def test_data_store_has_registered_labware(self, tmp_db):
        with _TempYamlFiles() as f:
            protocol, context = setup_protocol(
                f.gantry_path, f.deck_path, f.board_path, f.protocol_path,
                db_path=tmp_db,
            )
            contents = context.data_store.get_contents(
                context.campaign_id, "reagent_vial", None,
            )
            # Freshly registered, no contents yet
            assert contents is None

    def test_setup_without_db_path_has_no_data_store(self):
        with _TempYamlFiles() as f:
            protocol, context = setup_protocol(
                f.gantry_path, f.deck_path, f.board_path, f.protocol_path,
            )
            assert context.data_store is None
            assert context.campaign_id is None
            assert context.volume_tracker is None

    def test_campaign_stores_config_snapshots(self, tmp_db):
        with _TempYamlFiles() as f:
            protocol, context = setup_protocol(
                f.gantry_path, f.deck_path, f.board_path, f.protocol_path,
                db_path=tmp_db,
            )
            row = context.data_store._conn.execute(
                "SELECT deck_config, board_config, gantry_config, protocol_config "
                "FROM campaigns WHERE id = ?",
                (context.campaign_id,),
            ).fetchone()
            assert row is not None
            assert row[0] is not None  # deck_config
            assert row[1] is not None  # board_config
            assert row[2] is not None  # gantry_config
            assert row[3] is not None  # protocol_config


class TestVolumeTrackerRegistration:

    def test_register_vial_with_initial_volume(self):
        tracker = VolumeTracker()
        vial = Vial(
            name="v1", model_name="test", height_mm=50.0, diameter_mm=20.0,
            location=Coordinate3D(x=0, y=0, z=0),
            capacity_ul=1000.0, working_volume_ul=800.0,
            initial_volume_ul=500.0,
        )
        tracker.register_labware("v1", vial, initial_volume_ul=500.0)
        assert tracker.get_volume("v1") == 500.0
        assert tracker.get_capacity("v1") == 1000.0

    def test_register_vial_default_zero_volume(self):
        tracker = VolumeTracker()
        vial = Vial(
            name="v1", model_name="test", height_mm=50.0, diameter_mm=20.0,
            location=Coordinate3D(x=0, y=0, z=0),
            capacity_ul=1000.0, working_volume_ul=800.0,
        )
        tracker.register_labware("v1", vial)
        assert tracker.get_volume("v1") == 0.0


class TestProtocolExecutionWithTracking:

    def test_aspirate_updates_volume_tracker(self, tmp_db):
        with _TempYamlFiles(protocol=TRANSFER_PROTOCOL_YAML) as f:
            protocol, context = setup_protocol(
                f.gantry_path, f.deck_path, f.board_path, f.protocol_path,
                db_path=tmp_db,
            )
            protocol.run(context)
            vol = context.volume_tracker.get_volume("reagent_vial")
            assert vol == 900.0  # 1000 - 100

    def test_aspirate_persists_to_data_store(self, tmp_db):
        with _TempYamlFiles(protocol=TRANSFER_PROTOCOL_YAML) as f:
            protocol, context = setup_protocol(
                f.gantry_path, f.deck_path, f.board_path, f.protocol_path,
                db_path=tmp_db,
            )
            protocol.run(context)
            row = context.data_store._conn.execute(
                "SELECT current_volume_ul FROM labware "
                "WHERE campaign_id = ? AND labware_key = ?",
                (context.campaign_id, "reagent_vial"),
            ).fetchone()
            assert row is not None
            assert row[0] == pytest.approx(900.0)
