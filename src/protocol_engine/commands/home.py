"""Protocol command: home the gantry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..registry import protocol_command

if TYPE_CHECKING:
    from ..protocol import ProtocolContext


@protocol_command("home")
def home(context: "ProtocolContext") -> None:
    """Home the gantry and zero coordinates.

    Sends GRBL $H homing cycle, then zeros the work coordinate system.

    Args:
        context: Runtime context (board, deck, logger).
    """
    context.logger.info("home: homing gantry")
    context.board.gantry.home()
    context.board.gantry.zero_coordinates()
