"""Protocol command: move."""

from typing import Any, TYPE_CHECKING

from ..registry import protocol_command

if TYPE_CHECKING:
    from ..protocol import ProtocolContext


@protocol_command("move")
def move(context: "ProtocolContext", instrument: str, position: Any) -> None:
    """Move *instrument* to *position*.

    Position resolution order:
        1. Protocol-defined named position (from ``positions:`` in YAML)
        2. Raw [x, y, z] coordinates
        3. Deck target string via ``Deck.resolve()``

    Args:
        context:    Runtime context (board, deck, logger).
        instrument: Name of the instrument registered on the board.
        position:   Named position, [x, y, z] list, or deck target string.
    """
    if isinstance(position, (list, tuple)):
        target = tuple(position)
    elif isinstance(position, str) and position in context.positions:
        target = tuple(context.positions[position])
    else:
        target = context.deck.resolve(position)
    context.logger.info("move: %s -> %s", instrument, target)
    context.board.move(instrument, target)
