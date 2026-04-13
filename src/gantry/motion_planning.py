"""Shared motion-planning helpers for user-space gantry motion."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from instruments.base_instrument import BaseInstrument


DEFAULT_FEED_RATE = 2000.0
DEFAULT_USER_MAX_Z_HEIGHT = 0.0
DEFAULT_USER_SAFE_Z_HEIGHT = 10.0


@dataclass(frozen=True)
class MotionPose:
    """Simple immutable XYZ pose in user space."""

    x: float
    y: float
    z: float

    def to_dict(self) -> dict[str, float]:
        return {
            "x": round(self.x, 6),
            "y": round(self.y, 6),
            "z": round(self.z, 6),
        }


@dataclass(frozen=True)
class MotionSegmentPlan:
    """One atomic linear motion segment."""

    phase: str
    start_pose: MotionPose
    end_pose: MotionPose
    feed_rate: float
    distance_mm: float
    real_duration_s: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "start_pose": self.start_pose.to_dict(),
            "end_pose": self.end_pose.to_dict(),
            "feed_rate": self.feed_rate,
            "distance_mm": self.distance_mm,
            "real_duration_s": self.real_duration_s,
        }


def coerce_motion_pose(value: Any) -> MotionPose:
    """Coerce a tuple/dict/object with x/y/z fields into a ``MotionPose``."""
    if isinstance(value, MotionPose):
        return value
    if isinstance(value, tuple):
        x, y, z = value
        return MotionPose(x=float(x), y=float(y), z=float(z))
    if isinstance(value, dict):
        return MotionPose(
            x=float(value["x"]),
            y=float(value["y"]),
            z=float(value["z"]),
        )
    return MotionPose(
        x=float(value.x),
        y=float(value.y),
        z=float(value.z),
    )


def resolve_gantry_target(
    x: float,
    y: float,
    z: float,
    instrument: "BaseInstrument | None" = None,
    *,
    offset_x: float | None = None,
    offset_y: float | None = None,
    depth: float | None = None,
) -> MotionPose:
    """Resolve the gantry-center pose required to place an instrument tip at XYZ."""

    resolved_offset_x = offset_x if offset_x is not None else getattr(instrument, "offset_x", 0.0)
    resolved_offset_y = offset_y if offset_y is not None else getattr(instrument, "offset_y", 0.0)
    resolved_depth = depth if depth is not None else getattr(instrument, "depth", 0.0)
    return MotionPose(
        x=float(x) - float(resolved_offset_x),
        y=float(y) - float(resolved_offset_y),
        z=float(z) - float(resolved_depth),
    )


def resolve_instrument_tip_pose(
    gantry_pose: Any,
    instrument: "BaseInstrument | None" = None,
    *,
    offset_x: float | None = None,
    offset_y: float | None = None,
    depth: float | None = None,
) -> MotionPose:
    """Resolve an instrument tip pose from a gantry-center pose."""

    pose = coerce_motion_pose(gantry_pose)
    resolved_offset_x = offset_x if offset_x is not None else getattr(instrument, "offset_x", 0.0)
    resolved_offset_y = offset_y if offset_y is not None else getattr(instrument, "offset_y", 0.0)
    resolved_depth = depth if depth is not None else getattr(instrument, "depth", 0.0)
    return MotionPose(
        x=pose.x + float(resolved_offset_x),
        y=pose.y + float(resolved_offset_y),
        z=pose.z + float(resolved_depth),
    )


def _segment_distance(start_pose: MotionPose, end_pose: MotionPose) -> float:
    dx = end_pose.x - start_pose.x
    dy = end_pose.y - start_pose.y
    dz = end_pose.z - start_pose.z
    return sqrt(dx * dx + dy * dy + dz * dz)


def _segment_duration(distance_mm: float, feed_rate: float) -> float:
    if distance_mm <= 0:
        return 0.0
    if feed_rate <= 0:
        raise ValueError("feed_rate must be positive.")
    return distance_mm / (feed_rate / 60.0)


def _build_segment(
    phase: str,
    start_pose: MotionPose,
    end_pose: MotionPose,
    feed_rate: float,
) -> MotionSegmentPlan | None:
    if start_pose == end_pose:
        return None
    distance_mm = _segment_distance(start_pose, end_pose)
    return MotionSegmentPlan(
        phase=phase,
        start_pose=start_pose,
        end_pose=end_pose,
        feed_rate=feed_rate,
        distance_mm=distance_mm,
        real_duration_s=_segment_duration(distance_mm, feed_rate),
    )


def _should_move_to_safe_position_first(
    current_pose: MotionPose,
    destination_pose: MotionPose,
    *,
    safe_z_height: float,
    max_z_height: float,
) -> bool:
    """Mirror the GRBL driver's safe-Z branching in user space."""

    if current_pose.z <= max_z_height or current_pose.z <= safe_z_height:
        return False

    if current_pose.x != destination_pose.x or current_pose.y != destination_pose.y:
        return True

    return False


def _vertical_phase(start_z: float, end_z: float) -> str:
    if end_z > start_z:
        return "descend_z"
    return "ascend_z"


def plan_safe_move_segments(
    current_pose: Any,
    target_pose: Any,
    *,
    safe_z_height: float = DEFAULT_USER_SAFE_Z_HEIGHT,
    max_z_height: float = DEFAULT_USER_MAX_Z_HEIGHT,
    feed_rate: float = DEFAULT_FEED_RATE,
) -> list[MotionSegmentPlan]:
    """Plan atomic linear motion segments in user space."""

    resolved_current = coerce_motion_pose(current_pose)
    resolved_target = coerce_motion_pose(target_pose)
    segments: list[MotionSegmentPlan] = []
    working_pose = resolved_current

    move_to_safe_first = _should_move_to_safe_position_first(
        working_pose,
        resolved_target,
        safe_z_height=safe_z_height,
        max_z_height=max_z_height,
    )

    if move_to_safe_first and working_pose.z != max_z_height:
        lifted_pose = MotionPose(x=working_pose.x, y=working_pose.y, z=max_z_height)
        lift_segment = _build_segment(
            "lift_to_safe_z",
            working_pose,
            lifted_pose,
            feed_rate,
        )
        if lift_segment is not None:
            segments.append(lift_segment)
        working_pose = lifted_pose

    if working_pose.z <= safe_z_height or move_to_safe_first:
        if working_pose.x != resolved_target.x or working_pose.y != resolved_target.y:
            traversed_pose = MotionPose(
                x=resolved_target.x,
                y=resolved_target.y,
                z=working_pose.z,
            )
            if working_pose.x != resolved_target.x and working_pose.y != resolved_target.y:
                traverse_phase = "traverse_xy"
            elif working_pose.x != resolved_target.x:
                traverse_phase = "move_x"
            else:
                traverse_phase = "move_y"
            traverse_segment = _build_segment(
                traverse_phase,
                working_pose,
                traversed_pose,
                feed_rate,
            )
            if traverse_segment is not None:
                segments.append(traverse_segment)
            working_pose = traversed_pose

        if working_pose.z != resolved_target.z:
            vertical_segment = _build_segment(
                _vertical_phase(working_pose.z, resolved_target.z),
                working_pose,
                resolved_target,
                feed_rate,
            )
            if vertical_segment is not None:
                segments.append(vertical_segment)
    else:
        if working_pose.x != resolved_target.x:
            x_pose = MotionPose(x=resolved_target.x, y=working_pose.y, z=working_pose.z)
            x_segment = _build_segment("move_x", working_pose, x_pose, feed_rate)
            if x_segment is not None:
                segments.append(x_segment)
            working_pose = x_pose

        if working_pose.y != resolved_target.y:
            y_pose = MotionPose(x=working_pose.x, y=resolved_target.y, z=working_pose.z)
            y_segment = _build_segment("move_y", working_pose, y_pose, feed_rate)
            if y_segment is not None:
                segments.append(y_segment)
            working_pose = y_pose

        if working_pose.z != resolved_target.z:
            vertical_segment = _build_segment(
                _vertical_phase(working_pose.z, resolved_target.z),
                working_pose,
                resolved_target,
                feed_rate,
            )
            if vertical_segment is not None:
                segments.append(vertical_segment)

    return segments
