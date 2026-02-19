"""Load deck YAML into a Deck containing Labware (WellPlate or Vial)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Type, Union

import yaml
from pydantic import BaseModel, ValidationError

from .deck import Deck
from .labware import Coordinate3D
from .labware.vial import Vial
from .labware.well_plate import WellPlate
from .errors import DeckLoaderError
from .yaml_schema import DeckYamlSchema, VialYamlEntry, WellPlateYamlEntry, _YamlPoint3D


def _format_loader_exception(path: Path, error: Exception) -> str:
    """Return a concise, actionable error message with fix guidance."""
    detail = str(error)

    if isinstance(error, ValidationError):
        first_error = error.errors()[0] if error.errors() else {}
        detail = first_error.get("msg", detail)
        error_type = first_error.get("type", "")
        location = ".".join(str(part) for part in first_error.get("loc", []))

        if "axis-aligned" in detail or "diagonal orientation is invalid" in detail:
            guidance = (
                "Set `calibration.a1` and `calibration.a2` so A2 shares either "
                "the same x or the same y as A1 (not both different)."
            )
        elif error_type == "missing" or "Field required" in detail:
            guidance = "Add the missing required YAML field shown in the error location."
        elif "extra_forbidden" in error_type or "Extra inputs are not permitted" in detail:
            guidance = "Remove unknown YAML fields; only schema-defined fields are allowed."
        elif "model_type" in error_type:
            guidance = "Check YAML nesting/indentation and field types."
        else:
            guidance = "Review the YAML values against the deck schema and correct invalid entries."

        prefix = f" at `{location}`" if location else ""
        return f"❌ Deck YAML error{prefix}: {detail}\nHow to fix: {guidance}"

    if isinstance(error, yaml.YAMLError):
        return (
            f"❌ Deck YAML parse error in `{path}`.\n"
            "How to fix: Check YAML indentation, colons, and list/dict structure."
        )

    return (
        f"❌ Deck loader error in `{path}`: {detail}\n"
        "How to fix: Verify the file path and deck YAML contents."
    )


def _point_to_coord(p: _YamlPoint3D) -> Coordinate3D:
    """Convert schema point (x, y, z) to Coordinate3D."""
    return Coordinate3D(x=p.x, y=p.y, z=p.z)


def _entry_kwargs_for_model(entry: BaseModel, model_class: Type[BaseModel]) -> Dict[str, Any]:
    """
    Build constructor kwargs from entry by keeping only keys that exist on the target model.
    """
    allowed = set(model_class.model_fields.keys())
    raw = entry.model_dump()
    return {k: v for k, v in raw.items() if k in allowed}


def _row_labels(rows: int) -> list[str]:
    if rows <= 0:
        raise ValueError("rows must be positive for row label generation.")
    labels: list[str] = []
    for index in range(rows):
        label = ""
        value = index + 1
        while value > 0:
            value, remainder = divmod(value - 1, 26)
            label = chr(65 + remainder) + label
        labels.append(label)
    return labels


@dataclass(frozen=True)
class _PlateOrientation:
    """Resolved per-step deltas for column and row traversal.

    Separating orientation resolution from well generation makes the
    coordinate math easier to follow and test independently.
    """
    col_delta_x: float
    col_delta_y: float
    row_delta_x: float
    row_delta_y: float


def _resolve_plate_orientation(entry: WellPlateYamlEntry) -> _PlateOrientation:
    """Determine column/row axis mapping from the two-point calibration.

    Returns a ``_PlateOrientation`` whose deltas are used to compute each
    well position relative to A1 in ``_derive_wells_from_calibration``.

    Raises ``ValueError`` when the A2 calibration step does not match
    the declared offset or the points are not axis-aligned.
    """
    a1 = entry.a1_point
    a2 = entry.calibration.a2

    same_x = abs(a1.x - a2.x) < 1e-9
    same_y = abs(a1.y - a2.y) < 1e-9

    if same_y:
        col_step = a2.x - a1.x
        if abs(col_step - entry.x_offset_mm) > 1e-9:
            raise ValueError(
                "Calibration A2 must match one adjacent column step from A1 "
                "(delta x must equal x_offset_mm)."
            )
        return _PlateOrientation(
            col_delta_x=col_step, col_delta_y=0.0,
            row_delta_x=0.0, row_delta_y=entry.y_offset_mm,
        )

    if same_x:
        col_step = a2.y - a1.y
        if abs(col_step - entry.y_offset_mm) > 1e-9:
            raise ValueError(
                "Calibration A2 must match one adjacent column step from A1 "
                "(delta y must equal y_offset_mm)."
            )
        return _PlateOrientation(
            col_delta_x=0.0, col_delta_y=col_step,
            row_delta_x=entry.x_offset_mm, row_delta_y=0.0,
        )

    raise ValueError("Calibration must be axis-aligned (same x or same y).")


def _derive_wells_from_calibration(entry: WellPlateYamlEntry) -> Dict[str, Coordinate3D]:
    """Build well ID -> Coordinate3D from calibration A1/A2 and offsets."""
    a1 = entry.a1_point
    orientation = _resolve_plate_orientation(entry)
    rounding = 3
    wells: Dict[str, Coordinate3D] = {}

    for row_idx, row_label in enumerate(_row_labels(entry.rows)):
        for col_idx, col_num in enumerate(range(1, entry.columns + 1)):
            x = a1.x + orientation.col_delta_x * col_idx + orientation.row_delta_x * row_idx
            y = a1.y + orientation.col_delta_y * col_idx + orientation.row_delta_y * row_idx
            wells[f"{row_label}{col_num}"] = Coordinate3D(
                x=round(x, rounding),
                y=round(y, rounding),
                z=round(a1.z, rounding),
            )

    return wells


def _build_well_plate(entry: WellPlateYamlEntry) -> WellPlate:
    kwargs = _entry_kwargs_for_model(entry, WellPlate)
    kwargs["wells"] = _derive_wells_from_calibration(entry)
    return WellPlate(**kwargs)


def _build_vial(entry: VialYamlEntry) -> Vial:
    kwargs = _entry_kwargs_for_model(entry, Vial)
    kwargs["location"] = _point_to_coord(entry.location)
    return Vial(**kwargs)


def load_deck_from_yaml(path: str | Path) -> Deck:
    """
    Load a deck YAML file and return a Deck containing all labware.
    """
    path = Path(path)
    with path.open() as f:
        raw = yaml.safe_load(f)
    if raw is None:
        raw = {}
    schema = DeckYamlSchema.model_validate(raw)
    labware: Dict[str, Union[WellPlate, Vial]] = {}
    for name, entry in schema.labware.items():
        if isinstance(entry, WellPlateYamlEntry):
            labware[name] = _build_well_plate(entry)
        else:
            labware[name] = _build_vial(entry)
    return Deck(labware)


def load_deck_from_yaml_safe(path: str | Path) -> Deck:
    """
    Load deck YAML with user-friendly exception formatting.

    Raises:
        DeckLoaderError: concise, actionable message intended for CLI/UX output.
    """
    resolved_path = Path(path)
    try:
        return load_deck_from_yaml(resolved_path)
    except Exception as exc:
        raise DeckLoaderError(_format_loader_exception(resolved_path, exc)) from exc
