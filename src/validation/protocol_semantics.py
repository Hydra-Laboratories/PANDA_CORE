"""Semantic validation for protocol runtime movement assumptions."""

from __future__ import annotations

import math
from typing import Any

from deck.labware.well_plate import WellPlate
from protocol_engine.protocol import Protocol
from protocol_engine.scan_args import (
    NormalizedScanArguments,
    normalize_scan_arguments,
)
from board.board import Board
from deck.deck import Deck
from gantry.gantry_config import GantryConfig

from .errors import ProtocolSemanticViolation


def _normalize_scan_args(
    *,
    step_index: int,
    args: dict[str, Any],
) -> tuple[NormalizedScanArguments | None, list[ProtocolSemanticViolation]]:
    legacy_messages: list[ProtocolSemanticViolation] = []
    if "entry_travel_z" in args:
        legacy_messages.append(ProtocolSemanticViolation(
            step_index,
            "scan",
            "`entry_travel_z` is no longer supported. Use `entry_travel_height`.",
        ))
    if "safe_approach_height" in args:
        legacy_messages.append(ProtocolSemanticViolation(
            step_index,
            "scan",
            "`safe_approach_height` is no longer supported. Use `interwell_travel_height`.",
        ))
    if "measurement_height" in args:
        legacy_messages.append(ProtocolSemanticViolation(
            step_index,
            "scan",
            "Top-level `measurement_height` on `scan` is no longer supported. "
            "Move it inside `method_kwargs.measurement_height`; scan owns "
            "travel-Z between wells, per-well action Z lives with the method.",
        ))
    if "indentation_limit" in args:
        legacy_messages.append(ProtocolSemanticViolation(
            step_index,
            "scan",
            "Top-level `indentation_limit` on `scan` is no longer supported. "
            "Move it inside `method_kwargs.indentation_limit`.",
        ))
    if legacy_messages:
        return (None, legacy_messages)
    try:
        return (
            normalize_scan_arguments(
                entry_travel_height=args.get("entry_travel_height"),
                interwell_travel_height=args.get("interwell_travel_height"),
                method_kwargs=args.get("method_kwargs"),
            ),
            [],
        )
    except ValueError as exc:
        return (
            None,
            [ProtocolSemanticViolation(step_index, "scan", str(exc))],
        )


def _validate_scan_travel_heights(
    *,
    step_index: int,
    args: dict[str, Any],
    normalized: NormalizedScanArguments,
    board: Board,
    deck: Deck,
) -> list[ProtocolSemanticViolation]:
    violations: list[ProtocolSemanticViolation] = []
    instrument = args.get("instrument")
    plate = args.get("plate")

    if instrument not in board.instruments:
        return violations
    if plate not in deck:
        return violations

    plate_obj = deck[plate]
    if not isinstance(plate_obj, WellPlate):
        return violations

    instr = board.instruments[instrument]
    travel_fields = [(
        "interwell_travel_height",
        normalized.interwell_travel_height,
    )]
    if normalized.entry_travel_height != normalized.interwell_travel_height:
        travel_fields.append(("entry_travel_height", normalized.entry_travel_height))
    for field_name, travel_z in travel_fields:
        if travel_z is None:
            continue
        if not math.isfinite(float(travel_z)):
            violations.append(ProtocolSemanticViolation(
                step_index,
                "scan",
                f"{field_name} must be finite, got {travel_z!r}.",
            ))
            continue
        for well_id, well in plate_obj.wells.items():
            mh_from_kwargs = normalized.method_kwargs.get("measurement_height")
            action_z = (
                mh_from_kwargs
                if mh_from_kwargs is not None
                else instr.measurement_height
            )
            if travel_z < action_z:
                violations.append(ProtocolSemanticViolation(
                    step_index,
                    "scan",
                    f"{field_name} ({travel_z}) is below action_z ({action_z}) "
                    f"for {plate}.{well_id} under the deck-origin +Z-up "
                    "convention.",
                ))
                break

    return violations


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
            violations.append(ProtocolSemanticViolation(
                step_index,
                command_name,
                f"{label} gantry {axis}={value} is outside working volume "
                f"[{low}, {high}] for instrument {instrument!r}.",
            ))
    return violations


def _validate_scan_waypoints(
    *,
    step_index: int,
    args: dict[str, Any],
    normalized: NormalizedScanArguments,
    board: Board,
    deck: Deck,
    gantry: GantryConfig | None,
) -> list[ProtocolSemanticViolation]:
    violations: list[ProtocolSemanticViolation] = []
    instrument = args.get("instrument")
    plate = args.get("plate")

    if instrument not in board.instruments or plate not in deck:
        return violations
    plate_obj = deck[plate]
    if not isinstance(plate_obj, WellPlate):
        return violations

    instr = board.instruments[instrument]
    travel_fields = [(
        "interwell_travel_height",
        normalized.interwell_travel_height,
    )]
    if normalized.entry_travel_height != normalized.interwell_travel_height:
        travel_fields.append(("entry_travel_height", normalized.entry_travel_height))

    mh_from_kwargs = normalized.method_kwargs.get("measurement_height")
    for well_id, well in plate_obj.wells.items():
        action_z = (
            mh_from_kwargs
            if mh_from_kwargs is not None
            else instr.measurement_height
        )
        violations.extend(_validate_gantry_waypoint(
            step_index=step_index,
            command_name="scan",
            gantry=gantry,
            label=f"{plate}.{well_id} action_z",
            instrument=instrument,
            board=board,
            x=well.x,
            y=well.y,
            z=action_z,
        ))
        for field_name, travel_z in travel_fields:
            if travel_z is None:
                continue
            violations.extend(_validate_gantry_waypoint(
                step_index=step_index,
                command_name="scan",
                gantry=gantry,
                label=f"{plate}.{well_id} {field_name}",
                instrument=instrument,
                board=board,
                x=well.x,
                y=well.y,
                z=travel_z,
            ))

    return violations


def _validate_structure_clearance(
    *,
    step_index: int,
    command_name: str,
    label: str,
    z: float | None,
    gantry: GantryConfig | None,
) -> list[ProtocolSemanticViolation]:
    clearance = getattr(gantry, "structure_clearance_z", None)
    if clearance is None or z is None:
        return []
    if z < clearance:
        return [ProtocolSemanticViolation(
            step_index,
            command_name,
            f"{label} ({z}) is below configured structure_clearance_z "
            f"({clearance}). Use a higher absolute Z before entering "
            "home/park/edge-risk regions.",
        )]
    return []


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
            violations.append(ProtocolSemanticViolation(
                step_index,
                "move",
                f"position {position!r} cannot be resolved on the deck: {exc}",
            ))
            return violations
        approach_z = board.instruments[instrument].safe_approach_height
        target = (coord.x, coord.y, approach_z)

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
        violations.extend(_validate_structure_clearance(
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
    normalized: NormalizedScanArguments,
) -> list[ProtocolSemanticViolation]:
    violations: list[ProtocolSemanticViolation] = []
    if args.get("instrument") != "asmi" or args.get("method") != "indentation":
        return violations

    kwargs = normalized.method_kwargs
    measurement_height = kwargs.get("measurement_height")
    indentation_limit = kwargs.get("indentation_limit")
    step_size = kwargs.get("step_size")

    if step_size is not None and step_size <= 0:
        violations.append(ProtocolSemanticViolation(
            step_index,
            "scan",
            f"ASMI step_size must be positive, got {step_size}.",
        ))

    if measurement_height is None or indentation_limit is None:
        return violations

    if indentation_limit >= measurement_height:
        violations.append(ProtocolSemanticViolation(
            step_index,
            "scan",
            "ASMI indentation_limit must be less than measurement_height under the "
            f"deck-origin +Z-up convention; got measurement_height="
            f"{measurement_height}, indentation_limit={indentation_limit}.",
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
            continue
        if step.command_name != "scan":
            continue
        normalized, normalization_violations = _normalize_scan_args(
            step_index=step.index,
            args=step.args,
        )
        violations.extend(normalization_violations)
        if normalized is None:
            continue
        violations.extend(_validate_scan_travel_heights(
            step_index=step.index,
            args=step.args,
            normalized=normalized,
            board=board,
            deck=deck,
        ))
        violations.extend(_validate_scan_waypoints(
            step_index=step.index,
            args=step.args,
            normalized=normalized,
            board=board,
            deck=deck,
            gantry=gantry,
        ))
        violations.extend(_validate_structure_clearance(
            step_index=step.index,
            command_name="scan",
            label="entry_travel_height",
            z=normalized.entry_travel_height,
            gantry=gantry,
        ))
        violations.extend(_validate_asmi_indentation(
            step_index=step.index,
            args=step.args,
            normalized=normalized,
        ))
    return violations
