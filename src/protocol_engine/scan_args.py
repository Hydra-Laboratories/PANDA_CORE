"""Scan argument normalization for the multi-well scan command."""

from __future__ import annotations

import math
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


def _coerce_finite_number(value: Any, *, key: str) -> float:
    """Validate a YAML-supplied numeric kwarg and return it as a float.

    `method_kwargs` is typed `Dict[str, Any]` because each method has
    its own keyword set, so the YAML loader can't statically type the
    contents. That means a string like ``measurement_height: "27.0"``
    or ``measurement_height: ""`` reaches the dispatch surface unchecked
    and surfaces deep inside motion code as an opaque ``TypeError``.
    Validate at the boundary instead.
    """
    if isinstance(value, bool):
        raise ValueError(
            f"`method_kwargs.{key}` must be a finite number, got bool {value!r}."
        )
    if not isinstance(value, (int, float)):
        raise ValueError(
            f"`method_kwargs.{key}` must be a finite number, got "
            f"{type(value).__name__} {value!r}."
        )
    if not math.isfinite(float(value)):
        raise ValueError(
            f"`method_kwargs.{key}` must be a finite number, got {value!r}."
        )
    return float(value)


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

    # Type-check numeric kwargs that scan and the dispatch helper consume
    # before they reach motion code, so YAML strings/empty values fail
    # with a clear message instead of an opaque TypeError downstream.
    for numeric_key in ("measurement_height", "indentation_limit"):
        if numeric_key in kwargs and kwargs[numeric_key] is not None:
            kwargs[numeric_key] = _coerce_finite_number(
                kwargs[numeric_key], key=numeric_key,
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
