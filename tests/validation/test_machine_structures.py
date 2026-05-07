"""Machine-structure collision validation for protocol motion."""

from __future__ import annotations

from unittest.mock import MagicMock

from board.board import Board
from deck.deck import Deck
from deck.labware.labware import Coordinate3D
from deck.labware.well_plate import WellPlate
from gantry.gantry_config import (
    GantryConfig,
    HomingStrategy,
    MachineStructureBox,
    WorkingVolume,
)
from protocol_engine.protocol import Protocol, ProtocolStep
from validation.protocol_semantics import validate_protocol_semantics


def _rail() -> MachineStructureBox:
    return MachineStructureBox(
        x_min=480.0,
        x_max=540.0,
        y_min=0.0,
        y_max=300.0,
        z_min=0.0,
        z_max=100.0,
    )


def _gantry() -> GantryConfig:
    return GantryConfig(
        serial_port="/dev/ttyUSB0",
        homing_strategy=HomingStrategy.STANDARD,
        total_z_height=160.0,
        working_volume=WorkingVolume(
            x_min=0.0,
            x_max=600.0,
            y_min=0.0,
            y_max=300.0,
            z_min=0.0,
            z_max=160.0,
        ),
        machine_structures={"right_x_max_rail": _rail()},
    )


def _instrument(
    *,
    measurement_height: float = 50.0,
    safe_approach_height: float = 120.0,
):
    instr = MagicMock()
    instr.name = "asmi"
    instr.offset_x = 0.0
    instr.offset_y = 0.0
    instr.depth = 0.0
    instr.measurement_height = measurement_height
    instr.safe_approach_height = safe_approach_height
    return instr


def _board(
    *,
    measurement_height: float = 50.0,
    safe_approach_height: float = 120.0,
) -> Board:
    return Board(
        gantry=MagicMock(),
        instruments={
            "asmi": _instrument(
                measurement_height=measurement_height,
                safe_approach_height=safe_approach_height,
            )
        },
    )


def _deck(*, well_z: float = 40.0) -> Deck:
    return Deck({
        "plate": WellPlate(
            name="plate",
            model_name="test_plate",
            length_mm=127.71,
            width_mm=85.43,
            height_mm=14.10,
            rows=1,
            columns=1,
            wells={"A1": Coordinate3D(x=500.0, y=150.0, z=well_z)},
            capacity_ul=200.0,
            working_volume_ul=150.0,
        )
    })


def _protocol(*steps: ProtocolStep) -> Protocol:
    return Protocol(list(steps))


def _move_step(
    index: int,
    *,
    position,
    travel_z: float | None = None,
) -> ProtocolStep:
    args = {"instrument": "asmi", "position": position}
    if travel_z is not None:
        args["travel_z"] = travel_z
    return ProtocolStep(
        index=index,
        command_name="move",
        handler=lambda *a, **k: None,
        args=args,
    )


def test_low_pose_inside_machine_structure_fails():
    protocol = _protocol(_move_step(0, position=(500.0, 150.0, 50.0)))

    violations = validate_protocol_semantics(
        protocol, _board(), _deck(), _gantry(),
    )

    assert any("right_x_max_rail" in v.message for v in violations), violations


def test_high_pose_inside_machine_structure_xy_passes():
    protocol = _protocol(_move_step(0, position=(500.0, 150.0, 101.0)))

    assert validate_protocol_semantics(
        protocol, _board(), _deck(), _gantry(),
    ) == []


def test_travel_segment_crossing_machine_structure_at_low_z_fails():
    protocol = _protocol(
        _move_step(0, position=(400.0, 150.0, 120.0)),
        _move_step(1, position=(560.0, 150.0, 120.0), travel_z=50.0),
    )

    violations = validate_protocol_semantics(
        protocol, _board(), _deck(), _gantry(),
    )

    assert any(
        "travel segment" in v.message and "right_x_max_rail" in v.message
        for v in violations
    ), violations


def test_deck_target_move_validates_safe_approach_pose():
    protocol = _protocol(_move_step(0, position="plate.A1"))

    violations = validate_protocol_semantics(
        protocol,
        _board(safe_approach_height=50.0),
        _deck(),
        _gantry(),
    )

    assert any("safe_approach_height" in v.message for v in violations), violations


def test_scan_action_z_inside_machine_structure_fails():
    protocol = Protocol([
        ProtocolStep(
            index=0,
            command_name="scan",
            handler=lambda *a, **k: None,
            args={
                "plate": "plate",
                "instrument": "asmi",
                "method": "indentation",
                "entry_travel_height": 120.0,
                "interwell_travel_height": 120.0,
                "method_kwargs": {
                    "measurement_height": 50.0,
                    "indentation_limit": 40.0,
                    "step_size": 0.1,
                },
            },
        )
    ])

    violations = validate_protocol_semantics(
        protocol, _board(), _deck(), _gantry(),
    )

    assert any("action_z" in v.message for v in violations), violations
