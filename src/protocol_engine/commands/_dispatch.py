"""Shared method-dispatch helpers used by engaging protocol commands.

Most instrument methods are open-loop: a protocol command pre-positions
the gantry, then invokes the method to act at that pose. Some methods
are closed-loop and need to drive the gantry themselves during the
action — ASMI.indentation steps Z and reads force in a feedback loop.
Those methods declare a ``gantry`` parameter.

YAML protocol files don't mention the gantry handle, the resolved
absolute action Z, or the resolved absolute target Z. Commands inject
those from the runtime context based on the method signature, so the
same ``method_kwargs`` work whether or not the underlying method is
closed-loop.

Naming convention (the same one used across the protocol layer):

* ``[name]_z`` — absolute deck-frame Z (WPos).
* ``[name]_height`` — labware-relative offset (mm above the well/labware
  surface; +above, -below).

Runtime-injected names use ``_z`` because the engine has resolved
relative offsets to absolute deck-frame Z values before dispatch.
"""

from __future__ import annotations

import inspect
import math
from typing import Any, Callable, Dict, TYPE_CHECKING

from ..errors import ProtocolExecutionError

if TYPE_CHECKING:
    from ..protocol import ProtocolContext


def _assert_finite(value: Any, name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise ProtocolExecutionError(
            f"{name} must be a finite number, got "
            f"{type(value).__name__} {value!r}."
        )


def inject_runtime_args(
    callable_method: Callable[..., Any],
    method_kwargs: Dict[str, Any],
    context: "ProtocolContext",
    *,
    measurement_z: float,
    target_z: float | None = None,
) -> Dict[str, Any]:
    """Return a fresh kwargs dict with runtime-injected args added.

    Injects when the method's signature declares the parameter:
      * ``gantry`` — from ``context.board.gantry``.
      * ``measurement_z`` — the resolved absolute deck-frame action Z
        (where the gantry was just descended to).
      * ``target_z`` — the resolved absolute deepest Z for descent loops
        (e.g. ASMI indentation). Optional; only injected when supplied.

    Runtime injection is the source of truth: when the engine has a value
    that reflects physical state, it overrides whatever ``method_kwargs``
    carried. ``scan_args._LEGACY_KWARG_HINTS`` rejects YAML-supplied
    duplicates at load time.

    ``measurement_z`` is a required keyword: callers always have a
    resolved absolute Z to forward, and a defaulted ``None`` would let a
    forgotten parameter slip through silently. Tests of pure
    gantry-injection behavior pass any finite sentinel (e.g. ``0.0``).

    Raises:
        ProtocolExecutionError: if ``measurement_z`` or ``target_z`` is
            not a finite number, or if the method declares ``gantry`` but
            ``context.board.gantry`` is None.
    """
    _assert_finite(measurement_z, "measurement_z")
    if target_z is not None:
        _assert_finite(target_z, "target_z")

    kwargs: Dict[str, Any] = dict(method_kwargs)
    sig = inspect.signature(callable_method)
    if "gantry" in sig.parameters:
        if context.board.gantry is None:
            raise ProtocolExecutionError(
                f"Method {callable_method.__qualname__!r} declares a `gantry` "
                "parameter but `context.board.gantry` is None. Closed-loop "
                "methods need an attached gantry."
            )
        kwargs["gantry"] = context.board.gantry
    if "measurement_z" in sig.parameters:
        kwargs["measurement_z"] = measurement_z
    method_takes_target_z = "target_z" in sig.parameters
    if target_z is not None and method_takes_target_z:
        kwargs["target_z"] = target_z
    elif target_z is not None and not method_takes_target_z:
        # The engine has a resolved deepest-Z (from `indentation_limit_height`)
        # but the method doesn't consume one. Silently dropping it would let
        # a typo like `method: indent` (instead of `indentation`) bypass the
        # depth bound entirely.
        raise ProtocolExecutionError(
            f"Method {callable_method.__qualname__!r} does not declare a "
            "`target_z` parameter, but `indentation_limit_height` was "
            "supplied — the resolved deepest-Z would be silently ignored. "
            "Either drop `indentation_limit_height` from the scan command "
            "or use a method that consumes it (e.g. ASMI `indentation`)."
        )
    if (
        "target_z" in sig.parameters
        and target_z is None
        and sig.parameters["target_z"].default is inspect.Parameter.empty
    ):
        # Method declares `target_z` as required but the engine has no value
        # to inject. Surface this as an actionable command-boundary error
        # rather than letting Python raise a bare TypeError when the engine
        # calls the method without the required keyword.
        raise ProtocolExecutionError(
            f"Method {callable_method.__qualname__!r} requires a `target_z`, "
            "which the engine resolves from `indentation_limit_height`. Add "
            "`indentation_limit_height` (signed labware-relative offset; "
            "negative = below the well surface) to the scan command."
        )
    return kwargs
