"""Structure-clearance validation for multi-instrument deck-origin motion."""

from __future__ import annotations

from unittest.mock import MagicMock

from board.board import Board
from deck.deck import Deck
from deck.labware.labware import Coordinate3D
from deck.labware.well_plate import WellPlate
from gantry.gantry_config import GantryConfig, HomingStrategy, WorkingVolume
from protocol_engine.protocol import Protocol, ProtocolStep
from validation.protocol_semantics import validate_protocol_semantics


def _gantry(clearance_z: float = 85.0) -> GantryConfig:
    return GantryConfig(
        serial_port="/dev/ttyUSB0",
        homing_strategy=HomingStrategy.STANDARD,
        total_z_height=100.0,
        working_volume=WorkingVolume(
            x_min=0.0,
            x_max=400.0,
            y_min=0.0,
            y_max=300.0,
            z_min=0.0,
            z_max=100.0,
        ),
        structure_clearance_z=clearance_z,
    )


def _deck() -> Deck:
    return Deck({
        "plate": WellPlate(
            name="plate",
            model_name="test_plate",
            length_mm=127.71,
            width_mm=85.43,
            height_mm=14.10,
            rows=1,
            columns=1,
            wells={"A1": Coordinate3D(x=100.0, y=100.0, z=27.0)},
            capacity_ul=200.0,
            working_volume_ul=150.0,
        )
    })


def _board() -> Board:
    instrument = MagicMock()
    instrument.name = "asmi"
    instrument.offset_x = 0.0
    instrument.offset_y = 0.0
    instrument.depth = 0.0
    instrument.measurement_height = 26.0
    instrument.safe_approach_height = 35.0
    return Board(gantry=MagicMock(), instruments={"asmi": instrument})


def _protocol(entry_travel_height: float) -> Protocol:
    return Protocol([
        ProtocolStep(
            index=0,
            command_name="scan",
            handler=lambda *a, **k: None,
            args={
                "plate": "plate",
                "instrument": "asmi",
                "method": "indentation",
                "measurement_height": 26.0,
                "entry_travel_height": entry_travel_height,
                "interwell_travel_height": 35.0,
                "indentation_limit": 24.0,
                "method_kwargs": {"step_size": 0.1},
            },
        )
    ])


def test_scan_entry_must_meet_structure_clearance_when_configured():
    violations = validate_protocol_semantics(
        _protocol(entry_travel_height=80.0),
        _board(),
        _deck(),
        _gantry(clearance_z=85.0),
    )

    assert len(violations) == 1
    assert "structure_clearance_z" in violations[0].message


def test_scan_entry_at_structure_clearance_passes():
    assert validate_protocol_semantics(
        _protocol(entry_travel_height=85.0),
        _board(),
        _deck(),
        _gantry(clearance_z=85.0),
    ) == []


def _move_protocol(travel_z: float) -> Protocol:
    return Protocol([
        ProtocolStep(
            index=0,
            command_name="move",
            handler=lambda *a, **k: None,
            args={
                "instrument": "asmi",
                "position": [100.0, 150.0, 40.0],
                "travel_z": travel_z,
            },
        )
    ])


def test_move_travel_z_below_structure_clearance_fails():
    """travel_z=40 with structure_clearance_z=85 must be rejected."""
    violations = validate_protocol_semantics(
        _move_protocol(travel_z=40.0),
        _board(),
        _deck(),
        _gantry(clearance_z=85.0),
    )

    assert len(violations) == 1
    assert "structure_clearance_z" in violations[0].message


def test_move_travel_z_at_structure_clearance_passes():
    assert validate_protocol_semantics(
        _move_protocol(travel_z=85.0),
        _board(),
        _deck(),
        _gantry(clearance_z=85.0),
    ) == []


def test_move_travel_z_above_structure_clearance_passes():
    assert validate_protocol_semantics(
        _move_protocol(travel_z=90.0),
        _board(),
        _deck(),
        _gantry(clearance_z=85.0),
    ) == []
