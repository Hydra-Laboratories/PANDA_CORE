"""Load deck YAML into a Deck containing configured labware fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Type

import yaml
from pydantic import BaseModel, ValidationError

from .deck import Deck
from .labware import Coordinate3D, Labware
from .labware.definitions.registry import (
    get_supported_definitions,
    load_definition_config,
)
from .labware.holder import LabwareSlot
from .labware.tip_disposal import TipDisposal
from .labware.tip_rack import TipRack
from .labware.wall import Wall
from .labware.vial import Vial
from .labware.vial_holder import VialHolder
from .labware.well_plate import WellPlate
from .labware.well_plate_holder import WellPlateHolder
from .errors import DeckLoaderError
from .yaml_schema import (
    DeckYamlSchema,
    TipDisposalYamlEntry,
    TipRackYamlEntry,
    VialHolderYamlEntry,
    WallYamlEntry,
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

    ``exclude_none=True`` drops optional YAML fields that weren't set, so the
    target class's defaults take effect instead of being overridden with
    ``None`` (which would fail pydantic validation for required dimensions).
    """
    allowed = set(model_class.model_fields.keys())
    raw = entry.model_dump(exclude_none=True)
    return {k: v for k, v in raw.items() if k in allowed}


def _resolve_load_names(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Expand ``load_name:`` references against the labware definitions registry.

    For each entry in ``raw["labware"]`` that has a ``load_name`` field, load
    the corresponding definition config from ``labware/definitions/``, merge
    the user's fields on top (user wins), drop the ``load_name`` key, and
    default the labware ``name`` to the deck key if the user didn't override it.

    Entries without ``load_name`` are passed through untouched, so existing
    deck YAMLs keep working unchanged.
    """
    labware = raw.get("labware")
    if not isinstance(labware, dict):
        return raw

    # Cache the supported-definitions list once per call; get_supported_
    # definitions re-reads registry.yaml from disk each invocation.
    supported = get_supported_definitions()

    expanded: Dict[str, Dict[str, Any]] = {}
    for deck_key, entry in labware.items():
        if not isinstance(entry, dict) or "load_name" not in entry:
            expanded[deck_key] = entry
            continue

        load_name = entry["load_name"]
        if load_name not in supported:
            raise DeckLoaderError(
                f"❌ Unknown `load_name: '{load_name}'` in deck entry "
                f"'{deck_key}'.\n"
                f"How to fix: use one of {supported}, or add a new folder + "
                f"registry entry under `src/deck/labware/definitions/`."
            )
        # Malformed definition configs / missing files propagate with their
        # native message; they indicate a definition-package bug, not a
        # user-facing "unknown name" situation.
        base = load_definition_config(load_name)

        # Shallow merge: user fields override config fields. Drop load_name.
        merged: Dict[str, Any] = dict(base)
        for key, value in entry.items():
            if key == "load_name":
                continue
            merged[key] = value

        # Default the labware `name` to the deck key unless the user set it.
        if "name" not in entry:
            merged["name"] = deck_key

        expanded[deck_key] = merged

    new_raw = dict(raw)
    new_raw["labware"] = expanded
    return new_raw


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
    # Derive every tip pickup position from the two-point calibration and
    # pitch offsets, mirroring how well plates derive their wells.
    tips = _derive_wells_from_calibration(entry, resolved_z=entry.z_pickup)

    # Anchor location: use the explicit entry.location if given, otherwise
    # default to the A1 tip so the holder's bounding-box/geometry still works.
    if entry.location is not None:
        loc = _point_to_coord(
            entry.location,
            z_value=entry.location.z if entry.location.z is not None else entry.z_pickup,
        )
    else:
        loc = tips["A1"]

    kwargs = _entry_kwargs_for_model(entry, TipRack)
    kwargs.update(
        location=loc,
        tips=tips,
        tip_present=dict(entry.tip_present),
        slots=_build_holder_slots(entry.slots, default_z=loc.z),
    )
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
    # The YAML layer represents holder→labware references as name strings
    # (List[str] / Optional[str]), but the typed Python fields
    # (Dict[str, Vial] / Optional[WellPlate]) are resolved in pass 2 of
    # the loader. Drop these name-valued keys here so they don't reach the
    # typed constructor. A deliberate per-type check: if a future holder
    # grows a new reference field, the loader must be updated.
    if isinstance(entry, VialHolderYamlEntry):
        kwargs.pop("vials", None)
    if isinstance(entry, WellPlateHolderYamlEntry):
        kwargs.pop("well_plate", None)
    kwargs["location"] = _point_to_coord(entry.location, z_value=resolved_z)
    kwargs["slots"] = _build_holder_slots(entry.slots, default_z=resolved_z)
    return model_class(**kwargs)


def _resolve_vial_holder_references(
    deck_key: str,
    entry: VialHolderYamlEntry,
    holder: "VialHolder",
    labware: Dict[str, Labware],
    claimed: Dict[str, str],
) -> None:
    """Resolve vial_holder.vials name refs and assign the typed dict.

    Existence, correct-type, and cross-holder single-ownership checks run
    here because they require the full deck inventory. The drift check,
    back-reference assignment, and orphan back-reference clearing all happen
    inside ``VialHolder``'s own validator when ``vials`` is assigned below.
    ``VialHolder.contained_labware`` is derived from ``vials`` via
    ``_iter_contained_labware``; no separate mirror write is needed.
    """
    resolved: Dict[str, Vial] = {}
    for vial_name in entry.vials:
        if vial_name not in labware:
            raise DeckLoaderError(
                f"❌ vial_holder '{deck_key}' references unknown vial '{vial_name}'.\n"
                f"How to fix: define a top-level labware entry of type: vial with name '{vial_name}'."
            )
        target = labware[vial_name]
        if not isinstance(target, Vial):
            raise DeckLoaderError(
                f"❌ vial_holder '{deck_key}' references '{vial_name}', "
                f"which is not a vial (got {type(target).__name__}).\n"
                f"How to fix: only vial labware may be listed under vial_holder.vials."
            )
        if vial_name in claimed:
            raise DeckLoaderError(
                f"❌ vial '{vial_name}' is referenced by both "
                f"'{claimed[vial_name]}' and '{deck_key}'.\n"
                f"How to fix: each vial may belong to at most one holder."
            )
        claimed[vial_name] = deck_key
        resolved[vial_name] = target

    try:
        holder.vials = resolved
    except ValueError as exc:
        # Let the holder validator's message speak for itself — it already
        # names the specific invariant (drift, slot_count, seat-height,
        # name mismatch) that failed, each with its own actionable detail.
        raise DeckLoaderError(f"❌ vial_holder '{deck_key}': {exc}") from exc


def _resolve_well_plate_holder_reference(
    deck_key: str,
    entry: WellPlateHolderYamlEntry,
    holder: "WellPlateHolder",
    labware: Dict[str, Labware],
    claimed: Dict[str, str],
) -> None:
    """Resolve well_plate_holder.well_plate name ref and assign the typed field.

    Existence, correct-type, single-ownership, and "height_mm must be set"
    checks run here to surface YAML-specific "How to fix" guidance. The
    z-drift check and back-reference management happen inside
    ``WellPlateHolder``'s validator when ``well_plate`` is assigned below;
    the height_mm check is repeated there as a defence-in-depth guarantee
    for programmatic callers that construct the holder directly.
    ``contained_labware`` is derived via ``_iter_contained_labware``.
    """
    if entry.well_plate is None:
        return

    plate_name = entry.well_plate
    if plate_name not in labware:
        raise DeckLoaderError(
            f"❌ well_plate_holder '{deck_key}' references unknown well_plate '{plate_name}'.\n"
            f"How to fix: define a top-level labware entry of type: well_plate with name '{plate_name}'."
        )
    target = labware[plate_name]
    if not isinstance(target, WellPlate):
        raise DeckLoaderError(
            f"❌ well_plate_holder '{deck_key}' references '{plate_name}', "
            f"which is not a well_plate (got {type(target).__name__}).\n"
            f"How to fix: only well_plate labware may be assigned to well_plate_holder.well_plate."
        )
    if plate_name in claimed:
        raise DeckLoaderError(
            f"❌ well_plate '{plate_name}' is referenced by both "
            f"'{claimed[plate_name]}' and '{deck_key}'.\n"
            f"How to fix: each well plate may belong to at most one holder."
        )
    if target.height_mm is None:
        raise DeckLoaderError(
            f"❌ well_plate '{plate_name}' is held by '{deck_key}' but has no "
            "height_mm; top-Z calculations will fail at runtime.\n"
            "How to fix: set `height_mm` on the well_plate YAML entry."
        )

    claimed[plate_name] = deck_key
    try:
        holder.well_plate = target
    except ValueError as exc:
        raise DeckLoaderError(f"❌ well_plate_holder '{deck_key}': {exc}") from exc


def _build_deck_from_raw(raw: dict[str, Any], *, total_z_height: float | None = None) -> Deck:
    raw = _resolve_load_names(raw)
    schema = DeckYamlSchema.model_validate(raw)
    labware: Dict[str, Labware] = {}

    # Pass 1: build non-holder labware plus holders that don't reference
    # other labware by name (tip_rack, tip_disposal, wall). Vial/plate
    # holders are deferred so their referenced vials/plates exist first.
    deferred_holders: list[tuple[str, Any]] = []
    for name, entry in schema.labware.items():
        if isinstance(entry, WellPlateYamlEntry):
            labware[name] = _build_well_plate(entry, total_z_height=total_z_height)
        elif isinstance(entry, VialYamlEntry):
            labware[name] = _build_vial(entry, total_z_height=total_z_height)
        elif isinstance(entry, TipRackYamlEntry):
            labware[name] = _build_tip_rack(entry, total_z_height=total_z_height)
        elif isinstance(entry, TipDisposalYamlEntry):
            labware[name] = _build_holder(
                entry,
                total_z_height=total_z_height,
                model_class=TipDisposal,
            )
        elif isinstance(entry, WallYamlEntry):
            labware[name] = Wall(
                name=entry.name,
                corner_1=Coordinate3D(
                    x=entry.corner_1.x,
                    y=entry.corner_1.y,
                    z=entry.corner_1.z if entry.corner_1.z is not None else 0.0,
                ),
                corner_2=Coordinate3D(
                    x=entry.corner_2.x,
                    y=entry.corner_2.y,
                    z=entry.corner_2.z if entry.corner_2.z is not None else 0.0,
                ),
            )
        elif isinstance(entry, (VialHolderYamlEntry, WellPlateHolderYamlEntry)):
            if isinstance(entry, VialHolderYamlEntry):
                holder = _build_holder(
                    entry,
                    total_z_height=total_z_height,
                    model_class=VialHolder,
                )
            else:
                holder = _build_holder(
                    entry,
                    total_z_height=total_z_height,
                    model_class=WellPlateHolder,
                )
            labware[name] = holder
            deferred_holders.append((name, entry))
        else:
            raise DeckLoaderError(
                f"❌ Internal loader error: unsupported deck labware entry type "
                f"'{type(entry).__name__}'. This indicates a schema/loader mismatch; "
                "please file a bug."
            )

    # Pass 2: resolve holder→labware references by name.
    claimed: Dict[str, str] = {}
    for deck_key, entry in deferred_holders:
        holder = labware[deck_key]
        # Pass 1 dispatch already constructed each deferred holder via
        # model_class=VialHolder / WellPlateHolder, so the runtime types
        # below are guaranteed — no defensive isinstance re-check needed.
        if isinstance(entry, VialHolderYamlEntry):
            _resolve_vial_holder_references(deck_key, entry, holder, labware, claimed)
        else:
            _resolve_well_plate_holder_reference(deck_key, entry, holder, labware, claimed)

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

    Already-formatted :class:`DeckLoaderError`s are re-raised untouched so the
    caller sees the resolver's "How to fix" guidance directly. Pydantic
    validation errors, YAML parse errors, and ``FileNotFoundError`` (the
    user-actionable "wrong path" case) are wrapped with a concise message.
    Other OS errors (``PermissionError``, ``IsADirectoryError``, etc.) and
    unexpected programming bugs are left to propagate with their native
    tracebacks, which are more useful than a generic envelope.

    Raises:
        DeckLoaderError: concise, actionable message intended for CLI/UX output.
    """
    resolved_path = Path(path)
    try:
        return load_deck_from_yaml(resolved_path, total_z_height=total_z_height)
    except DeckLoaderError:
        raise
    except (ValidationError, yaml.YAMLError, FileNotFoundError) as exc:
        raise DeckLoaderError(_format_loader_exception(resolved_path, exc)) from exc
