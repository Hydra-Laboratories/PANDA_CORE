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
from gantry.gantry_config import GantryConfig, MachineStructureBox

from .errors import ProtocolSemanticViolation

Point3D = tuple[float, float, float]


def _normalize_scan_args(
    *,
    step_index: int,
    args: dict[str, Any],
) -> tuple[NormalizedScanArguments | None, list[ProtocolSemanticViolation]]:
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


def _row_major_key(well_id: str) -> tuple[str, int]:
    return (well_id[0], int(well_id[1:]))


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


def _format_box(box: MachineStructureBox) -> str:
    return (
        f"X[{box.x_min}, {box.x_max}] "
        f"Y[{box.y_min}, {box.y_max}] "
        f"Z[{box.z_min}, {box.z_max}]"
    )


def _segment_intersects_box(
    start: Point3D,
    end: Point3D,
    box: MachineStructureBox,
) -> bool:
    t_min = 0.0
    t_max = 1.0
    for start_value, end_value, low, high in (
        (start[0], end[0], box.x_min, box.x_max),
        (start[1], end[1], box.y_min, box.y_max),
        (start[2], end[2], box.z_min, box.z_max),
    ):
        delta = end_value - start_value
        if delta == 0:
            if start_value < low or start_value > high:
                return False
            continue
        t1 = (low - start_value) / delta
        t2 = (high - start_value) / delta
        axis_min = min(t1, t2)
        axis_max = max(t1, t2)
        t_min = max(t_min, axis_min)
        t_max = min(t_max, axis_max)
        if t_min > t_max:
            return False
    return True


def _validate_machine_structure_point(
    *,
    step_index: int,
    command_name: str,
    gantry: GantryConfig | None,
    label: str,
    instrument: str,
    x: float,
    y: float,
    z: float,
) -> list[ProtocolSemanticViolation]:
    if gantry is None:
        return []
    violations: list[ProtocolSemanticViolation] = []
    for name, box in gantry.machine_structures.items():
        if box.contains(x, y, z):
            violations.append(ProtocolSemanticViolation(
                step_index,
                command_name,
                f"{label} instrument point ({x}, {y}, {z}) overlaps "
                f"machine structure {name!r} ({_format_box(box)}) for "
                f"instrument {instrument!r}.",
            ))
    return violations


def _validate_machine_structure_segment(
    *,
    step_index: int,
    command_name: str,
    gantry: GantryConfig | None,
    label: str,
    instrument: str,
    start: Point3D,
    end: Point3D,
) -> list[ProtocolSemanticViolation]:
    if gantry is None:
        return []
    violations: list[ProtocolSemanticViolation] = []
    for name, box in gantry.machine_structures.items():
        if _segment_intersects_box(start, end, box):
            violations.append(ProtocolSemanticViolation(
                step_index,
                command_name,
                f"{label} travel segment from {start} to {end} intersects "
                f"machine structure {name!r} ({_format_box(box)}) for "
                f"instrument {instrument!r}.",
            ))
    return violations


def _transit_segments(
    current: Point3D,
    target: Point3D,
    travel_z: float,
) -> list[tuple[str, Point3D, Point3D]]:
    current_x, current_y = current[0], current[1]
    target_x, target_y = target[0], target[1]
    travel_start = (current_x, current_y, travel_z)
    x_done = (target_x, current_y, travel_z)
    y_done = (target_x, target_y, travel_z)
    segments = [
        ("travel_z lift/lower", current, travel_start),
        ("travel_z X travel", travel_start, x_done),
        ("travel_z Y travel", x_done, y_done),
        ("travel_z final Z", y_done, target),
    ]
    return [segment for segment in segments if segment[1] != segment[2]]


def _home_pose_for_instrument(
    gantry: GantryConfig,
    instrument: Any,
) -> Point3D:
    volume = gantry.working_volume
    return (
        volume.x_max + instrument.offset_x,
        volume.y_max + instrument.offset_y,
        volume.z_max - instrument.depth,
    )


def _validate_home_waypoints(
    *,
    step_index: int,
    board: Board,
    gantry: GantryConfig | None,
    current_poses: dict[str, Point3D],
) -> list[ProtocolSemanticViolation]:
    if gantry is None:
        current_poses.clear()
        return []

    violations: list[ProtocolSemanticViolation] = []
    for instrument_name, instrument in board.instruments.items():
        pose = _home_pose_for_instrument(gantry, instrument)
        violations.extend(_validate_machine_structure_point(
            step_index=step_index,
            command_name="home",
            gantry=gantry,
            label="home pose",
            instrument=instrument_name,
            x=pose[0],
            y=pose[1],
            z=pose[2],
        ))
        current_poses[instrument_name] = pose
    return violations


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
    violations.extend(_validate_machine_structure_point(
        step_index=step_index,
        command_name=command_name,
        gantry=gantry,
        label=label,
        instrument=instrument,
        x=x,
        y=y,
        z=z,
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
    current_poses: dict[str, Point3D],
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

    current = current_poses.get(instrument)
    sorted_wells = sorted(
        plate_obj.wells.items(),
        key=lambda item: _row_major_key(item[0]),
    )
    for well_index, (well_id, well) in enumerate(sorted_wells):
        action_z = (
            mh_from_kwargs
            if mh_from_kwargs is not None
            else instr.measurement_height
        )
        if well_index == 0 and normalized.entry_travel_height is not None:
            approach_z = normalized.entry_travel_height
            approach_label = "entry_travel_height"
        elif normalized.interwell_travel_height is not None:
            approach_z = normalized.interwell_travel_height
            approach_label = "interwell_travel_height"
        else:
            approach_z = instr.safe_approach_height
            approach_label = "safe_approach_height"

        approach = (well.x, well.y, approach_z)
        action = (well.x, well.y, action_z)
        if current is not None:
            for segment_label, start, end in _transit_segments(
                current, approach, approach_z,
            ):
                violations.extend(_validate_machine_structure_segment(
                    step_index=step_index,
                    command_name="scan",
                    gantry=gantry,
                    label=(
                        f"{plate}.{well_id} {approach_label} "
                        f"{segment_label}"
                    ),
                    instrument=instrument,
                    start=start,
                    end=end,
                ))
        violations.extend(_validate_machine_structure_segment(
            step_index=step_index,
            command_name="scan",
            gantry=gantry,
            label=f"{plate}.{well_id} action_z descend",
            instrument=instrument,
            start=approach,
            end=action,
        ))
        current = action

    if sorted_wells:
        last_well_id, last_well = sorted_wells[-1]
        final_approach_z = (
            normalized.interwell_travel_height
            if normalized.interwell_travel_height is not None
            else instr.safe_approach_height
        )
        final_approach = (last_well.x, last_well.y, final_approach_z)
        if current is not None:
            violations.extend(_validate_machine_structure_segment(
                step_index=step_index,
                command_name="scan",
                gantry=gantry,
                label=f"{plate}.{last_well_id} final approach",
                instrument=instrument,
                start=current,
                end=final_approach,
            ))
        current_poses[instrument] = final_approach

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
    current_poses: dict[str, Point3D],
) -> list[ProtocolSemanticViolation]:
    violations: list[ProtocolSemanticViolation] = []
    instrument = args.get("instrument")
    position = args.get("position")
    travel_z = args.get("travel_z")
    if instrument not in board.instruments:
        return violations

    target: Point3D | None = None
    target_label = f"move target {position!r}"
    transit_z = travel_z
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
        target_label = f"move safe_approach_height for {position!r}"
        transit_z = approach_z

    if target is None:
        return violations

    x, y, z = target
    violations.extend(_validate_gantry_waypoint(
        step_index=step_index,
        command_name="move",
        gantry=gantry,
        label=target_label,
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
    if transit_z is not None and instrument in current_poses:
        for segment_label, start, end in _transit_segments(
            current_poses[instrument], target, transit_z,
        ):
            violations.extend(_validate_machine_structure_segment(
                step_index=step_index,
                command_name="move",
                gantry=gantry,
                label=f"{target_label} {segment_label}",
                instrument=instrument,
                start=start,
                end=end,
            ))
    current_poses[instrument] = target
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
    current_poses: dict[str, Point3D] = {}
    for step in protocol.steps:
        if step.command_name == "home":
            violations.extend(_validate_home_waypoints(
                step_index=step.index,
                board=board,
                gantry=gantry,
                current_poses=current_poses,
            ))
            continue
        if step.command_name == "move":
            violations.extend(_validate_move_waypoints(
                step_index=step.index,
                args=step.args,
                protocol=protocol,
                board=board,
                deck=deck,
                gantry=gantry,
                current_poses=current_poses,
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
            current_poses=current_poses,
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
