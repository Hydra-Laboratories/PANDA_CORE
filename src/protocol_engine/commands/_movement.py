"""Shared movement helpers used by engaging protocol commands.

Every command that *engages* with a labware (measure, scan, aspirate,
dispense, etc.) follows the same two-phase motion:

    1. Approach: ``board.move_to_labware`` — retract (if below approach)
       and travel XY at the absolute deck-frame approach Z.
    2. Descend: raw ``board.move`` straight down to
       the absolute deck-frame action Z.

Centralising that composition here prevents docstring/behaviour drift
between command modules.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..protocol import ProtocolContext


def unpack_xyz(coord: Any) -> tuple[float, float, float]:
    """Extract ``(x, y, z)`` from a ``Coordinate3D``-like object, a
    tuple, or a list.

    Commands receive ``coord`` from ``Deck.resolve()`` which returns a
    ``Coordinate3D`` in production. Tests frequently pass raw tuples.
    """
    if isinstance(coord, (tuple, list)):
        return (coord[0], coord[1], coord[2])
    return (coord.x, coord.y, coord.z)


def approach_and_descend(
    context: "ProtocolContext",
    instrument: str,
    coord: Any,
    safe_approach_height: float | None = None,
    measurement_height: float | None = None,
) -> None:
    """Safely travel above a labware target, then descend to action Z.

    Args:
        context:    Runtime context (board + instruments).
        instrument: Name of the instrument registered on the board.
        coord:      Labware-reference point (``Coordinate3D``-like or
                    ``(x, y, z)`` tuple).
        safe_approach_height:
                    Optional protocol-level override for the XY-travel
                    absolute Z coordinate.
        measurement_height:
                    Optional protocol-level override for the action/start
                    absolute deck-frame Z coordinate.
    """
    instr = context.board.instruments[instrument]
    x, y, z = unpack_xyz(coord)
    action_z = (
        measurement_height
        if measurement_height is not None
        else instr.measurement_height
    )
    if safe_approach_height is None:
        context.board.move_to_labware(instrument, coord)
    else:
        if safe_approach_height < action_z:
            raise ValueError(
                f"safe_approach_height ({safe_approach_height}) must be >= "
                f"action_z ({action_z}) for instrument {instrument!r} under "
                "the deck-origin +Z-up convention."
            )
        approach_z = safe_approach_height
        context.board.move(
            instrument, (x, y, approach_z), travel_z=approach_z,
        )
    del z
    context.board.move(instrument, (x, y, action_z))
