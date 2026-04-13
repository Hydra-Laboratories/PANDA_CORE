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
    position: str,
    method: str = "measure",
    method_kwargs: Dict[str, Any] = {},
) -> Any:
    """Measure at a deck position using *instrument*.

    Resolves *position* on the deck, applies the instrument's
    measurement_height offset to Z, moves the instrument there,
    then calls the instrument method with any provided kwargs.

    Args:
        context:       Runtime context (board, deck, logger).
        instrument:    Name of the instrument registered on the board.
        position:      Deck target string (e.g. "plate_1.A1").
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

    coord = context.deck.resolve(position)
    # move_to_labware handles approach (safe_approach_height) and action
    # (measurement_height) offsets in a single call.
    context.board.move_to_labware(instrument, coord)

    context.logger.info("measure: %s.%s(%s) at %s", instrument, method, method_kwargs, position)
    return getattr(instr, method)(**method_kwargs)
