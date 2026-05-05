"""Scan argument normalization.

The scan command takes two height fields and both are *labware-relative*
offsets (mm above the labware's ``height_mm`` surface; negative = below):

* ``measurement_height``: action-plane offset.
* ``safe_approach_height``: between-well XY-travel offset (above the
  action plane).

Inter-labware travel uses the gantry's absolute ``safe_z``, not these
fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class NormalizedScanArguments:
    """Runtime scan arguments after compatibility checks."""

    measurement_height: float | None
    safe_approach_height: float
    method_kwargs: dict[str, Any]


_LEGACY_KWARG_HINTS = {
    "entry_travel_height": (
        "`entry_travel_height` is no longer supported. Inter-labware/entry "
        "travel uses the gantry's `safe_z` (absolute deck-frame Z)."
    ),
    "interwell_travel_height": (
        "`interwell_travel_height` is no longer supported. Use "
        "`safe_approach_height` (labware-relative offset)."
    ),
    "z_limit": (
        "`z_limit` is no longer supported. Use `indentation_limit`."
    ),
}


def normalize_scan_arguments(
    *,
    measurement_height: float | None = None,
    safe_approach_height: float | None = None,
    indentation_limit: float | None = None,
    method_kwargs: Mapping[str, Any] | None = None,
) -> NormalizedScanArguments:
    """Validate and normalize the scan command's argument surface.

    Raises:
        ValueError: When required fields are missing, legacy fields are
            present, or top-level args conflict with ``method_kwargs``.
    """
    kwargs = dict(method_kwargs or {})

    for legacy_key, message in _LEGACY_KWARG_HINTS.items():
        if legacy_key in kwargs:
            raise ValueError(message)

    if safe_approach_height is None:
        raise ValueError(
            "scan requires `safe_approach_height` (labware-relative offset, "
            "mm above the labware's `height_mm` surface)."
        )

    if measurement_height is not None and "measurement_height" in kwargs:
        if kwargs["measurement_height"] != measurement_height:
            raise ValueError(
                "Conflicting scan arguments: top-level `measurement_height`="
                f"{measurement_height!r} and "
                f"`method_kwargs.measurement_height`={kwargs['measurement_height']!r}. "
                "Use only the top-level field."
            )

    method_indentation_limit = kwargs.pop("indentation_limit", None)
    if indentation_limit is not None and method_indentation_limit is not None:
        if indentation_limit != method_indentation_limit:
            raise ValueError(
                "Conflicting scan arguments: top-level `indentation_limit`="
                f"{indentation_limit!r} and "
                f"`method_kwargs.indentation_limit`={method_indentation_limit!r}. "
                "Use only the top-level field."
            )
    resolved_limit = (
        indentation_limit
        if indentation_limit is not None
        else method_indentation_limit
    )
    if resolved_limit is not None:
        kwargs["indentation_limit"] = resolved_limit

    return NormalizedScanArguments(
        measurement_height=measurement_height,
        safe_approach_height=safe_approach_height,
        method_kwargs=kwargs,
    )
