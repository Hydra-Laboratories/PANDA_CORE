"""Protocol command: measure with an instrument at a deck position."""

from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

from ..errors import ProtocolExecutionError
from ..registry import protocol_command
from ._dispatch import inject_runtime_args
from ._movement import engage_at_labware

if TYPE_CHECKING:
    from ..protocol import ProtocolContext


@protocol_command("measure")
def measure(
    context: ProtocolContext,
    instrument: str,
    position: str,
    method: str = "measure",
    method_kwargs: Dict[str, Any] = {},
) -> Any:
    """Measure at a deck position using *instrument*.

    Motion:
      1. Travel at the gantry's ``safe_z`` (absolute) to above the target.
      2. Descend straight down to ``labware.height_mm + instr.measurement_height``.
      3. Call ``instrument.method(**method_kwargs)``.

    ``measurement_height`` is owned by the instrument config — a
    labware-relative offset (mm above the labware's ``height_mm`` surface;
    negative = below). It is not a protocol-command parameter.
    """
    if instrument not in context.board.instruments:
        raise ProtocolExecutionError(
            f"Unknown instrument '{instrument}'. "
            f"Available: {', '.join(sorted(context.board.instruments.keys()))}"
        )
    instr = context.board.instruments[instrument]

    if not hasattr(instr, method):
        raise ProtocolExecutionError(
            f"Instrument '{instrument}' has no method '{method}'."
        )

    try:
        action_z = engage_at_labware(
            context,
            instrument,
            position,
            command_label="measure",
        )
    except ValueError as exc:
        raise ProtocolExecutionError(str(exc)) from exc

    context.logger.info(
        "measure: %s.%s(%s) at %s — action_z=%.3f",
        instrument, method, method_kwargs, position, action_z,
    )

    # Inject gantry + the resolved absolute action Z into closed-loop
    # methods (e.g. ASMI.indentation) that drive the gantry themselves.
    callable_method = getattr(instr, method)
    kwargs = inject_runtime_args(
        callable_method, method_kwargs, context,
        measurement_height=action_z,
    )
    return callable_method(**kwargs)
