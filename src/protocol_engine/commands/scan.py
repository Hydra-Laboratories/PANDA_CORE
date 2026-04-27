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
from ..well_selection import resolve_well_ids
from ._movement import approach_and_descend

if TYPE_CHECKING:
    from ..protocol import ProtocolContext

logger = logging.getLogger(__name__)


@protocol_command("scan")
def scan(
    context: ProtocolContext,
    plate: str,
    instrument: str,
    method: str,
    wells: list[str] | None = None,
    delay_s: float = 0.0,
    entry_travel_z: float | None = None,
    safe_approach_height: float | None = None,
    method_kwargs: Dict[str, Any] = {},
) -> Dict[str, Any]:
    """Scan wells on *plate* using *instrument*'s *method*.

    When ``wells`` is omitted, iterates every well in row-major order
    (A1, A2, ..., B1, B2, ...). When ``wells`` is supplied, scans exactly
    those well IDs in the caller-provided order.
    For each well, uses :func:`approach_and_descend` to safely travel
    above the well (at ``safe_approach_height``) and descend to the
    action Z (``measurement_height``), then calls the method with any
    provided keyword arguments.

    When a ``DataStore`` is configured on *context*, each measurement
    is persisted as an experiment + measurement row in the database.

    Args:
        context:       Runtime context (board, deck, logger).
        plate:         Deck key of the well plate (e.g. "plate_1").
        instrument:    Name of the instrument registered on the board.
        method:        Name of the method on the instrument to call per well.
        wells:         Optional explicit well IDs to scan.
        delay_s:       Seconds to pause between wells (default 0.0).
        entry_travel_z:
                       Optional absolute Z coordinate used only for the
                       initial transit into the first well of the scan.
        safe_approach_height:
                       Optional protocol-level override for the XY-travel
                       absolute Z coordinate used between wells. When
                       omitted, the instrument's board-configured default
                       is used.
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
        scan_wells = resolve_well_ids(plate_obj.wells, wells)
    except ValueError as exc:
        raise ProtocolExecutionError(str(exc)) from exc

    results: Dict[str, Any] = {}
    sig = inspect.signature(callable_method)
    for i, well_id in enumerate(scan_wells):
        if i > 0 and delay_s > 0:
            context.logger.info("Pausing %.1fs between wells", delay_s)
            time.sleep(delay_s)

        well = plate_obj.get_well_center(well_id)
        approach_z = entry_travel_z if i == 0 and entry_travel_z is not None else safe_approach_height
        approach_and_descend(
            context,
            instrument,
            well,
            safe_approach_height=approach_z,
        )

        # Inject gantry if the method accepts it (e.g. ASMI.indentation
        # needs the gantry for Z stepping), then merge with method_kwargs.
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

    if scan_wells:
        last_well = plate_obj.get_well_center(scan_wells[-1])
        final_approach_z = (
            safe_approach_height
            if safe_approach_height is not None
            else last_well.z - instr.safe_approach_height
        )
        context.board.move(instrument, (last_well.x, last_well.y, final_approach_z))

    return results
