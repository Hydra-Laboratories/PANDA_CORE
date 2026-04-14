"""Protocol command: move."""

from typing import Any, TYPE_CHECKING

from ..registry import protocol_command

if TYPE_CHECKING:
    from ..protocol import ProtocolContext


@protocol_command("move")
def move(context: "ProtocolContext", instrument: str, position: Any) -> None:
    """Move *instrument* to *position*.

    Position resolution:
        1. ``[x, y, z]`` list/tuple → raw gantry move to the literal
           coordinates (applies only the instrument's mounting offsets).
        2. Named position from the protocol YAML ``positions:`` block →
           same raw move treatment.
        3. Deck target string (e.g. ``"plate_1.A1"``) → safe
           ``move_to_labware`` that retracts (if needed), travels XY at
           the instrument's ``safe_approach_height``, and ends above the
           target (no descent — use ``measure``/``aspirate``/etc. to
           engage).

    Args:
        context:    Runtime context (board, deck, logger).
        instrument: Name of the instrument registered on the board.
        position:   Named position, [x, y, z] list, or deck target string.
    """
    if isinstance(position, (list, tuple)):
        target = tuple(position)
        context.logger.info("move: %s -> %s (raw)", instrument, target)
        context.board.move(instrument, target)
        return
    if isinstance(position, str) and position in context.positions:
        target = tuple(context.positions[position])
        context.logger.info("move: %s -> %s (named: %s)", instrument, target, position)
        context.board.move(instrument, target)
        return

    # Deck target — route through move_to_labware so safe_approach_height
    # is applied consistently with measure/aspirate at the same position.
    coord = context.deck.resolve(position)
    context.logger.info("move: %s -> %s (labware: safe approach)", instrument, position)
    context.board.move_to_labware(instrument, coord)
