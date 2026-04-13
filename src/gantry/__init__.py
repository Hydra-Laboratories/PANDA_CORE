"""Gantry hardware and configuration module."""

from .errors import GantryLoaderError
from .gantry import Gantry
from .gantry_config import GantryConfig, HomingStrategy, WorkingVolume
from .loader import load_gantry_from_yaml, load_gantry_from_yaml_safe
from .motion_planning import (
    DEFAULT_FEED_RATE,
    DEFAULT_USER_MAX_Z_HEIGHT,
    DEFAULT_USER_SAFE_Z_HEIGHT,
    MotionPose,
    MotionSegmentPlan,
    coerce_motion_pose,
    plan_safe_move_segments,
    resolve_gantry_target,
    resolve_instrument_tip_pose,
)

__all__ = [
    "DEFAULT_FEED_RATE",
    "DEFAULT_USER_MAX_Z_HEIGHT",
    "DEFAULT_USER_SAFE_Z_HEIGHT",
    "Gantry",
    "GantryConfig",
    "GantryLoaderError",
    "HomingStrategy",
    "MotionPose",
    "MotionSegmentPlan",
    "WorkingVolume",
    "coerce_motion_pose",
    "load_gantry_from_yaml",
    "load_gantry_from_yaml_safe",
    "plan_safe_move_segments",
    "resolve_gantry_target",
    "resolve_instrument_tip_pose",
]
