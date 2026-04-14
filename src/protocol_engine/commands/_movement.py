"""Shared movement helpers used by engaging protocol commands.

Every command that *engages* with a labware (measure, scan, aspirate,
dispense, etc.) follows the same two-phase motion:

    1. Approach: ``board.move_to_labware`` — retract (if below approach)
       and travel XY at ``labware.z + safe_approach_height``.
    2. Descend: raw ``board.move`` straight down to
       ``labware.z + measurement_height``.

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
) -> None:
    """Safely travel above a labware target, then descend to action Z.

    Args:
        context:    Runtime context (board + instruments).
        instrument: Name of the instrument registered on the board.
        coord:      Labware-reference point (``Coordinate3D``-like or
                    ``(x, y, z)`` tuple).
    """
    context.board.move_to_labware(instrument, coord)
    x, y, z = unpack_xyz(coord)
    instr = context.board.instruments[instrument]
    action_z = z + instr.measurement_height
    context.board.move(instrument, (x, y, action_z))
