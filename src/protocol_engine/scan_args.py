"""Scan argument normalization for legacy and new YAML names."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class NormalizedScanArguments:
    """Runtime scan arguments after resolving compatibility aliases."""

    measurement_height: float | None
    entry_travel_z: float | None
    interwell_travel_z: float | None
    method_kwargs: dict[str, Any]


def _warn_deprecated(old_name: str, new_name: str) -> None:
    warnings.warn(
        f"`{old_name}` is deprecated; use `{new_name}` instead.",
        DeprecationWarning,
        stacklevel=3,
    )


def _resolve_alias(
    *,
    new_name: str,
    new_value: Any,
    old_name: str,
    old_value: Any,
) -> Any:
    """Resolve a new field and its legacy alias.

    Both names may be supplied only when they carry the same value. This lets
    migrations be mechanical without letting two conflicting values silently
    choose one behavior.
    """
    if old_value is not None:
        _warn_deprecated(old_name, new_name)
    if new_value is not None and old_value is not None and new_value != old_value:
        raise ValueError(
            f"Conflicting scan arguments: `{new_name}`={new_value!r} and "
            f"`{old_name}`={old_value!r}. Use only `{new_name}`."
        )
    return new_value if new_value is not None else old_value


def normalize_scan_arguments(
    *,
    measurement_height: float | None = None,
    entry_travel_z: float | None = None,
    entry_travel_height: float | None = None,
    safe_approach_height: float | None = None,
    interwell_travel_height: float | None = None,
    indentation_limit: float | None = None,
    method_kwargs: Mapping[str, Any] | None = None,
) -> NormalizedScanArguments:
    """Normalize scan naming aliases while preserving legacy behavior.

    Phase 1 does not change the current positive-down coordinate semantics. The
    normalized ``entry_travel_z`` and ``interwell_travel_z`` values are still
    absolute Z coordinates consumed by the existing scan implementation.
    """
    kwargs = dict(method_kwargs or {})

    resolved_entry = _resolve_alias(
        new_name="entry_travel_height",
        new_value=entry_travel_height,
        old_name="entry_travel_z",
        old_value=entry_travel_z,
    )
    resolved_interwell = _resolve_alias(
        new_name="interwell_travel_height",
        new_value=interwell_travel_height,
        old_name="safe_approach_height",
        old_value=safe_approach_height,
    )

    if measurement_height is not None and "measurement_height" in kwargs:
        if kwargs["measurement_height"] != measurement_height:
            raise ValueError(
                "Conflicting scan arguments: `measurement_height`="
                f"{measurement_height!r} and `method_kwargs.measurement_height`="
                f"{kwargs['measurement_height']!r}. Use only top-level "
                "`measurement_height`."
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
    method_z_limit = kwargs.get("z_limit")
    resolved_limit = _resolve_alias(
        new_name="indentation_limit",
        new_value=(
            indentation_limit
            if indentation_limit is not None
            else method_indentation_limit
        ),
        old_name="z_limit",
        old_value=method_z_limit,
    )
    if resolved_limit is not None:
        kwargs["z_limit"] = resolved_limit

    # New scan naming keeps common non-contact scans concise.
    if resolved_interwell is None and measurement_height is not None:
        resolved_interwell = measurement_height
    if resolved_entry is None:
        resolved_entry = resolved_interwell

    return NormalizedScanArguments(
        measurement_height=measurement_height,
        entry_travel_z=resolved_entry,
        interwell_travel_z=resolved_interwell,
        method_kwargs=kwargs,
    )
