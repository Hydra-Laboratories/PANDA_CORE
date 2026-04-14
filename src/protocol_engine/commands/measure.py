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

    Three phases:
      1. **Approach.** ``Board.move_to_labware`` retracts (if below
         ``safe_approach_height``) and travels XY to above the target.
      2. **Descend.** Lower straight down to
         ``labware.z + measurement_height``.
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
    # 1. Approach: safely travel to above the labware at safe_approach_height.
    context.board.move_to_labware(instrument, coord)
    # 2. Descend: lower to action Z at the same XY.
    x, y, z = coord if isinstance(coord, tuple) else (coord.x, coord.y, coord.z)
    action_z = z + instr.measurement_height
    context.board.move(instrument, (x, y, action_z))

    context.logger.info("measure: %s.%s(%s) at %s", instrument, method, method_kwargs, position)
    return getattr(instr, method)(**method_kwargs)
