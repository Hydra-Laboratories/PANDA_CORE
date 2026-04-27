"""Shared well-selection helpers for protocol commands."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def row_major_key(well_id: str) -> tuple[str, int]:
    """Sort key for row-major traversal: (row_letter, column_number)."""
    return (well_id[0], int(well_id[1:]))


def resolve_well_ids(
    available_wells: Mapping[str, Any],
    selected_wells: Sequence[str] | None = None,
) -> list[str]:
    """Resolve scan well IDs.

    When *selected_wells* is omitted, return every available well in row-major
    order. When supplied, preserve the caller-provided order so protocol YAML
    can represent handpicked repeat/repair runs from external workflows.
    """
    if selected_wells is None:
        return sorted(available_wells, key=row_major_key)

    if isinstance(selected_wells, str):
        raise ValueError("scan wells must be a list of well IDs, not a string.")

    resolved: list[str] = []
    seen: set[str] = set()
    missing: list[str] = []
    duplicates: list[str] = []
    for raw in selected_wells:
        well_id = str(raw).upper()
        if well_id in seen:
            duplicates.append(well_id)
            continue
        seen.add(well_id)
        if well_id not in available_wells:
            missing.append(well_id)
            continue
        resolved.append(well_id)

    if duplicates:
        raise ValueError(
            "scan wells contains duplicates: " + ", ".join(duplicates)
        )
    if missing:
        available = ", ".join(sorted(available_wells, key=row_major_key))
        raise ValueError(
            "Unknown scan wells: "
            + ", ".join(missing)
            + f". Available wells: {available}"
        )
    if not resolved:
        raise ValueError("scan wells must contain at least one well ID.")
    return resolved
