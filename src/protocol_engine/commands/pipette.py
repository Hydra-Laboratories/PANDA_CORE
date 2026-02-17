"""Protocol commands for pipette operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..errors import ProtocolExecutionError
from ..registry import protocol_command

if TYPE_CHECKING:
    from ..protocol import ProtocolContext


def _get_pipette(context: ProtocolContext):
    """Return the pipette instrument or raise ProtocolExecutionError."""
    if "pipette" not in context.board.instruments:
        raise ProtocolExecutionError(
            "No pipette registered on the board. "
            "Add one via Board(instruments={'pipette': ...})"
        )
    return context.board.instruments["pipette"]


@protocol_command("aspirate")
def aspirate(
    context: ProtocolContext,
    position: str,
    volume_ul: float,
    speed: float = 50.0,
) -> None:
    """Move pipette to *position*, then aspirate."""
    coord = context.deck.resolve(position)
    pipette = _get_pipette(context)
    context.board.move("pipette", coord)
    return pipette.aspirate(volume_ul, speed)


@protocol_command("dispense")
def dispense(
    context: ProtocolContext,
    position: str,
    volume_ul: float,
    speed: float = 50.0,
) -> None:
    """Move pipette to *position*, then dispense."""
    coord = context.deck.resolve(position)
    pipette = _get_pipette(context)
    context.board.move("pipette", coord)
    return pipette.dispense(volume_ul, speed)


@protocol_command("blowout")
def blowout(
    context: ProtocolContext,
    position: str,
    speed: float = 50.0,
) -> None:
    """Move pipette to *position*, then blowout."""
    coord = context.deck.resolve(position)
    pipette = _get_pipette(context)
    context.board.move("pipette", coord)
    pipette.blowout(speed)


@protocol_command("mix")
def mix(
    context: ProtocolContext,
    position: str,
    volume_ul: float,
    repetitions: int = 3,
    speed: float = 50.0,
) -> None:
    """Move pipette to *position*, then mix."""
    coord = context.deck.resolve(position)
    pipette = _get_pipette(context)
    context.board.move("pipette", coord)
    return pipette.mix(volume_ul, repetitions, speed)


@protocol_command("pick_up_tip")
def pick_up_tip(
    context: ProtocolContext,
    position: str,
    speed: float = 50.0,
) -> None:
    """Move pipette to *position*, then pick up a tip."""
    coord = context.deck.resolve(position)
    pipette = _get_pipette(context)
    context.board.move("pipette", coord)
    pipette.pick_up_tip(speed)


@protocol_command("drop_tip")
def drop_tip(
    context: ProtocolContext,
    position: str,
    speed: float = 50.0,
) -> None:
    """Move pipette to *position*, then drop the tip."""
    coord = context.deck.resolve(position)
    pipette = _get_pipette(context)
    context.board.move("pipette", coord)
    pipette.drop_tip(speed)
