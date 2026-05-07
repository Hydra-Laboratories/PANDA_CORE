"""Tests for semantic protocol validation beyond static bounds."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

from board.board import Board
from deck.deck import Deck
from deck.labware.labware import Coordinate3D
from deck.labware.well_plate import WellPlate
from gantry.gantry_config import GantryConfig, HomingStrategy, WorkingVolume
from protocol_engine.protocol import Protocol, ProtocolStep
from validation.protocol_semantics import validate_protocol_semantics


def _plate() -> WellPlate:
    return WellPlate(
        name="plate",
        model_name="test_plate",
        length_mm=127.71,
        width_mm=85.43,
        height_mm=14.10,
        rows=1,
        columns=1,
        wells={"A1": Coordinate3D(x=0.0, y=0.0, z=73.0)},
        capacity_ul=200.0,
        working_volume_ul=150.0,
    )


def _instrument(
    name: str = "asmi",
    measurement_height: float | None = None,
    safe_approach_height: float | None = None,
):
    instr = MagicMock()
    instr.name = name
    instr.offset_x = 0.0
    instr.offset_y = 0.0
    instr.depth = 0.0
    instr.measurement_height = measurement_height
    instr.safe_approach_height = safe_approach_height
    return instr


def _protocol(args: dict, command_name: str = "scan") -> Protocol:
    return Protocol([
        ProtocolStep(
            index=0,
            command_name=command_name,
            handler=lambda *a, **k: None,
            args=args,
        )
    ])


def _gantry_config(
    *,
    x_max: float = 300.0,
    y_max: float = 200.0,
    z_max: float = 100.0,
    safe_z: float | None = None,
) -> GantryConfig:
    return GantryConfig(
        serial_port="/dev/null",
        homing_strategy=HomingStrategy.STANDARD,
        total_z_height=z_max,
        working_volume=WorkingVolume(
            x_min=0.0, x_max=x_max,
            y_min=0.0, y_max=y_max,
            z_min=0.0, z_max=z_max,
        ),
        safe_z=safe_z,
    )


def _board_and_deck(instrument=None):
    board = Board(
        gantry=MagicMock(),
        instruments={"asmi": instrument or _instrument("asmi")},
    )
    deck = Deck({"plate": _plate()})
    return board, deck


def _move_step(*, position, instrument: str = "asmi", travel_z: float | None = None,
               command_name: str = "move") -> Protocol:
    args: dict = {"instrument": instrument, "position": position}
    if travel_z is not None:
        args["travel_z"] = travel_z
    return _protocol(args, command_name=command_name)


def test_asmi_indentation_within_z_bounds_passes():
    """Indentation deepest abs Z = height_mm + measurement_height - |limit|."""
    instr = _instrument("asmi", measurement_height=-1.0)
    board, deck = _board_and_deck(instr)
    gantry = _gantry_config(z_max=100.0)
    protocol = _protocol({
        "plate": "plate",
        "instrument": "asmi",
        "method": "indentation",
        "safe_approach_height": 10.0,
        "indentation_limit": 5.0,
        "method_kwargs": {"step_size": 0.01},
    })

    assert validate_protocol_semantics(protocol, board, deck, gantry) == []


def test_asmi_indentation_below_z_min_violates():
    """height_mm=14.10 + measurement_height=-1.0 - |20.0| = -6.90 < z_min=0."""
    instr = _instrument("asmi", measurement_height=-1.0)
    board, deck = _board_and_deck(instr)
    gantry = _gantry_config(z_max=100.0)
    protocol = _protocol({
        "plate": "plate",
        "instrument": "asmi",
        "method": "indentation",
        "safe_approach_height": 10.0,
        "indentation_limit": 20.0,
        "method_kwargs": {"step_size": 0.01},
    })

    violations = validate_protocol_semantics(protocol, board, deck, gantry)

    assert any("indentation deepest" in v.message for v in violations)


def test_indentation_limit_is_sign_agnostic():
    """A negative limit and its positive counterpart produce identical bounds."""
    instr = _instrument("asmi", measurement_height=-1.0)
    board, deck = _board_and_deck(instr)
    gantry = _gantry_config(z_max=100.0)
    base_args = {
        "plate": "plate",
        "instrument": "asmi",
        "method": "indentation",
        "safe_approach_height": 10.0,
        "method_kwargs": {"step_size": 0.01},
    }

    pos = validate_protocol_semantics(
        _protocol({**base_args, "indentation_limit": 20.0}),
        board, deck, gantry,
    )
    neg = validate_protocol_semantics(
        _protocol({**base_args, "indentation_limit": -20.0}),
        board, deck, gantry,
    )

    assert [v.message for v in pos] == [v.message for v in neg]


def test_scan_safe_approach_below_measurement_violates():
    instr = _instrument("asmi", measurement_height=2.0)
    board, deck = _board_and_deck(instr)
    gantry = _gantry_config()
    protocol = _protocol({
        "plate": "plate",
        "instrument": "asmi",
        "method": "indentation",
        "safe_approach_height": 1.0,
        "method_kwargs": {"step_size": 0.01},
    })

    violations = validate_protocol_semantics(protocol, board, deck, gantry)

    assert any("approach must be at or above" in v.message for v in violations)


def test_scan_approach_above_safe_z_violates():
    instr = _instrument("asmi", measurement_height=-1.0)
    board, deck = _board_and_deck(instr)
    gantry = _gantry_config(z_max=100.0, safe_z=20.0)
    protocol = _protocol({
        "plate": "plate",
        "instrument": "asmi",
        "method": "indentation",
        "safe_approach_height": 10.0,
        "method_kwargs": {"step_size": 0.01},
    })

    violations = validate_protocol_semantics(protocol, board, deck, gantry)

    assert any("safe_z" in v.message for v in violations)


def test_valid_asmi_scan_semantics_pass():
    instr = _instrument("asmi", measurement_height=-1.0)
    board, deck = _board_and_deck(instr)
    gantry = _gantry_config(z_max=100.0, safe_z=85.0)
    protocol = _protocol({
        "plate": "plate",
        "instrument": "asmi",
        "method": "indentation",
        "safe_approach_height": 10.0,
        "indentation_limit": 5.0,
        "method_kwargs": {"step_size": 0.01},
    })

    assert validate_protocol_semantics(protocol, board, deck, gantry) == []


def test_legacy_scan_travel_names_are_semantic_violations():
    instr = _instrument("asmi", measurement_height=-1.0)
    board, deck = _board_and_deck(instr)
    protocol = _protocol({
        "plate": "plate",
        "instrument": "asmi",
        "method": "indentation",
        "safe_approach_height": 10.0,
        "method_kwargs": {
            "interwell_travel_height": 70.0,
            "step_size": 0.01,
        },
    })

    violations = validate_protocol_semantics(protocol, board, deck)

    assert any("interwell_travel_height" in v.message for v in violations)


def test_scan_top_level_measurement_height_is_rejected():
    """`measurement_height` is owned by the instrument config, never on
    the protocol command."""
    instr = _instrument("asmi", measurement_height=-1.0)
    board, deck = _board_and_deck(instr)
    protocol = _protocol({
        "plate": "plate",
        "instrument": "asmi",
        "method": "indentation",
        "measurement_height": -1.0,    # not allowed on scan args
        "safe_approach_height": 10.0,
        "method_kwargs": {"step_size": 0.01},
    })

    violations = validate_protocol_semantics(protocol, board, deck)

    assert any("not supported" in v.message for v in violations)


def test_scan_missing_instrument_measurement_height_violates():
    instr = _instrument("asmi", measurement_height=None)
    board, deck = _board_and_deck(instr)
    protocol = _protocol({
        "plate": "plate",
        "instrument": "asmi",
        "method": "indentation",
        "safe_approach_height": 10.0,
        "method_kwargs": {"step_size": 0.01},
    })

    violations = validate_protocol_semantics(protocol, board, deck)

    assert any("not set on instrument" in v.message for v in violations)


def test_legacy_asmi_z_limit_is_semantic_violation():
    instr = _instrument("asmi", measurement_height=-1.0)
    board, deck = _board_and_deck(instr)
    protocol = _protocol({
        "plate": "plate",
        "instrument": "asmi",
        "method": "indentation",
        "safe_approach_height": 10.0,
        "method_kwargs": {"z_limit": 70.0, "step_size": 0.01},
    })

    violations = validate_protocol_semantics(protocol, board, deck)

    assert any("`z_limit` is no longer supported" in v.message for v in violations)


def test_measure_missing_instrument_measurement_height_violates():
    instr = _instrument("asmi", measurement_height=None)
    board, deck = _board_and_deck(instr)
    protocol = _protocol(
        {"instrument": "asmi", "position": "plate.A1", "method": "measure"},
        command_name="measure",
    )

    violations = validate_protocol_semantics(protocol, board, deck)

    assert any("not set on instrument" in v.message for v in violations)


def test_measure_with_instrument_default_passes():
    instr = _instrument("asmi", measurement_height=-1.0)
    board, deck = _board_and_deck(instr)
    gantry = _gantry_config(z_max=100.0, safe_z=85.0)
    protocol = _protocol(
        {"instrument": "asmi", "position": "plate.A1", "method": "measure"},
        command_name="measure",
    )

    assert validate_protocol_semantics(protocol, board, deck, gantry) == []


# ─── working-volume bound checks for `move` ──────────────────────────────────


def test_move_target_in_bounds_with_zero_offsets_passes():
    board, deck = _board_and_deck()
    gantry = _gantry_config()
    protocol = _move_step(position=(150.0, 100.0, 50.0))

    assert validate_protocol_semantics(protocol, board, deck, gantry) == []


def test_move_x_offset_is_subtracted_so_offset_x_can_drive_violation():
    """Instrument offset_x must be SUBTRACTED from user X to get gantry X.

    A naive sign error (adding instead of subtracting) would not catch this:
    user x=290 with offset_x=20 → gantry x=270 (in-bounds), and would only
    appear out-of-bounds if the offset were added (290+20=310 > 300).
    Conversely, a user x=10 with offset_x=-300 must place gantry x at 310,
    which violates x_max=300.
    """
    instr = _instrument("asmi")
    instr.offset_x = -300.0
    board, deck = _board_and_deck(instr)
    gantry = _gantry_config(x_max=300.0)
    protocol = _move_step(position=(10.0, 100.0, 50.0))

    violations = validate_protocol_semantics(protocol, board, deck, gantry)

    assert any("x" in v.message and "310" in v.message for v in violations), violations


def test_move_y_offset_is_subtracted():
    instr = _instrument("asmi")
    instr.offset_y = -250.0
    board, deck = _board_and_deck(instr)
    gantry = _gantry_config(y_max=200.0)
    protocol = _move_step(position=(100.0, 10.0, 50.0))

    violations = validate_protocol_semantics(protocol, board, deck, gantry)

    assert any("y" in v.message for v in violations), violations


def test_move_depth_is_added_to_z():
    """instr.depth must be ADDED to user Z to get gantry Z.

    User z=80 with depth=30 → gantry z=110, which violates z_max=100.
    """
    instr = _instrument("asmi")
    instr.depth = 30.0
    board, deck = _board_and_deck(instr)
    gantry = _gantry_config(z_max=100.0)
    protocol = _move_step(position=(100.0, 100.0, 80.0))

    violations = validate_protocol_semantics(protocol, board, deck, gantry)

    assert any("z" in v.message and "110" in v.message for v in violations), violations


def test_move_target_at_volume_boundary_is_valid():
    """Inclusive bounds: value == low and value == high pass."""
    board, deck = _board_and_deck()
    gantry = _gantry_config(x_max=300.0, y_max=200.0, z_max=100.0)
    protocol = _move_step(position=(300.0, 200.0, 100.0))
    assert validate_protocol_semantics(protocol, board, deck, gantry) == []
    protocol = _move_step(position=(0.0, 0.0, 0.0))
    assert validate_protocol_semantics(protocol, board, deck, gantry) == []


def test_move_travel_z_violation_independent_of_target():
    instr = _instrument("asmi")
    instr.depth = 0.0
    board, deck = _board_and_deck(instr)
    gantry = _gantry_config(z_max=100.0)
    protocol = _move_step(position=(100.0, 100.0, 50.0), travel_z=150.0)

    violations = validate_protocol_semantics(protocol, board, deck, gantry)

    assert any("travel_z" in v.message for v in violations), violations


def test_move_to_unknown_named_position_emits_violation():
    """Bare-except previously hid this case; now resolve failures must surface."""
    board, deck = _board_and_deck()
    gantry = _gantry_config()
    protocol = _move_step(position="does_not_exist")

    violations = validate_protocol_semantics(protocol, board, deck, gantry)

    assert any("cannot be resolved" in v.message for v in violations), violations


def test_move_without_gantry_config_skips_bound_check():
    """Default-None gantry preserves backward compatibility with older callers."""
    board, deck = _board_and_deck()
    protocol = _move_step(position=(9999.0, 9999.0, 9999.0))
    assert validate_protocol_semantics(protocol, board, deck) == []


# ─── working-volume bound checks for `scan` ──────────────────────────────────


def test_scan_well_offset_x_drives_volume_violation():
    instr = _instrument("asmi", measurement_height=-1.0)
    instr.offset_x = -350.0
    board, deck = _board_and_deck(instr)
    gantry = _gantry_config(x_max=300.0)
    protocol = _protocol({
        "plate": "plate",
        "instrument": "asmi",
        "method": "indentation",
        "safe_approach_height": 10.0,
        "method_kwargs": {"step_size": 0.01},
    })

    violations = validate_protocol_semantics(protocol, board, deck, gantry)

    assert any("x" in v.message for v in violations), violations


def test_scan_depth_drives_z_violation():
    """height_mm=14.10 + measurement_height=80.0 + depth=30.0 = 124.10 > z_max=100."""
    instr = _instrument("asmi", measurement_height=80.0)
    instr.depth = 30.0
    board, deck = _board_and_deck(instr)
    gantry = _gantry_config(z_max=100.0)
    protocol = _protocol({
        "plate": "plate",
        "instrument": "asmi",
        "method": "indentation",
        "safe_approach_height": 85.0,
        "method_kwargs": {"step_size": 0.01},
    })

    violations = validate_protocol_semantics(protocol, board, deck, gantry)

    assert any("z" in v.message for v in violations), violations
