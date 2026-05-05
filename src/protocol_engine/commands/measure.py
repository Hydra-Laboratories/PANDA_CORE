"""Protocol command: measure with an instrument at the current position."""

from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

from ..errors import ProtocolExecutionError
from ..registry import protocol_command
from ._dispatch import inject_runtime_args
from ._movement import approach_and_descend

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

    Three phases:
      1. **Approach.** ``Board.move_to_labware`` retracts (if below
         ``safe_approach_height``) and travels XY to above the target.
      2. **Descend.** Lower straight down to the current action Z.
      3. **Act.** Call the instrument method.

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
    context.logger.info("measure: %s.%s(%s) at %s", instrument, method, method_kwargs, position)
    approach_and_descend(context, instrument, coord)

    callable_method = getattr(instr, method)
    kwargs = inject_runtime_args(callable_method, method_kwargs, context)
    return callable_method(**kwargs)
