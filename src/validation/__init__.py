"""Validation module for protocol setup."""

from .bounds import validate_deck_positions, validate_gantry_positions
from .collision import (
    CollisionBox,
    CollisionEnvelope,
    CollisionPose,
    CollisionReport,
    CollisionSettings,
    CollisionValidationMode,
    build_labware_envelopes,
    compute_required_safe_z,
    extract_collision_poses,
    validate_collision_safety,
)
from .errors import (
    BoundsViolation,
    CollisionIssue,
    CollisionValidationError,
    SetupValidationError,
)

__all__ = [
    "BoundsViolation",
    "CollisionBox",
    "CollisionEnvelope",
    "CollisionIssue",
    "CollisionPose",
    "CollisionReport",
    "CollisionSettings",
    "CollisionValidationError",
    "CollisionValidationMode",
    "SetupValidationError",
    "build_labware_envelopes",
    "compute_required_safe_z",
    "extract_collision_poses",
    "validate_deck_positions",
    "validate_gantry_positions",
    "validate_collision_safety",
]
