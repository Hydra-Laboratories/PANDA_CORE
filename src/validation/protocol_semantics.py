"""Semantic validation for protocol runtime movement assumptions.

The protocol model:

* ``measurement_height`` and ``interwell_scan_height`` are *labware-relative*
  offsets (mm above the well's calibrated surface Z; negative = below)
  and are first-class arguments to the protocol commands that use them.
* ``measurement_height`` is required on ``measure`` and ``scan``.
* ``interwell_scan_height`` is required on ``scan``.
* Instruments do not declare these heights.
* ``gantry.safe_z`` is the absolute deck-frame Z used for inter-labware
  travel and the entry approach for the first well of a scan. Resolved
  approach planes must satisfy ``well.z + interwell_scan_height <= safe_z``.
"""

from __future__ import annotations

import math
from typing import Any

from deck.deck import Deck
from deck.labware.well_plate import WellPlate
from board.board import Board
from gantry.gantry_config import GantryConfig
from protocol_engine.protocol import Protocol
from protocol_engine.scan_args import (
    NormalizedScanArguments,
    normalize_scan_arguments,
)

from .errors import ProtocolSemanticViolation


def _violation(step_index: int, command: str, message: str) -> ProtocolSemanticViolation:
    return ProtocolSemanticViolation(step_index, command, message)


def _finite_field_violation(
    step_index: int,
    command: str,
    field_name: str,
    value: Any,
) -> ProtocolSemanticViolation | None:
    """Return a per-field finite-number violation, or None when *value* passes.

    Mirrors the message format of ``_movement._assert_finite_number`` so a
    field name and the offending value (with type) are always surfaced —
    a single combined "scan heights must be finite" message hides which
    field is bad and what the bad value was.
    """
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        return _violation(
            step_index, command,
            f"{field_name} must be a finite number, got "
            f"{type(value).__name__} {value!r}.",
        )
    return None


def _resolved_safe_z(gantry: GantryConfig | None) -> float | None:
    if gantry is None:
        return None
    return gantry.resolved_safe_z


def _gantry_xyz_for_tip(
    board: Board,
    instrument: str,
    x: float,
    y: float,
    z: float,
) -> tuple[float, float, float]:
    instr = board.instruments[instrument]
    return (x - instr.offset_x, y - instr.offset_y, z + instr.depth)


def _validate_gantry_waypoint(
    *,
    step_index: int,
    command_name: str,
    gantry: GantryConfig | None,
    label: str,
    instrument: str,
    board: Board,
    x: float,
    y: float,
    z: float,
) -> list[ProtocolSemanticViolation]:
    if gantry is None or instrument not in board.instruments:
        return []
    gx, gy, gz = _gantry_xyz_for_tip(board, instrument, x, y, z)
    volume = gantry.working_volume
    violations: list[ProtocolSemanticViolation] = []
    for axis, value, low, high in (
        ("x", gx, volume.x_min, volume.x_max),
        ("y", gy, volume.y_min, volume.y_max),
        ("z", gz, volume.z_min, volume.z_max),
    ):
        if value < low or value > high:
            violations.append(_violation(
                step_index,
                command_name,
                f"{label} gantry {axis}={value} is outside working volume "
                f"[{low}, {high}] for instrument {instrument!r}.",
            ))
    return violations


def _validate_below_safe_z(
    *,
    step_index: int,
    command_name: str,
    label: str,
    z: float | None,
    gantry: GantryConfig | None,
) -> list[ProtocolSemanticViolation]:
    """Verify that absolute Z *z* is at or below ``safe_z`` (the ceiling)."""
    safe_z = _resolved_safe_z(gantry)
    if safe_z is None or z is None:
        return []
    if z > safe_z:
        return [_violation(
            step_index,
            command_name,
            f"{label} ({z}) is above the gantry's safe_z ({safe_z}). "
            "All resolved action and approach Z values must satisfy "
            "z <= safe_z so the gantry can retract above them.",
        )]
    return []


def _validate_scan_command(
    *,
    step_index: int,
    args: dict[str, Any],
    board: Board,
    deck: Deck,
    gantry: GantryConfig | None,
) -> list[ProtocolSemanticViolation]:
    violations: list[ProtocolSemanticViolation] = []

    try:
        normalized = normalize_scan_arguments(
            indentation_limit_height=args.get("indentation_limit_height"),
            method_kwargs=args.get("method_kwargs"),
        )
    except ValueError as exc:
        return [_violation(step_index, "scan", str(exc))]

    relative_action = args.get("measurement_height")
    relative_approach = args.get("interwell_scan_height")
    if relative_action is None:
        violations.append(_violation(
            step_index, "scan",
            "`measurement_height` is required on `scan` (labware-relative "
            "offset, mm above the well's calibrated surface Z).",
        ))
        return violations
    if relative_approach is None:
        violations.append(_violation(
            step_index, "scan",
            "`interwell_scan_height` is required on `scan` (labware-relative "
            "offset for between-wells XY travel).",
        ))
        return violations

    instrument = args.get("instrument")
    plate = args.get("plate")
    if instrument not in board.instruments or plate not in deck:
        return violations
    plate_obj = deck[plate]
    if not isinstance(plate_obj, WellPlate):
        return violations

    try:
        ref_z = plate_obj.get_well_center("A1").z
    except KeyError:
        violations.append(_violation(
            step_index, "scan",
            f"plate {plate!r} has no calibrated A1 well; cannot resolve "
            "the surface Z reference for labware-relative heights.",
        ))
        return violations

    finite_violations = [
        v for v in (
            _finite_field_violation(
                step_index, "scan", "measurement_height", relative_action,
            ),
            _finite_field_violation(
                step_index, "scan", "interwell_scan_height", relative_approach,
            ),
        ) if v is not None
    ]
    if finite_violations:
        violations.extend(finite_violations)
        return violations

    if relative_approach < relative_action:
        violations.append(_violation(
            step_index, "scan",
            f"interwell_scan_height ({relative_approach}) is below "
            f"measurement_height ({relative_action}). In +Z-up, the "
            "approach must be at or above the action plane.",
        ))

    action_abs = ref_z + relative_action
    approach_abs = ref_z + relative_approach

    safe_z = _resolved_safe_z(gantry)
    if safe_z is not None and approach_abs > safe_z:
        violations.append(_violation(
            step_index, "scan",
            f"resolved approach Z ({approach_abs:.3f} = "
            f"{ref_z}+{relative_approach}) is above the gantry's safe_z "
            f"({safe_z}). Lower `interwell_scan_height` or raise `safe_z`.",
        ))

    for well_id, well in plate_obj.wells.items():
        violations.extend(_validate_gantry_waypoint(
            step_index=step_index,
            command_name="scan",
            gantry=gantry,
            label=f"{plate}.{well_id} action_z",
            instrument=instrument,
            board=board,
            x=well.x,
            y=well.y,
            z=action_abs,
        ))
        violations.extend(_validate_gantry_waypoint(
            step_index=step_index,
            command_name="scan",
            gantry=gantry,
            label=f"{plate}.{well_id} approach_z",
            instrument=instrument,
            board=board,
            x=well.x,
            y=well.y,
            z=approach_abs,
        ))

    violations.extend(_validate_asmi_indentation(
        step_index=step_index,
        args=args,
        ref_z=ref_z,
        relative_action=relative_action,
        normalized=normalized,
        board=board,
        gantry=gantry,
    ))
    indentation_limit_height = args.get("indentation_limit_height")
    if (
        indentation_limit_height is not None
        and isinstance(indentation_limit_height, (int, float))
        and not isinstance(indentation_limit_height, bool)
        and math.isfinite(float(indentation_limit_height))
        and indentation_limit_height > relative_action
    ):
        violations.append(_violation(
            step_index, "scan",
            f"indentation_limit_height ({indentation_limit_height}) is above "
            f"measurement_height ({relative_action}). The deepest descent "
            "plane must be at or below the action plane in +Z-up.",
        ))
    return violations


def _validate_measure_command(
    *,
    step_index: int,
    args: dict[str, Any],
    board: Board,
    deck: Deck,
    gantry: GantryConfig | None,
) -> list[ProtocolSemanticViolation]:
    violations: list[ProtocolSemanticViolation] = []
    instrument = args.get("instrument")
    position = args.get("position")
    relative_action = args.get("measurement_height")

    if relative_action is None:
        violations.append(_violation(
            step_index, "measure",
            "`measurement_height` is required on `measure` (labware-relative "
            "offset, mm above the resolved coordinate's surface Z).",
        ))
        return violations

    if instrument not in board.instruments:
        return violations

    finite_violation = _finite_field_violation(
        step_index, "measure", "measurement_height", relative_action,
    )
    if finite_violation is not None:
        violations.append(finite_violation)
        return violations

    try:
        coord = deck.resolve(position)
    except (KeyError, AttributeError, ValueError):
        return violations
    action_abs = coord.z + relative_action
    violations.extend(_validate_gantry_waypoint(
        step_index=step_index,
        command_name="measure",
        gantry=gantry,
        label=f"measure {position!r} action_z",
        instrument=instrument,
        board=board,
        x=coord.x,
        y=coord.y,
        z=action_abs,
    ))
    violations.extend(_validate_below_safe_z(
        step_index=step_index,
        command_name="measure",
        label=f"measure {position!r} action_z",
        z=action_abs,
        gantry=gantry,
    ))
    return violations


def _validate_move_waypoints(
    *,
    step_index: int,
    args: dict[str, Any],
    protocol: Protocol,
    board: Board,
    deck: Deck,
    gantry: GantryConfig | None,
) -> list[ProtocolSemanticViolation]:
    violations: list[ProtocolSemanticViolation] = []
    instrument = args.get("instrument")
    position = args.get("position")
    travel_z = args.get("travel_z")
    if instrument not in board.instruments:
        return violations

    target: tuple[float, float, float] | None = None
    if isinstance(position, (list, tuple)):
        target = (position[0], position[1], position[2])
    elif isinstance(position, str) and position in protocol.positions:
        named = protocol.positions[position]
        target = (named[0], named[1], named[2])
    elif isinstance(position, str):
        try:
            coord = deck.resolve(position)
        except (KeyError, AttributeError, ValueError) as exc:
            violations.append(_violation(
                step_index, "move",
                f"position {position!r} cannot be resolved on the deck: {exc}",
            ))
            return violations
        safe_z = _resolved_safe_z(gantry)
        if safe_z is None:
            violations.append(_violation(
                step_index, "move",
                f"deck-target move to {position!r} requires gantry `safe_z` "
                "to be configured.",
            ))
            return violations
        target = (coord.x, coord.y, safe_z)

    if target is None:
        return violations

    x, y, z = target
    violations.extend(_validate_gantry_waypoint(
        step_index=step_index,
        command_name="move",
        gantry=gantry,
        label=f"move target {position!r}",
        instrument=instrument,
        board=board,
        x=x,
        y=y,
        z=z,
    ))
    if travel_z is not None:
        violations.extend(_validate_gantry_waypoint(
            step_index=step_index,
            command_name="move",
            gantry=gantry,
            label=f"move travel_z for {position!r}",
            instrument=instrument,
            board=board,
            x=x,
            y=y,
            z=travel_z,
        ))
        violations.extend(_validate_below_safe_z(
            step_index=step_index,
            command_name="move",
            label=f"move travel_z for {position!r}",
            z=travel_z,
            gantry=gantry,
        ))
    return violations


def _validate_asmi_indentation(
    *,
    step_index: int,
    args: dict[str, Any],
    ref_z: float,
    relative_action: float,
    normalized: NormalizedScanArguments,
    board: Board,
    gantry: GantryConfig | None,
) -> list[ProtocolSemanticViolation]:
    """Bounds-check ASMI indentation against the working volume.

    ``indentation_limit_height`` is a *signed* labware-relative offset
    (mm above the well's calibrated surface Z; negative = below). The
    deepest absolute Z reached during the descent is
    ``ref_z + indentation_limit_height``.
    """
    # Match by *type* (not by the user-chosen instrument key) so a force
    # sensor named e.g. ``force_sensor`` or ``asmi_main`` still goes
    # through the depth-bound check. The deepest-Z bound is the only thing
    # protecting against driving the gantry through the deck.
    from instruments.asmi.driver import ASMI

    violations: list[ProtocolSemanticViolation] = []
    instrument = args.get("instrument")
    if (
        instrument not in board.instruments
        or not isinstance(board.instruments[instrument], ASMI)
        or args.get("method") != "indentation"
    ):
        return violations

    indentation_limit_height = args.get("indentation_limit_height")
    step_size = normalized.method_kwargs.get("step_size")

    if step_size is not None and step_size <= 0:
        violations.append(_violation(
            step_index, "scan",
            f"ASMI step_size must be positive, got {step_size}.",
        ))

    if indentation_limit_height is None or gantry is None:
        return violations
    deepest_abs = ref_z + indentation_limit_height
    if deepest_abs < gantry.working_volume.z_min:
        violations.append(_violation(
            step_index, "scan",
            f"ASMI indentation deepest absolute Z ({deepest_abs:.3f}) is "
            f"below working_volume.z_min ({gantry.working_volume.z_min}). "
            "Raise `indentation_limit_height`, raise the labware, or adjust "
            "z_min.",
        ))
    return violations


def validate_protocol_semantics(
    protocol: Protocol,
    board: Board,
    deck: Deck,
    gantry: GantryConfig | None = None,
) -> list[ProtocolSemanticViolation]:
    """Return protocol semantic violations that static bounds checks miss."""
    violations: list[ProtocolSemanticViolation] = []
    for step in protocol.steps:
        if step.command_name == "move":
            violations.extend(_validate_move_waypoints(
                step_index=step.index,
                args=step.args,
                protocol=protocol,
                board=board,
                deck=deck,
                gantry=gantry,
            ))
        elif step.command_name == "measure":
            violations.extend(_validate_measure_command(
                step_index=step.index,
                args=step.args,
                board=board,
                deck=deck,
                gantry=gantry,
            ))
        elif step.command_name == "scan":
            violations.extend(_validate_scan_command(
                step_index=step.index,
                args=step.args,
                board=board,
                deck=deck,
                gantry=gantry,
            ))
    return violations
