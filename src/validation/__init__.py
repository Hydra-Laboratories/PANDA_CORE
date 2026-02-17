"""Validation module for protocol setup."""

from .bounds import validate_deck_positions, validate_gantry_positions
from .errors import BoundsViolation, SetupValidationError

__all__ = [
    "BoundsViolation",
    "SetupValidationError",
    "validate_deck_positions",
    "validate_gantry_positions",
]
