"""Scan argument normalization for the multi-well scan command."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class NormalizedScanArguments:
    """Runtime scan arguments after normalization.

    `entry_travel_height` and `interwell_travel_height` are absolute
    deck-frame Z coordinates. Per-well action Z (``measurement_height``)
    and method-specific kwargs (``indentation_limit`` etc.) live inside
    ``method_kwargs`` — scan does not own them.
    """

    entry_travel_height: float | None
    interwell_travel_height: float | None
    method_kwargs: dict[str, Any]


def normalize_scan_arguments(
    *,
    entry_travel_height: float | None = None,
    interwell_travel_height: float | None = None,
    method_kwargs: Mapping[str, Any] | None = None,
) -> NormalizedScanArguments:
    """Normalize the scan command's argument surface.

    Scan owns multi-well travel between positions; everything else
    (per-well action Z, instrument-specific stopping criteria) lives in
    ``method_kwargs`` or on the instrument's board config.
    """
    kwargs = dict(method_kwargs or {})

    if "z_limit" in kwargs:
        raise ValueError(
            "`z_limit` is no longer supported. Use `indentation_limit` "
            "inside `method_kwargs`."
        )

    measurement_height = kwargs.get("measurement_height")
    resolved_interwell = interwell_travel_height
    if resolved_interwell is None and measurement_height is not None:
        resolved_interwell = measurement_height
    resolved_entry = entry_travel_height
    if resolved_entry is None:
        resolved_entry = resolved_interwell

    return NormalizedScanArguments(
        entry_travel_height=resolved_entry,
        interwell_travel_height=resolved_interwell,
        method_kwargs=kwargs,
    )
