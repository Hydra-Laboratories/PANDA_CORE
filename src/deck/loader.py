"""Load deck YAML into a Deck containing configured labware fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Type

import yaml
from pydantic import BaseModel, ValidationError

from .deck import Deck
from .labware import Coordinate3D, Labware
from .labware.holder import LabwareSlot, TipDisposal, TipHolder, VialHolder, WellPlateHolder
from .labware.tip_rack import TipRack
from .labware.vial import Vial
from .labware.well_plate import WellPlate
from .errors import DeckLoaderError
from .yaml_schema import (
    DeckYamlSchema,
    NestedVialYamlEntry,
    NestedWellPlateYamlEntry,
    TipDisposalYamlEntry,
    TipHolderYamlEntry,
    TipRackYamlEntry,
    VialHolderYamlEntry,
    VialYamlEntry,
    WellPlateHolderYamlEntry,
    WellPlateYamlEntry,
    _BaseHolderYamlEntry,
    _YamlHolderSlot,
    _YamlPoint3D,
)


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


def _point_to_coord(p: _YamlPoint3D, z_value: float | None = None) -> Coordinate3D:
    """Convert schema point (x, y, z) to Coordinate3D."""
    z = p.z if z_value is None else z_value
    if z is None:
        raise ValueError("Missing z value for coordinate conversion.")
    return Coordinate3D(x=p.x, y=p.y, z=z)


def _resolve_user_z(
    explicit_z: float | None,
    *,
    height: float | None,
    total_z_height: float | None,
    context: str,
    default_z: float | None = None,
) -> float:
    """Resolve a user-space Z using explicit z or total_z_height - height."""
    if height is not None:
        if total_z_height is None:
            raise ValueError(
                f"{context}: total_z_height is required when labware `height` is provided."
            )
        return total_z_height - height

    if explicit_z is None:
        if default_z is not None:
            return default_z
        raise ValueError(
            f"{context}: z is required when labware `height` is not provided."
        )
    return explicit_z


def _entry_kwargs_for_model(entry: BaseModel, model_class: Type[BaseModel]) -> Dict[str, Any]:
    """
    Build constructor kwargs from entry by keeping only keys that exist on the target model.
    """
    allowed = set(model_class.model_fields.keys())
    raw = entry.model_dump()
    return {k: v for k, v in raw.items() if k in allowed}


def _slot_to_model(slot_entry: _YamlHolderSlot, *, default_z: float) -> LabwareSlot:
    """Convert a YAML holder slot definition into a LabwareSlot."""
    resolved_z = slot_entry.location.z if slot_entry.location.z is not None else default_z
    return LabwareSlot(
        location=_point_to_coord(slot_entry.location, z_value=resolved_z),
        supported_labware_types=slot_entry.supported_labware_types,
        description=slot_entry.description,
    )


def _build_holder_slots(
    slots: Dict[str, _YamlHolderSlot],
    *,
    default_z: float,
) -> Dict[str, LabwareSlot]:
    return {
        slot_name: _slot_to_model(slot_entry, default_z=default_z)
        for slot_name, slot_entry in slots.items()
    }


def _build_tip_rack(
    entry: TipRackYamlEntry,
    total_z_height: float | None,
) -> TipRack:
    del total_z_height
    kwargs = _entry_kwargs_for_model(entry, TipRack)
    kwargs["tips"] = {
        tip_id: _point_to_coord(point, z_value=point.z if point.z is not None else entry.z_pickup)
        for tip_id, point in entry.tips.items()
    }
    return TipRack(**kwargs)


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


def _resolve_plate_orientation(entry: Any) -> _PlateOrientation:
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


def _derive_wells_from_calibration(
    entry: Any,
    resolved_z: float,
) -> Dict[str, Coordinate3D]:
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
                z=round(resolved_z, rounding),
            )

    return wells


def _build_well_plate(
    entry: WellPlateYamlEntry,
    total_z_height: float | None,
) -> WellPlate:
    resolved_z = _resolve_user_z(
        entry.a1_point.z,
        height=entry.height,
        total_z_height=total_z_height,
        context=f"well_plate '{entry.name}'",
    )
    kwargs = _entry_kwargs_for_model(entry, WellPlate)
    kwargs["wells"] = _derive_wells_from_calibration(entry, resolved_z=resolved_z)
    return WellPlate(**kwargs)


def _build_vial(
    entry: VialYamlEntry,
    total_z_height: float | None,
) -> Vial:
    resolved_z = _resolve_user_z(
        entry.location.z,
        height=entry.height,
        total_z_height=total_z_height,
        context=f"vial '{entry.name}'",
    )
    kwargs = _entry_kwargs_for_model(entry, Vial)
    kwargs["location"] = _point_to_coord(entry.location, z_value=resolved_z)
    return Vial(**kwargs)


def _build_holder(
    entry: _BaseHolderYamlEntry,
    total_z_height: float | None,
    *,
    model_class: Type[Labware],
) -> Labware:
    resolved_z = _resolve_user_z(
        entry.location.z,
        height=entry.height,
        total_z_height=total_z_height,
        context=f"{entry.type} '{entry.name}'",
    )
    kwargs = _entry_kwargs_for_model(entry, model_class)
    kwargs["location"] = _point_to_coord(entry.location, z_value=resolved_z)
    kwargs["slots"] = _build_holder_slots(entry.slots, default_z=resolved_z)
    holder = model_class(**kwargs)

    seat_height = getattr(holder, "labware_seat_height_from_bottom_mm", None)
    contained_labware: Dict[str, Labware] = {}
    if seat_height is not None:
        contained_z = holder.location.z + seat_height
        if isinstance(entry, VialHolderYamlEntry):
            contained_labware = {
                vial_key: _build_nested_vial(
                    vial_key,
                    vial_entry,
                    resolved_z=contained_z,
                )
                for vial_key, vial_entry in entry.vials.items()
            }
        elif isinstance(entry, WellPlateHolderYamlEntry) and entry.well_plate is not None:
            contained_labware["plate"] = _build_nested_well_plate(
                "plate",
                entry.well_plate,
                resolved_z=contained_z,
            )

    holder.contained_labware = contained_labware
    return holder


def _build_nested_vial(
    vial_key: str,
    entry: NestedVialYamlEntry,
    *,
    resolved_z: float,
) -> Vial:
    return Vial(
        name=entry.name or vial_key,
        model_name=entry.model_name,
        height_mm=entry.height_mm,
        diameter_mm=entry.diameter_mm,
        location=Coordinate3D(
            x=entry.location.x,
            y=entry.location.y,
            z=resolved_z,
        ),
        capacity_ul=entry.capacity_ul,
        working_volume_ul=entry.working_volume_ul,
    )


def _build_nested_well_plate(
    plate_key: str,
    entry: NestedWellPlateYamlEntry,
    *,
    resolved_z: float,
) -> WellPlate:
    return WellPlate(
        name=entry.name or plate_key,
        model_name=entry.model_name,
        length_mm=entry.length_mm,
        width_mm=entry.width_mm,
        height_mm=entry.height_mm,
        rows=entry.rows,
        columns=entry.columns,
        wells=_derive_wells_from_calibration(entry, resolved_z=resolved_z),
        capacity_ul=entry.capacity_ul,
        working_volume_ul=entry.working_volume_ul,
    )


def _build_deck_from_raw(raw: dict[str, Any], *, total_z_height: float | None = None) -> Deck:
    schema = DeckYamlSchema.model_validate(raw)
    labware: Dict[str, Labware] = {}
    for name, entry in schema.labware.items():
        if isinstance(entry, WellPlateYamlEntry):
            labware[name] = _build_well_plate(entry, total_z_height=total_z_height)
        elif isinstance(entry, VialYamlEntry):
            labware[name] = _build_vial(entry, total_z_height=total_z_height)
        elif isinstance(entry, TipRackYamlEntry):
            labware[name] = _build_tip_rack(entry, total_z_height=total_z_height)
        elif isinstance(entry, TipHolderYamlEntry):
            labware[name] = _build_holder(
                entry,
                total_z_height=total_z_height,
                model_class=TipHolder,
            )
        elif isinstance(entry, TipDisposalYamlEntry):
            labware[name] = _build_holder(
                entry,
                total_z_height=total_z_height,
                model_class=TipDisposal,
            )
        elif isinstance(entry, WellPlateHolderYamlEntry):
            labware[name] = _build_holder(
                entry,
                total_z_height=total_z_height,
                model_class=WellPlateHolder,
            )
        elif isinstance(entry, VialHolderYamlEntry):
            labware[name] = _build_holder(
                entry,
                total_z_height=total_z_height,
                model_class=VialHolder,
            )
        else:
            raise TypeError(f"Unsupported deck labware entry type: {type(entry).__name__}")
    return Deck(labware)


def load_deck_from_yaml(
    path: str | Path,
    total_z_height: float | None = None,
) -> Deck:
    """
    Load a deck YAML file and return a Deck containing all labware.
    """
    resolved_path = Path(path)
    with resolved_path.open() as handle:
        raw = yaml.safe_load(handle)
    if raw is None:
        raw = {}
    return _build_deck_from_raw(raw, total_z_height=total_z_height)


def load_deck_from_yaml_safe(
    path: str | Path,
    total_z_height: float | None = None,
) -> Deck:
    """
    Load deck YAML with user-friendly exception formatting.

    Raises:
        DeckLoaderError: concise, actionable message intended for CLI/UX output.
    """
    resolved_path = Path(path)
    try:
        return load_deck_from_yaml(resolved_path, total_z_height=total_z_height)
    except Exception as exc:
        raise DeckLoaderError(_format_loader_exception(resolved_path, exc)) from exc
