"""Protocol command: scan a well plate with an instrument."""

from __future__ import annotations

import inspect
import json
import logging
import sqlite3
import time
from typing import TYPE_CHECKING, Any, Dict

from deck.labware.well_plate import WellPlate

from ..errors import ProtocolExecutionError
from ..measurements import normalize_measurement
from ..registry import protocol_command

if TYPE_CHECKING:
    from ..protocol import ProtocolContext

logger = logging.getLogger(__name__)


def _row_major_key(well_id: str) -> tuple:
    """Sort key for row-major traversal: (row_letter, column_number)."""
    return (well_id[0], int(well_id[1:]))


@protocol_command("scan")
def scan(
    context: ProtocolContext,
    plate: str,
    instrument: str,
    method: str,
    delay_s: float = 0.0,
    method_kwargs: Dict[str, Any] = {},
) -> Dict[str, Any]:
    """Scan every well on *plate* using *instrument*'s *method*.

    Iterates wells in row-major order (A1, A2, ..., B1, B2, ...).
    For each well, moves the instrument via ``Board.move_to_labware``
    (which applies ``safe_approach_height`` during XY travel and
    ``measurement_height`` at the target), then calls the method with
    any provided keyword arguments.

    When a ``DataStore`` is configured on *context*, each measurement
    is persisted as an experiment + measurement row in the database.

    Args:
        context:       Runtime context (board, deck, logger).
        plate:         Deck key of the well plate (e.g. "plate_1").
        instrument:    Name of the instrument registered on the board.
        method:        Name of the method on the instrument to call per well.
        delay_s:       Seconds to pause between wells (default 0.0).
        method_kwargs: Keyword arguments passed to the instrument method
                       on each well (e.g. {"intensity": 50, "exposure_time": 10.0}).

    Returns:
        Mapping of well ID to the result of each method call.
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

    results: Dict[str, Any] = {}
    sorted_wells = sorted(plate_obj.wells, key=_row_major_key)
    for i, well_id in enumerate(sorted_wells):
        if i > 0 and delay_s > 0:
            context.logger.info("Pausing %.1fs between wells", delay_s)
            time.sleep(delay_s)

        well = plate_obj.get_well_center(well_id)
        context.board.move_to_labware(instrument, well)

        # Inject gantry if the method accepts it (e.g. ASMI.indentation
        # needs the gantry for Z stepping), then merge with method_kwargs.
        sig = inspect.signature(callable_method)
        kwargs: Dict[str, Any] = dict(method_kwargs)
        if "gantry" in sig.parameters:
            kwargs["gantry"] = context.board.gantry
        result = callable_method(**kwargs)
        results[well_id] = result

        if context.data_store is not None and context.campaign_id is not None:
            try:
                contents = context.data_store.get_contents(
                    context.campaign_id, plate, well_id,
                )
                contents_json = json.dumps(contents) if contents else "[]"
                exp_id = context.data_store.create_experiment(
                    campaign_id=context.campaign_id,
                    labware_name=plate_obj.name,
                    well_id=well_id,
                    contents_json=contents_json,
                )
                measurement = normalize_measurement(
                    instrument_name=instrument,
                    method_name=method,
                    raw_result=result,
                )
                context.data_store.log_measurement(exp_id, measurement)
            except (sqlite3.Error, TypeError, ValueError) as exc:
                logger.warning(
                    "Failed to log measurement for well %s: %s", well_id, exc,
                )

    return results
