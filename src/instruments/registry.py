"""Instrument registry: single source of truth for supported types and vendors."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Dict, List, Type

import yaml

from instruments.base_instrument import BaseInstrument

_REGISTRY_PATH = Path(__file__).parent / "registry.yaml"

_cache: Dict[str, Any] | None = None


def load_registry() -> Dict[str, Any]:
    """Load and cache the instrument registry from registry.yaml."""
    global _cache
    if _cache is None:
        with _REGISTRY_PATH.open() as f:
            _cache = yaml.safe_load(f)
    return _cache


def get_supported_types() -> List[str]:
    """Return a sorted list of all supported instrument type keys."""
    return sorted(load_registry()["instruments"].keys())


def get_supported_vendors(instrument_type: str) -> List[str]:
    """Return the list of allowed vendors for an instrument type.

    Raises:
        ValueError: If the instrument type is not in the registry.
    """
    instruments = load_registry()["instruments"]
    if instrument_type not in instruments:
        raise ValueError(
            f"Unknown instrument type '{instrument_type}'. "
            f"Supported types: {sorted(instruments.keys())}"
        )
    return instruments[instrument_type]["vendors"]


def get_instrument_class(instrument_type: str) -> Type[BaseInstrument]:
    """Dynamically import and return the driver class for an instrument type.

    Raises:
        ValueError: If the instrument type is not in the registry.
    """
    instruments = load_registry()["instruments"]
    if instrument_type not in instruments:
        raise ValueError(
            f"Unknown instrument type '{instrument_type}'. "
            f"Supported types: {sorted(instruments.keys())}"
        )
    entry = instruments[instrument_type]
    module = importlib.import_module(entry["module"])
    return getattr(module, entry["class_name"])


def validate_instrument(instrument_type: str, vendor: str) -> None:
    """Validate that a type+vendor combination is supported.

    Raises:
        ValueError: If the type is unknown or the vendor is not allowed.
    """
    allowed_vendors = get_supported_vendors(instrument_type)
    if vendor not in allowed_vendors:
        raise ValueError(
            f"'{vendor}' is not a supported vendor for '{instrument_type}'. "
            f"Allowed vendors: {allowed_vendors}"
        )
