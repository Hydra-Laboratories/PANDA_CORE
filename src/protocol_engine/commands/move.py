"""Protocol command: move."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..registry import protocol_command

if TYPE_CHECKING:
    from ..protocol import ProtocolContext


@protocol_command("move")
def move(context: ProtocolContext, instrument: str, position: str) -> None:
    """Move *instrument* to *position* on the deck.

    Resolves the deck position and applies the instrument's
    measurement_height offset to Z before moving.

    Args:
        context:    Runtime context (board, deck, logger).
        instrument: Name of the instrument registered on the board (e.g. "pipette").
        position:   Deck target string resolved via ``Deck.resolve()``
                    (e.g. "plate_1.A1", "vial_1").
    """
    coord = context.deck.resolve(position)
    instr = context.board.instruments[instrument]
    target = (coord.x, coord.y, coord.z + instr.measurement_height)
    context.logger.info("move: %s -> %s (%s)", instrument, position, target)
    context.board.move(instrument, target)
