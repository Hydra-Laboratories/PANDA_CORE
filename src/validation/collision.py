"""Static pre-run collision validation for protocol setup.

The v1 model is intentionally conservative and dependency-free. It validates
axis-aligned envelopes at safe-Z and working poses; it does not perform path
planning, swept-volume checks, or layout optimization.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Literal

from board.board import Board
from deck.deck import Deck
from deck.labware.holder import HolderLabware
from deck.labware.labware import Coordinate3D, Labware
from deck.labware.tip_rack import TipRack
from deck.labware.well_plate import WellPlate
from gantry.gantry_config import GantryConfig, WorkingVolume
from protocol_engine.protocol import Protocol, ProtocolContext, ProtocolStep

from .errors import CollisionIssue


class CollisionValidationMode(str, Enum):
    """Strictness for collision validation."""

    STRICT = "strict"
    REPORT_ONLY = "report_only"


@dataclass(frozen=True)
class CollisionSettings:
    """Configuration for static collision validation."""

    mode: CollisionValidationMode = CollisionValidationMode.STRICT
    clearance_mm: float = 2.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.clearance_mm) or self.clearance_mm < 0:
            raise ValueError("clearance_mm must be a finite non-negative number.")


@dataclass(frozen=True)
class CollisionBox:
    """Axis-aligned bounding box in user-facing deck coordinates."""

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float

    def __post_init__(self) -> None:
        if self.x_min > self.x_max:
            raise ValueError("x_min must be <= x_max.")
        if self.y_min > self.y_max:
            raise ValueError("y_min must be <= y_max.")
        if self.z_min > self.z_max:
            raise ValueError("z_min must be <= z_max.")

    @classmethod
    def from_origin_size(
        cls,
        *,
        origin_x: float,
        origin_y: float,
        origin_z: float,
        size_x: float,
        size_y: float,
        size_z: float,
    ) -> "CollisionBox":
        if size_x <= 0 or size_y <= 0 or size_z <= 0:
            raise ValueError("Collision dimensions must be positive.")
        return cls(
            x_min=origin_x,
            x_max=origin_x + size_x,
            y_min=origin_y,
            y_max=origin_y + size_y,
            z_min=origin_z,
            z_max=origin_z + size_z,
        )

    @classmethod
    def from_center_base(
        cls,
        *,
        center_x: float,
        center_y: float,
        base_z: float,
        size_x: float,
        size_y: float,
        size_z: float,
    ) -> "CollisionBox":
        if size_x <= 0 or size_y <= 0 or size_z <= 0:
            raise ValueError("Collision dimensions must be positive.")
        return cls(
            x_min=center_x - size_x / 2,
            x_max=center_x + size_x / 2,
            y_min=center_y - size_y / 2,
            y_max=center_y + size_y / 2,
            z_min=base_z,
            z_max=base_z + size_z,
        )

    def translated(self, dx: float, dy: float, dz: float) -> "CollisionBox":
        return CollisionBox(
            x_min=self.x_min + dx,
            x_max=self.x_max + dx,
            y_min=self.y_min + dy,
            y_max=self.y_max + dy,
            z_min=self.z_min + dz,
            z_max=self.z_max + dz,
        )

    def intersects(self, other: "CollisionBox") -> bool:
        """Return True when boxes overlap with positive volume."""
        return (
            self.x_min < other.x_max
            and self.x_max > other.x_min
            and self.y_min < other.y_max
            and self.y_max > other.y_min
            and self.z_min < other.z_max
            and self.z_max > other.z_min
        )

    def overlaps_xy(self, other: "CollisionBox") -> bool:
        return (
            self.x_min < other.x_max
            and self.x_max > other.x_min
            and self.y_min < other.y_max
            and self.y_max > other.y_min
        )

    def contained_by(self, volume: WorkingVolume) -> bool:
        return (
            volume.x_min <= self.x_min <= self.x_max <= volume.x_max
            and volume.y_min <= self.y_min <= self.y_max <= volume.y_max
            and volume.z_min <= self.z_min <= self.z_max <= volume.z_max
        )


@dataclass(frozen=True)
class CollisionEnvelope:
    """Named physical collision envelope."""

    key: str
    owner_type: Literal["labware", "instrument"]
    box: CollisionBox


@dataclass(frozen=True)
class CollisionPose:
    """One protocol pose to validate statically."""

    step_index: int
    command_name: str
    active_instrument: str
    target: Coordinate3D
    target_key: str | None = None
    purpose: str = "working_pose"


@dataclass
class CollisionReport:
    """Structured collision validation report."""

    issues: list[CollisionIssue] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[CollisionIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[CollisionIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def add_issue(
        self,
        *,
        severity: Literal["error", "warning", "suggestion"],
        code: str,
        message: str,
        step_index: int | None = None,
        command_name: str | None = None,
        active_instrument: str | None = None,
        body_a: str | None = None,
        body_b: str | None = None,
    ) -> None:
        self.issues.append(
            CollisionIssue(
                severity=severity,
                code=code,
                message=message,
                step_index=step_index,
                command_name=command_name,
                active_instrument=active_instrument,
                body_a=body_a,
                body_b=body_b,
            )
        )


def _issue_severity(settings: CollisionSettings) -> Literal["error", "warning"]:
    if settings.mode == CollisionValidationMode.STRICT:
        return "error"
    return "warning"


def _dimensions_from_geometry(labware: Labware) -> tuple[float, float, float] | None:
    geometry = getattr(labware, "geometry", None)
    if geometry is None:
        return None
    length = geometry.length_mm
    width = geometry.width_mm
    height = geometry.height_mm
    if length is None or width is None or height is None:
        return None
    return (length, width, height)


def _positions_xy_box(
    positions: Iterable[Coordinate3D],
    *,
    fallback_center: Coordinate3D,
    length_mm: float,
    width_mm: float,
    height_mm: float,
) -> CollisionBox:
    coords = list(positions)
    if not coords:
        return CollisionBox.from_center_base(
            center_x=fallback_center.x,
            center_y=fallback_center.y,
            base_z=fallback_center.z,
            size_x=length_mm,
            size_y=width_mm,
            size_z=height_mm,
        )

    min_x = min(coord.x for coord in coords)
    max_x = max(coord.x for coord in coords)
    min_y = min(coord.y for coord in coords)
    max_y = max(coord.y for coord in coords)
    min_z = min(coord.z for coord in coords)
    spread_x = max_x - min_x
    spread_y = max_y - min_y
    pad_x = max((length_mm - spread_x) / 2, 0.0)
    pad_y = max((width_mm - spread_y) / 2, 0.0)
    return CollisionBox(
        x_min=min_x - pad_x,
        x_max=max_x + pad_x,
        y_min=min_y - pad_y,
        y_max=max_y + pad_y,
        z_min=min_z,
        z_max=min_z + height_mm,
    )


def build_labware_envelopes(
    deck: Deck,
    *,
    settings: CollisionSettings | None = None,
) -> tuple[list[CollisionEnvelope], CollisionReport]:
    """Build conservative deck-space envelopes for all labware."""
    settings = settings or CollisionSettings()
    report = CollisionReport()
    envelopes: list[CollisionEnvelope] = []

    def add_labware(key: str, labware: Labware) -> None:
        dims = _dimensions_from_geometry(labware)
        if dims is None:
            report.add_issue(
                severity=_issue_severity(settings),
                code="missing_labware_geometry",
                message=f"Labware '{key}' is missing collision dimensions.",
                body_a=key,
            )
            return

        length, width, height = dims
        if isinstance(labware, (WellPlate, TipRack)):
            box = _positions_xy_box(
                labware.iter_positions().values(),
                fallback_center=labware.get_initial_position(),
                length_mm=length,
                width_mm=width,
                height_mm=height,
            )
        else:
            loc = labware.get_initial_position()
            box = CollisionBox.from_center_base(
                center_x=loc.x,
                center_y=loc.y,
                base_z=loc.z,
                size_x=length,
                size_y=width,
                size_z=height,
            )

        envelopes.append(CollisionEnvelope(key=key, owner_type="labware", box=box))

        if isinstance(labware, HolderLabware):
            for child_key, child in labware.contained_labware.items():
                add_labware(f"{key}.{child_key}", child)

    for key in deck:
        add_labware(key, deck[key])

    return envelopes, report


def _dict_get_xyz(data: Any, key: str) -> tuple[float, float, float] | None:
    value = data.get(key) if isinstance(data, dict) else getattr(data, key, None)
    if value is None:
        return None
    if isinstance(value, dict):
        return (float(value["x"]), float(value["y"]), float(value["z"]))
    return (float(value.x), float(value.y), float(value.z))


def instrument_envelope_at(
    *,
    instrument_name: str,
    instrument: Any,
    gantry_x: float,
    gantry_y: float,
    gantry_z: float,
) -> CollisionEnvelope | None:
    """Return an instrument envelope at a gantry pose, if geometry exists."""
    geometry = getattr(instrument, "collision_geometry", None)
    if geometry is None:
        return None
    size = _dict_get_xyz(geometry, "size")
    origin_offset = _dict_get_xyz(geometry, "origin_offset") or (0.0, 0.0, 0.0)
    if size is None:
        return None

    point_x = gantry_x + float(instrument.offset_x)
    point_y = gantry_y + float(instrument.offset_y)
    point_z = gantry_z + float(instrument.depth)
    box = CollisionBox.from_origin_size(
        origin_x=point_x + origin_offset[0],
        origin_y=point_y + origin_offset[1],
        origin_z=point_z + origin_offset[2],
        size_x=size[0],
        size_y=size[1],
        size_z=size[2],
    )
    return CollisionEnvelope(key=instrument_name, owner_type="instrument", box=box)


def _resolve_target_info(context: ProtocolContext, position: Any) -> tuple[Coordinate3D, str | None]:
    if isinstance(position, (list, tuple)):
        return (
            Coordinate3D(
                x=float(position[0]),
                y=float(position[1]),
                z=float(position[2]),
            ),
            None,
        )
    if isinstance(position, str) and position in context.positions:
        coords = context.positions[position]
        return (
            Coordinate3D(
                x=float(coords[0]),
                y=float(coords[1]),
                z=float(coords[2]),
            ),
            None,
        )
    if isinstance(position, str):
        return context.deck.resolve(position), position
    raise TypeError(f"Unsupported protocol target position: {position!r}")


def _row_major_key(well_id: str) -> tuple[str, int]:
    return (well_id[0], int(well_id[1:]))


def _wells_for_axis(plate: WellPlate, axis: str) -> list[str]:
    if axis.isalpha():
        wells = [well for well in plate.wells if well[0] == axis.upper()]
    else:
        wells = [well for well in plate.wells if well[1:] == axis]
    return sorted(wells, key=_row_major_key)


def _pose(
    step: ProtocolStep,
    *,
    active_instrument: str,
    target: Coordinate3D,
    target_key: str | None,
    purpose: str = "working_pose",
) -> CollisionPose:
    return CollisionPose(
        step_index=step.index,
        command_name=step.command_name,
        active_instrument=active_instrument,
        target=target,
        target_key=target_key,
        purpose=purpose,
    )


def extract_collision_poses(
    protocol: Protocol,
    context: ProtocolContext,
    *,
    settings: CollisionSettings | None = None,
) -> tuple[list[CollisionPose], CollisionReport]:
    """Extract static validation poses from a loaded protocol."""
    settings = settings or CollisionSettings()
    report = CollisionReport()
    poses: list[CollisionPose] = []

    for step in protocol.steps:
        args = step.args
        command = step.command_name

        try:
            if command == "move":
                target, target_key = _resolve_target_info(context, args["position"])
                poses.append(_pose(
                    step, active_instrument=args["instrument"],
                    target=target, target_key=target_key,
                ))
            elif command in {"aspirate", "blowout", "mix", "pick_up_tip", "drop_tip"}:
                target, target_key = _resolve_target_info(context, args["position"])
                poses.append(_pose(
                    step, active_instrument="pipette",
                    target=target, target_key=target_key,
                ))
            elif command == "transfer":
                source, source_key = _resolve_target_info(context, args["source"])
                dest, dest_key = _resolve_target_info(context, args["destination"])
                poses.append(_pose(
                    step, active_instrument="pipette",
                    target=source, target_key=source_key, purpose="source",
                ))
                poses.append(_pose(
                    step, active_instrument="pipette",
                    target=dest, target_key=dest_key, purpose="destination",
                ))
            elif command == "serial_transfer":
                source, source_key = _resolve_target_info(context, args["source"])
                poses.append(_pose(
                    step, active_instrument="pipette",
                    target=source, target_key=source_key, purpose="source",
                ))
                plate = context.deck[args["plate"]]
                if not isinstance(plate, WellPlate):
                    raise TypeError("serial_transfer plate target must be a WellPlate.")
                for well_id in _wells_for_axis(plate, args["axis"]):
                    target_key = f"{args['plate']}.{well_id}"
                    poses.append(_pose(
                        step,
                        active_instrument="pipette",
                        target=plate.get_well_center(well_id),
                        target_key=target_key,
                        purpose="destination",
                    ))
            elif command == "scan":
                plate = context.deck[args["plate"]]
                if not isinstance(plate, WellPlate):
                    raise TypeError("scan plate target must be a WellPlate.")
                instrument_name = args["instrument"]
                instr = context.board.instruments[instrument_name]
                for well_id in sorted(plate.wells, key=_row_major_key):
                    well = plate.get_well_center(well_id)
                    poses.append(_pose(
                        step,
                        active_instrument=instrument_name,
                        target=Coordinate3D(
                            x=well.x,
                            y=well.y,
                            z=well.z - float(instr.measurement_height),
                        ),
                        target_key=f"{args['plate']}.{well_id}",
                    ))
            elif command == "measure":
                instrument_name = args["instrument"]
                instr = context.board.instruments[instrument_name]
                coord, target_key = _resolve_target_info(context, args["position"])
                poses.append(_pose(
                    step,
                    active_instrument=instrument_name,
                    target=Coordinate3D(
                        x=coord.x,
                        y=coord.y,
                        z=coord.z + float(instr.measurement_height),
                    ),
                    target_key=target_key,
                ))
            elif command in {"home", "pause", "breakpoint"}:
                continue
            else:
                report.add_issue(
                    severity=_issue_severity(settings),
                    code="unsupported_command",
                    message=(
                        f"Command '{command}' has no collision pose extractor; "
                        "mark it collision-noop or add extraction support."
                    ),
                    step_index=step.index,
                    command_name=command,
                )
        except Exception as exc:
            report.add_issue(
                severity=_issue_severity(settings),
                code="pose_extraction_failed",
                message=f"Could not extract collision pose for command '{command}': {exc}",
                step_index=step.index,
                command_name=command,
            )

    return poses, report


def _allowed_labware_keys(
    target_key: str | None,
    labware_envelopes: list[CollisionEnvelope],
) -> set[str]:
    """Return labware envelopes the active instrument may intentionally touch."""
    if target_key is None:
        return set()
    envelope_keys = {envelope.key for envelope in labware_envelopes}
    if target_key in envelope_keys:
        return {target_key}
    matching_prefixes = [
        key for key in envelope_keys
        if target_key.startswith(f"{key}.")
    ]
    if matching_prefixes:
        return {max(matching_prefixes, key=len)}
    return set()


def _gantry_for_pose(board: Board, pose: CollisionPose) -> tuple[float, float, float] | None:
    instrument = board.instruments.get(pose.active_instrument)
    if instrument is None:
        return None
    return (
        pose.target.x - float(instrument.offset_x),
        pose.target.y - float(instrument.offset_y),
        pose.target.z - float(instrument.depth),
    )


def compute_required_safe_z(
    labware_envelopes: list[CollisionEnvelope],
    *,
    clearance_mm: float,
) -> float:
    if not labware_envelopes:
        return clearance_mm
    # CubOS user-facing Z is positive-down, so a smaller Z is higher/safer.
    return min(envelope.box.z_min for envelope in labware_envelopes) - clearance_mm


def validate_collision_safety(
    protocol: Protocol,
    context: ProtocolContext,
    gantry: GantryConfig,
    *,
    settings: CollisionSettings | None = None,
) -> CollisionReport:
    """Validate static collision safety for a loaded protocol setup."""
    settings = settings or CollisionSettings()
    report = CollisionReport()

    labware_envelopes, labware_report = build_labware_envelopes(
        context.deck, settings=settings,
    )
    report.issues.extend(labware_report.issues)

    volume = gantry.working_volume
    for envelope in labware_envelopes:
        if not envelope.box.contained_by(volume):
            report.add_issue(
                severity=_issue_severity(settings),
                code="labware_out_of_volume",
                message=f"Labware envelope '{envelope.key}' is outside the gantry working volume.",
                body_a=envelope.key,
            )

    required_safe_z = compute_required_safe_z(
        labware_envelopes, clearance_mm=settings.clearance_mm,
    )
    if required_safe_z < volume.z_min:
        report.add_issue(
            severity=_issue_severity(settings),
            code="safe_z_out_of_volume",
            message=(
                f"Required safe_z {required_safe_z:.3f} is above "
                f"working volume z_min {volume.z_min:.3f}."
            ),
        )
        report.suggestions.append(
            "Lower labware height, reduce required clearance, or use a gantry with more upward Z clearance."
        )

    poses, pose_report = extract_collision_poses(
        protocol, context, settings=settings,
    )
    report.issues.extend(pose_report.issues)

    missing_instruments_reported: set[str] = set()
    for pose in poses:
        allowed_labware = _allowed_labware_keys(pose.target_key, labware_envelopes)
        gantry_position = _gantry_for_pose(context.board, pose)
        if gantry_position is None:
            report.add_issue(
                severity=_issue_severity(settings),
                code="unknown_instrument",
                message=f"Unknown active instrument '{pose.active_instrument}'.",
                step_index=pose.step_index,
                command_name=pose.command_name,
                active_instrument=pose.active_instrument,
            )
            continue

        gx, gy, gz = gantry_position
        instrument_envelopes: list[CollisionEnvelope] = []
        for name, instrument in context.board.instruments.items():
            envelope = instrument_envelope_at(
                instrument_name=name,
                instrument=instrument,
                gantry_x=gx,
                gantry_y=gy,
                gantry_z=gz,
            )
            if envelope is None:
                if name in missing_instruments_reported:
                    continue
                missing_instruments_reported.add(name)
                report.add_issue(
                    severity=_issue_severity(settings),
                    code="missing_instrument_geometry",
                    message=f"Instrument '{name}' is missing collision_geometry.",
                    step_index=pose.step_index,
                    command_name=pose.command_name,
                    active_instrument=pose.active_instrument,
                    body_a=name,
                )
                continue
            instrument_envelopes.append(envelope)

        for envelope in instrument_envelopes:
            if not envelope.box.contained_by(volume):
                report.add_issue(
                    severity=_issue_severity(settings),
                    code="instrument_out_of_volume",
                    message=(
                        f"Instrument envelope '{envelope.key}' at step {pose.step_index} "
                        "is outside the gantry working volume."
                    ),
                    step_index=pose.step_index,
                    command_name=pose.command_name,
                    active_instrument=pose.active_instrument,
                    body_a=envelope.key,
                )

            for labware in labware_envelopes:
                if envelope.key == pose.active_instrument and labware.key in allowed_labware:
                    continue
                if not envelope.box.overlaps_xy(labware.box):
                    continue
                if envelope.box.z_max <= labware.box.z_min - settings.clearance_mm:
                    continue
                report.add_issue(
                    severity=_issue_severity(settings),
                    code="instrument_labware_collision",
                    message=(
                        f"Instrument '{envelope.key}' overlaps labware '{labware.key}' "
                        f"without {settings.clearance_mm:.3f} mm Z clearance."
                    ),
                    step_index=pose.step_index,
                    command_name=pose.command_name,
                    active_instrument=pose.active_instrument,
                    body_a=envelope.key,
                    body_b=labware.key,
                )
                report.suggestions.append(
                    "Increase safe-Z clearance, move the labware, or adjust the instrument offset/geometry."
                )

    return report
