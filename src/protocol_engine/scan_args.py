"""Scan argument normalization for the Phase 1 scan naming surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class NormalizedScanArguments:
    """Runtime scan arguments after resolving compatibility aliases."""

    measurement_height: float | None
    entry_travel_z: float | None
    interwell_travel_z: float | None
    method_kwargs: dict[str, Any]


def normalize_scan_arguments(
    *,
    measurement_height: float | None = None,
    entry_travel_height: float | None = None,
    interwell_travel_height: float | None = None,
    indentation_limit: float | None = None,
    method_kwargs: Mapping[str, Any] | None = None,
) -> NormalizedScanArguments:
    """Normalize the supported scan naming surface.

    The normalized ``entry_travel_z`` and ``interwell_travel_z`` values are
    absolute deck-frame Z coordinates consumed by the scan implementation.
    """
    kwargs = dict(method_kwargs or {})

    if measurement_height is not None and "measurement_height" in kwargs:
        if kwargs["measurement_height"] != measurement_height:
            raise ValueError(
                "Conflicting scan arguments: `measurement_height`="
                f"{measurement_height!r} and `method_kwargs.measurement_height`="
                f"{kwargs['measurement_height']!r}. Use only top-level "
                "`measurement_height`."
            )
    if "z_limit" in kwargs:
        raise ValueError(
            "`z_limit` is no longer supported. Use `indentation_limit`."
        )

    method_indentation_limit = kwargs.pop("indentation_limit", None)
    if indentation_limit is not None and method_indentation_limit is not None:
        if indentation_limit != method_indentation_limit:
            raise ValueError(
                "Conflicting scan arguments: `indentation_limit`="
                f"{indentation_limit!r} and "
                "`method_kwargs.indentation_limit`="
                f"{method_indentation_limit!r}. Use only top-level "
                "`indentation_limit`."
            )
    resolved_limit = (
        indentation_limit
        if indentation_limit is not None
        else method_indentation_limit
    )
    if resolved_limit is not None:
        kwargs["indentation_limit"] = resolved_limit

    # New scan naming keeps common non-contact scans concise.
    resolved_interwell = interwell_travel_height
    if resolved_interwell is None and measurement_height is not None:
        resolved_interwell = measurement_height
    resolved_entry = entry_travel_height
    if resolved_entry is None:
        resolved_entry = resolved_interwell

    return NormalizedScanArguments(
        measurement_height=measurement_height,
        entry_travel_z=resolved_entry,
        interwell_travel_z=resolved_interwell,
        method_kwargs=kwargs,
    )
