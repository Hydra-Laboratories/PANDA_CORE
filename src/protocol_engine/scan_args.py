"""Scan argument normalization.

The scan command's required heights (``measurement_height`` and
``safe_approach_height``) are first-class function parameters and are
validated by the command itself, not here. This module only handles
``method_kwargs`` reconciliation: rejecting legacy field names and
threading ``indentation_limit`` through when present.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class NormalizedScanArguments:
    """Runtime scan arguments after compatibility checks."""

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
    indentation_limit: float | None = None,
    method_kwargs: Mapping[str, Any] | None = None,
) -> NormalizedScanArguments:
    """Validate and normalize the scan command's ``method_kwargs``.

    Raises:
        ValueError: When legacy fields are present or top-level
            ``indentation_limit`` conflicts with ``method_kwargs``.
    """
    kwargs = dict(method_kwargs or {})

    for legacy_key, message in _LEGACY_KWARG_HINTS.items():
        if legacy_key in kwargs:
            raise ValueError(message)

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

    return NormalizedScanArguments(method_kwargs=kwargs)
