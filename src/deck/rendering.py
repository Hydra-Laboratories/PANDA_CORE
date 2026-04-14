"""Public helpers for deck-definition resolution and render metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .labware.definitions import registry as definition_registry
from .loader import _resolve_load_names, _resolve_plate_orientation
from .yaml_schema import DeckYamlSchema, NestedWellPlateYamlEntry, TipRackYamlEntry, WellPlateYamlEntry


@dataclass(frozen=True)
class PlateOrientation:
    """Public, serializable view of plate/rack orientation deltas."""

    col_delta_x: float
    col_delta_y: float
    row_delta_x: float
    row_delta_y: float


def load_deck_yaml_with_definitions(path: str | Path) -> dict[str, Any]:
    """Load a deck YAML file and expand any ``load_name`` definitions."""

    raw = yaml.safe_load(Path(path).read_text()) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Expected deck YAML mapping at {path}, got {type(raw).__name__}.")
    return _resolve_load_names(raw)


def load_deck_render_schema(path: str | Path) -> DeckYamlSchema:
    """Load and validate a deck YAML after resolving ``load_name`` definitions."""

    return DeckYamlSchema.model_validate(load_deck_yaml_with_definitions(path))


def resolve_plate_orientation(
    entry: WellPlateYamlEntry | NestedWellPlateYamlEntry | TipRackYamlEntry,
) -> PlateOrientation:
    """Return the public orientation vectors for a plate-like deck entry."""

    orientation = _resolve_plate_orientation(entry)
    return PlateOrientation(
        col_delta_x=orientation.col_delta_x,
        col_delta_y=orientation.col_delta_y,
        row_delta_x=orientation.row_delta_x,
        row_delta_y=orientation.row_delta_y,
    )


def resolve_definition_asset_path(load_name: str) -> Path | None:
    """Return the preferred GLB asset path for a labware definition, if any."""

    entry = definition_registry.load_registry().get("labware", {}).get(load_name)
    if entry is None:
        raise ValueError(
            f"Unknown labware definition '{load_name}'. "
            f"Supported definitions: {definition_registry.get_supported_definitions()}"
        )
    config_dir = Path(definition_registry.__file__).resolve().parent / Path(entry["config"]).parent
    glb_candidates = sorted(config_dir.glob("*.glb"))
    if not glb_candidates:
        return None
    preferred = [path for path in glb_candidates if "-key" not in path.stem.lower()]
    return (preferred or glb_candidates)[0]
