"""Protocol command: move."""

from __future__ import annotations

from typing import Any, List, TYPE_CHECKING, Union

from ..registry import protocol_command

if TYPE_CHECKING:
    from ..protocol import ProtocolContext


@protocol_command("move")
def move(context: ProtocolContext, instrument: str, position: Union[str, List[float]]) -> None:
    """Move *instrument* to *position*.

    Position can be a deck target string (e.g. "plate_1.A1") resolved
    via Deck.resolve(), or raw [x, y, z] coordinates.

    Args:
        context:    Runtime context (board, deck, logger).
        instrument: Name of the instrument registered on the board.
        position:   Deck target string or [x, y, z] coordinate list.
    """
    if isinstance(position, (list, tuple)):
        target = tuple(position)
    else:
        target = context.deck.resolve(position)
    context.logger.info("move: %s -> %s", instrument, target)
    context.board.move(instrument, target)
