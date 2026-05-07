"""Gantry hardware and configuration module."""

from .errors import GantryLoaderError
from .gantry import Gantry
from .gantry_config import (
    GantryConfig,
    GantryType,
    HomingStrategy,
    WorkingVolume,
)
from .loader import load_gantry_from_yaml, load_gantry_from_yaml_safe
from .machine_geometry import (
    FixedStructureBox,
    fixed_structures_for_gantry,
    fixed_structures_for_gantry_type,
)

__all__ = [
    "Gantry",
    "GantryConfig",
    "GantryLoaderError",
    "GantryType",
    "FixedStructureBox",
    "HomingStrategy",
    "WorkingVolume",
    "fixed_structures_for_gantry",
    "fixed_structures_for_gantry_type",
    "load_gantry_from_yaml",
    "load_gantry_from_yaml_safe",
]
