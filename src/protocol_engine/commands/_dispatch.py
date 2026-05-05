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
from typing import Any, Callable, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..protocol import ProtocolContext


def inject_runtime_args(
    callable_method: Callable[..., Any],
    method_kwargs: Dict[str, Any],
    context: "ProtocolContext",
) -> Dict[str, Any]:
    """Return a fresh kwargs dict with runtime-injected args added.

    Currently injects:
      * ``gantry`` — set to ``context.board.gantry`` when the method
        declares a ``gantry`` parameter (e.g. ASMI.indentation).

    Caller-provided ``method_kwargs`` always win; injection only fills
    in parameters the caller didn't already supply.
    """
    kwargs: Dict[str, Any] = dict(method_kwargs)
    sig = inspect.signature(callable_method)
    if "gantry" in sig.parameters and "gantry" not in kwargs:
        kwargs["gantry"] = context.board.gantry
    return kwargs
