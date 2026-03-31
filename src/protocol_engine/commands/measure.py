"""Protocol command: measure with an instrument at the current position."""

from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

from ..errors import ProtocolExecutionError
from ..registry import protocol_command

if TYPE_CHECKING:
    from ..protocol import ProtocolContext


@protocol_command("measure")
def measure(
    context: ProtocolContext,
    instrument: str,
    method: str = "measure",
    method_kwargs: Dict[str, Any] = {},
) -> Any:
    """Call a measurement method on *instrument* at its current position.

    Unlike ``scan``, this does not iterate wells or move the gantry.
    Pair with a preceding ``move`` command to position first.

    Args:
        context:       Runtime context (board, deck, logger).
        instrument:    Name of the instrument registered on the board.
        method:        Name of the callable on the instrument (default "measure").
        method_kwargs: Keyword arguments passed to the instrument method
                       (e.g. {"intensity": 50, "exposure_time": 10.0}).

    Returns:
        Whatever the instrument method returns.
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

    context.logger.info("measure: %s.%s(%s)", instrument, method, method_kwargs)
    return getattr(instr, method)(**method_kwargs)
