"""Protocol command: home the gantry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from gantry.origin import validate_deck_origin_minima

from ..registry import protocol_command

if TYPE_CHECKING:
    from ..protocol import ProtocolContext


@protocol_command("home")
def home(context: "ProtocolContext") -> None:
    """Home the gantry without redefining a calibrated deck-origin WCS.

    Deck-origin configs rely on persistent G54 WPos established by the
    calibration script. Legacy configs without deck-origin zero minima keep the
    older behavior of zeroing at the homed pose.

    Args:
        context: Runtime context (board, deck, logger).
    """
    context.logger.info("home: homing gantry")
    gantry = context.board.gantry
    gantry.set_serial_timeout(10)
    try:
        gantry.home()
        if context.gantry is None:
            gantry.zero_coordinates()
        else:
            try:
                validate_deck_origin_minima(context.gantry)
            except ValueError:
                gantry.zero_coordinates()
    finally:
        gantry.set_serial_timeout(0.05)
