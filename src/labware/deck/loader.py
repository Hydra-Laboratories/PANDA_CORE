"""Load deck YAML into a mapping of name -> Labware (WellPlate or Vial)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Type, Union

import yaml
from pydantic import BaseModel, ValidationError

from ..labware import Coordinate3D
from ..vial import Vial
from ..well_plate import WellPlate
from .errors import DeckLoaderError
from .schema import DeckSchema, VialEntry, WellPlateEntry, _Point3D


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


def _point_to_coord(p: _Point3D) -> Coordinate3D:
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


def _derive_wells_from_calibration(entry: WellPlateEntry) -> Dict[str, Coordinate3D]:
    """Build well ID -> Coordinate3D from calibration A1/A2 and offsets."""
    a1 = entry.a1_point
    a2 = entry.calibration.a2
    rounding = 3
    wells: Dict[str, Coordinate3D] = {}
    row_labels = _row_labels(entry.rows)
    column_indices = list(range(1, entry.columns + 1))

    same_x = abs(a1.x - a2.x) < 1e-9
    same_y = abs(a1.y - a2.y) < 1e-9

    if same_y:
        # Columns along X: A2 is (a1.x + col_step, a1.y)
        col_step = a2.x - a1.x
        # Ensure calibration A2 corresponds to physical well A2 (one adjacent column step).
        if abs(col_step - entry.x_offset_mm) > 1e-9:
            raise ValueError(
                "Calibration A2 must match one adjacent column step from A1 (delta x must equal x_offset_mm)."
            )
        row_step = entry.y_offset_mm
        for row_idx, row_label in enumerate(row_labels):
            for col_idx, col_num in enumerate(column_indices):
                x = a1.x + col_step * col_idx
                y = a1.y + row_step * row_idx
                wells[f"{row_label}{col_num}"] = Coordinate3D(
                    x=round(x, rounding),
                    y=round(y, rounding),
                    z=round(a1.z, rounding),
                )
    elif same_x:
        # Columns along Y: A2 is (a1.x, a1.y + col_step)
        col_step = a2.y - a1.y
        # Ensure calibration A2 corresponds to physical well A2 (one adjacent column step).
        if abs(col_step - entry.y_offset_mm) > 1e-9:
            raise ValueError(
                "Calibration A2 must match one adjacent column step from A1 (delta y must equal y_offset_mm)."
            )
        row_step = entry.x_offset_mm
        for row_idx, row_label in enumerate(row_labels):
            for col_idx, col_num in enumerate(column_indices):
                x = a1.x + row_step * row_idx
                y = a1.y + col_step * col_idx
                wells[f"{row_label}{col_num}"] = Coordinate3D(
                    x=round(x, rounding),
                    y=round(y, rounding),
                    z=round(a1.z, rounding),
                )
    else:
        raise ValueError("Calibration must be axis-aligned (same x or same y).")

    return wells


def _build_well_plate(entry: WellPlateEntry) -> WellPlate:
    kwargs = _entry_kwargs_for_model(entry, WellPlate)
    kwargs["wells"] = _derive_wells_from_calibration(entry)
    return WellPlate(**kwargs)


def _build_vial(entry: VialEntry) -> Vial:
    kwargs = _entry_kwargs_for_model(entry, Vial)
    kwargs["location"] = _point_to_coord(entry.location)
    return Vial(**kwargs)


def load_labware_from_deck_yaml(path: str | Path) -> Dict[str, Union[WellPlate, Vial]]:
    """
    Load a deck YAML file and return a mapping from labware name (key in YAML) to Labware.
    """
    path = Path(path)
    with path.open() as f:
        raw = yaml.safe_load(f)
    if raw is None:
        raw = {}
    deck = DeckSchema.model_validate(raw)
    result: Dict[str, Union[WellPlate, Vial]] = {}
    for name, entry in deck.labware.items():
        if isinstance(entry, WellPlateEntry):
            result[name] = _build_well_plate(entry)
        else:
            result[name] = _build_vial(entry)
    return result


def load_labware_from_deck_yaml_safe(path: str | Path) -> Dict[str, Union[WellPlate, Vial]]:
    """
    Load deck YAML with user-friendly exception formatting.

    Raises:
        DeckLoaderError: concise, actionable message intended for CLI/UX output.
    """
    resolved_path = Path(path)
    try:
        return load_labware_from_deck_yaml(resolved_path)
    except Exception as exc:
        raise DeckLoaderError(_format_loader_exception(resolved_path, exc)) from exc

