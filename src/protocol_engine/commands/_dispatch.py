"""Shared method-dispatch helpers used by engaging protocol commands.

Most instrument methods are open-loop: a protocol command pre-positions
the gantry, then invokes the method to act at that pose. Some methods
are closed-loop and need to drive the gantry themselves during the
action — ASMI.indentation steps Z and reads force in a feedback loop.
Those methods declare a ``gantry`` parameter.

YAML protocol files don't mention the gantry handle. Commands inject it
from the runtime context based on the method signature, so the same
``method_kwargs`` work whether or not the underlying method is closed-
loop.
"""

from __future__ import annotations

import inspect
import math
from typing import Any, Callable, Dict, TYPE_CHECKING

from ..errors import ProtocolExecutionError

if TYPE_CHECKING:
    from ..protocol import ProtocolContext


def inject_runtime_args(
    callable_method: Callable[..., Any],
    method_kwargs: Dict[str, Any],
    context: "ProtocolContext",
    *,
    measurement_height: float | None = None,
) -> Dict[str, Any]:
    """Return a fresh kwargs dict with runtime-injected args added.

    Injects when the method's signature declares the parameter:
      * ``gantry`` — from ``context.board.gantry``.
      * ``measurement_height`` — from the keyword argument when supplied.

    Runtime injection is the source of truth: when the engine has a value
    that reflects physical state (the gantry handle, the Z the gantry was
    just descended to), it overrides whatever ``method_kwargs`` carried.
    A YAML-supplied ``gantry`` is never legitimate (the board only has one
    gantry), and a YAML-supplied ``method_kwargs.measurement_height`` that
    diverges from the protocol command's descent target is the exact
    footgun this dispatch surface exists to prevent.

    Raises:
        ProtocolExecutionError: if the method declares ``gantry`` but
            ``context.board.gantry`` is None — produces a clearer error
            than the late ``AttributeError`` the closed-loop method would
            otherwise raise inside its first ``gantry.move(...)``.
        ProtocolExecutionError: if ``measurement_height`` is supplied as
            something other than a finite number (e.g. an unconverted
            YAML string) — fail at the dispatch boundary rather than
            deep inside motion code.
    """
    if measurement_height is not None:
        if (
            isinstance(measurement_height, bool)
            or not isinstance(measurement_height, (int, float))
            or not math.isfinite(float(measurement_height))
        ):
            raise ProtocolExecutionError(
                f"measurement_height must be a finite number, got "
                f"{type(measurement_height).__name__} {measurement_height!r}."
            )

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
    if (
        measurement_height is not None
        and "measurement_height" in sig.parameters
    ):
        kwargs["measurement_height"] = measurement_height
    return kwargs
