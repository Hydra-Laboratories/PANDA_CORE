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
from ..scan_args import normalize_scan_arguments
from ._movement import approach_and_descend

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
    measurement_height: float | None = None,
    entry_travel_height: float | None = None,
    interwell_travel_height: float | None = None,
    indentation_limit: float | None = None,
    method_kwargs: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Scan every well on *plate* using *instrument*'s *method*.

    Iterates wells in row-major order (A1, A2, ..., B1, B2, ...).
    For each well, uses :func:`approach_and_descend` to safely travel
    above the well (at ``interwell_travel_height``) and descend to the
    action Z (``measurement_height``), then calls the method with any
    provided keyword arguments.

    When a ``DataStore`` is configured on *context*, each measurement
    is persisted as an experiment + measurement row in the database.

    Args:
        context:       Runtime context (board, deck, logger).
        plate:         Deck key of the well plate (e.g. "plate_1").
        instrument:    Name of the instrument registered on the board.
        method:        Name of the method on the instrument to call per well.
        delay_s:       Seconds to pause between wells (default 0.0).
        measurement_height:
                       Optional protocol-level action/start Z. This is an
                       absolute deck-frame Z plane, not a labware-relative
                       offset.
        entry_travel_height:
                       Optional absolute Z coordinate used only for the
                       initial transit into the first well of the scan.
        interwell_travel_height:
                       Optional absolute Z coordinate used between wells.
                       Defaults to ``measurement_height`` when provided.
        indentation_limit:
                       ASMI indentation stopping Z.
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
    try:
        normalized = normalize_scan_arguments(
            measurement_height=measurement_height,
            entry_travel_height=entry_travel_height,
            interwell_travel_height=interwell_travel_height,
            indentation_limit=indentation_limit,
            method_kwargs=method_kwargs,
        )
    except ValueError as exc:
        raise ProtocolExecutionError(str(exc)) from exc

    results: Dict[str, Any] = {}
    sorted_wells = sorted(plate_obj.wells, key=_row_major_key)
    sig = inspect.signature(callable_method)
    for i, well_id in enumerate(sorted_wells):
        if i > 0 and delay_s > 0:
            context.logger.info("Pausing %.1fs between wells", delay_s)
            time.sleep(delay_s)

        well = plate_obj.get_well_center(well_id)
        approach_z = (
            normalized.entry_travel_height
            if i == 0 and normalized.entry_travel_height is not None
            else normalized.interwell_travel_height
        )
        approach_and_descend(
            context,
            instrument,
            well,
            safe_approach_height=approach_z,
            measurement_height=normalized.measurement_height,
        )

        # Inject gantry if the method accepts it (e.g. ASMI.indentation
        # needs the gantry for Z stepping), then merge with method_kwargs.
        kwargs: Dict[str, Any] = dict(normalized.method_kwargs)
        if (
            normalized.measurement_height is not None
            and "measurement_height" in sig.parameters
        ):
            kwargs["measurement_height"] = normalized.measurement_height
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

    if sorted_wells:
        last_well = plate_obj.get_well_center(sorted_wells[-1])
        final_approach_z = (
            normalized.interwell_travel_height
            if normalized.interwell_travel_height is not None
            else instr.safe_approach_height
        )
        context.board.move(instrument, (last_well.x, last_well.y, final_approach_z))

    return results
