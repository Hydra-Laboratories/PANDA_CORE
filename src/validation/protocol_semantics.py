"""Semantic validation for protocol runtime movement assumptions.

The protocol model:

* ``measurement_height`` and ``safe_approach_height`` are *labware-relative*
  offsets (mm above the labware's ``height_mm`` surface; negative = below).
* ``measurement_height`` is owned by the instrument config (not on
  protocol commands). ``safe_approach_height`` may be on either source
  with a dual-source rule (at least one set; if both, values match).
* ``safe_approach_height`` is required only on ``scan`` commands.
* ``gantry.safe_z`` is the absolute deck-frame Z used for inter-labware
  travel and the entry approach for the first well of a scan. Resolved
  approach planes must satisfy ``height_mm + safe_approach_height <= safe_z``.
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


def _resolve_labware_for_target(
    deck: Deck, position: str,
) -> WellPlate | Any | None:
    """Resolve the labware referenced by a measure/move position string."""
    if not isinstance(position, str):
        return None
    labware_key = position.split(".", 1)[0]
    if labware_key not in deck:
        return None
    return deck[labware_key]


def _resolve_dual_source_height(
    *,
    instrument_value: float | None,
    command_value: float | None,
) -> tuple[float | None, str | None]:
    """Return ``(resolved, error_message)``.

    The field may be set on the instrument config, on the command, or
    both. At least one source must define it; if both do, they must
    agree.
    """
    if instrument_value is not None and command_value is not None:
        if instrument_value != command_value:
            return (
                None,
                f"set on the instrument config ({instrument_value}) and on "
                f"the command ({command_value}) with conflicting values; "
                "they must match",
            )
        return (instrument_value, None)
    if instrument_value is None and command_value is None:
        return (None, "is not set on either the instrument config or the command")
    return (
        instrument_value if instrument_value is not None else command_value,
        None,
    )


# Kept for compatibility with callers that import the old name.
_resolve_measurement_height = _resolve_dual_source_height


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
            safe_approach_height=args.get("safe_approach_height"),
            indentation_limit=args.get("indentation_limit"),
            method_kwargs=args.get("method_kwargs"),
        )
    except ValueError as exc:
        return [_violation(step_index, "scan", str(exc))]
    if "measurement_height" in args:
        return [_violation(
            step_index, "scan",
            "Top-level `measurement_height` on `scan` is not supported. "
            "`measurement_height` is owned by the instrument config; set "
            "it in the gantry YAML's `instruments:` block.",
        )]

    instrument = args.get("instrument")
    plate = args.get("plate")
    if instrument not in board.instruments or plate not in deck:
        return violations
    plate_obj = deck[plate]
    if not isinstance(plate_obj, WellPlate):
        return violations
    instr = board.instruments[instrument]

    if plate_obj.height_mm is None:
        violations.append(_violation(
            step_index, "scan",
            f"plate {plate!r} has no `height_mm` set. Add it to the deck "
            "YAML so labware-relative scan heights resolve.",
        ))
        return violations

    if instr.measurement_height is None:
        violations.append(_violation(
            step_index, "scan",
            f"`measurement_height` is not set on instrument {instrument!r}. "
            "Set it in the gantry YAML's `instruments:` block.",
        ))
        return violations
    relative_action = instr.measurement_height

    relative_approach, approach_error = _resolve_dual_source_height(
        instrument_value=getattr(instr, "safe_approach_height", None),
        command_value=normalized.safe_approach_height,
    )
    if approach_error:
        violations.append(_violation(
            step_index, "scan",
            f"`safe_approach_height` {approach_error}.",
        ))
        return violations

    if not math.isfinite(relative_action) or not math.isfinite(relative_approach):
        violations.append(_violation(
            step_index, "scan",
            "scan heights must be finite.",
        ))
        return violations

    if relative_approach < relative_action:
        violations.append(_violation(
            step_index, "scan",
            f"safe_approach_height ({relative_approach}) is below "
            f"measurement_height ({relative_action}). In +Z-up, the "
            "approach must be at or above the action plane.",
        ))

    ref_z = plate_obj.height_mm
    action_abs = ref_z + relative_action
    approach_abs = ref_z + relative_approach

    safe_z = _resolved_safe_z(gantry)
    if safe_z is not None and approach_abs > safe_z:
        violations.append(_violation(
            step_index, "scan",
            f"resolved approach Z ({approach_abs:.3f} = "
            f"{ref_z}+{relative_approach}) is above the gantry's safe_z "
            f"({safe_z}). Lower `safe_approach_height` or raise `safe_z`.",
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
        gantry=gantry,
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

    if "measurement_height" in args:
        violations.append(_violation(
            step_index, "measure",
            "Top-level `measurement_height` on `measure` is not supported. "
            "`measurement_height` is owned by the instrument config; set "
            "it in the gantry YAML's `instruments:` block.",
        ))
        return violations

    if instrument not in board.instruments:
        return violations

    labware = _resolve_labware_for_target(deck, position)
    if labware is None:
        return violations
    if getattr(labware, "height_mm", None) is None:
        violations.append(_violation(
            step_index, "measure",
            f"labware at {position!r} has no `height_mm` set.",
        ))
        return violations

    instr = board.instruments[instrument]
    if instr.measurement_height is None:
        violations.append(_violation(
            step_index, "measure",
            f"`measurement_height` is not set on instrument {instrument!r}. "
            "Set it in the gantry YAML's `instruments:` block.",
        ))
        return violations
    relative_action = instr.measurement_height
    if not math.isfinite(relative_action):
        violations.append(_violation(
            step_index, "measure",
            "measure measurement_height must be finite.",
        ))
        return violations

    try:
        coord = deck.resolve(position)
    except (KeyError, AttributeError, ValueError):
        return violations
    action_abs = labware.height_mm + relative_action
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
    gantry: GantryConfig | None,
) -> list[ProtocolSemanticViolation]:
    """Bounds-check ASMI indentation against the working volume.

    ``indentation_limit`` is treated as a magnitude (sign-agnostic): the
    deepest absolute Z reached during the descent is
    ``ref_z + relative_action - |indentation_limit|``.
    """
    violations: list[ProtocolSemanticViolation] = []
    if args.get("instrument") != "asmi" or args.get("method") != "indentation":
        return violations

    kwargs = normalized.method_kwargs
    indentation_limit = kwargs.get("indentation_limit")
    step_size = kwargs.get("step_size")

    if step_size is not None and step_size <= 0:
        violations.append(_violation(
            step_index, "scan",
            f"ASMI step_size must be positive, got {step_size}.",
        ))

    if indentation_limit is None or gantry is None:
        return violations
    deepest_abs = ref_z + relative_action - abs(indentation_limit)
    if deepest_abs < gantry.working_volume.z_min:
        violations.append(_violation(
            step_index, "scan",
            f"ASMI indentation deepest absolute Z ({deepest_abs:.3f}) is "
            f"below working_volume.z_min ({gantry.working_volume.z_min}). "
            "Reduce indentation_limit, raise the labware, or adjust z_min.",
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
