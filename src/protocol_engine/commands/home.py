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
    gantry = context.board.gantry
    gantry.set_serial_timeout(10)
    gantry.home()
    gantry.zero_coordinates()
    gantry.set_serial_timeout(0.05)
