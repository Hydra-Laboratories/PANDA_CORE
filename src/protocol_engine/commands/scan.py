"""Protocol command: scan a well plate with an instrument."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from src.deck.labware.well_plate import WellPlate

from ..errors import ProtocolExecutionError
from ..registry import protocol_command

if TYPE_CHECKING:
    from ..protocol import ProtocolContext


def _row_major_key(well_id: str) -> tuple:
    """Sort key for row-major traversal: (row_letter, column_number)."""
    return (well_id[0], int(well_id[1:]))


@protocol_command("scan")
def scan(
    context: ProtocolContext,
    plate: str,
    instrument: str,
    method: str,
) -> Dict[str, bool]:
    """Scan every well on *plate* using *instrument*'s *method*.

    Iterates wells in row-major order (A1, A2, …, B1, B2, …).
    For each well, moves the instrument into position (applying
    measurement_height offset) then calls the method.

    Args:
        context:    Runtime context (board, deck, logger).
        plate:      Deck key of the well plate (e.g. "plate_1").
        instrument: Name of the instrument registered on the board.
        method:     Name of the method on the instrument to call per well.

    Returns:
        Mapping of well ID to boolean result of each method call.
    """
    plate_obj = context.deck[plate]
    if not isinstance(plate_obj, WellPlate):
        raise ProtocolExecutionError(
            f"scan requires a WellPlate, but '{plate}' is {type(plate_obj).__name__}."
        )

    if instrument not in context.board.instruments:
        raise ProtocolExecutionError(
            f"Unknown instrument '{instrument}'. "
            f"Available: {', '.join(sorted(context.board.instruments.keys()))}"
        )
    instr = context.board.instruments[instrument]

    if not hasattr(instr, method):
        raise ProtocolExecutionError(
            f"Instrument '{instrument}' has no method '{method}'."
        )
    callable_method = getattr(instr, method)

    results: Dict[str, bool] = {}
    for well_id in sorted(plate_obj.wells, key=_row_major_key):
        well = plate_obj.get_well_center(well_id)
        target = (well.x, well.y, well.z + instr.measurement_height)
        context.board.move(instrument, target)
        results[well_id] = callable_method(plate_obj)

    return results
