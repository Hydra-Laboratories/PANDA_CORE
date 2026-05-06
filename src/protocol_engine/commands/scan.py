"""Protocol command: scan a well plate with an instrument."""

from __future__ import annotations

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
from ._dispatch import inject_runtime_args
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
    entry_travel_height: float | None = None,
    interwell_travel_height: float | None = None,
    method_kwargs: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Scan every well on *plate* using *instrument*'s *method*.

    Iterates wells in row-major order (A1, A2, ..., B1, B2, ...). For each
    well, uses :func:`approach_and_descend` to safely travel above the
    well (at ``interwell_travel_height``) and descend to the per-well
    action Z, then calls the method.

    Scan owns travel-Z between positions; everything per-position
    (action/start Z and any method-specific stopping criteria) lives in
    ``method_kwargs`` or on the instrument's board config. The one
    method-side knob scan understands is ``method_kwargs.measurement_height``:
    when set, the gantry descends to that absolute deck-frame Z at every
    well and the same value is forwarded into the bound method (so
    closed-loop callees start from there). When omitted, the gantry
    descends to ``instr.measurement_height`` from the board config.

    When a ``DataStore`` is configured on *context*, each measurement
    is persisted as an experiment + measurement row in the database.

    Args:
        context:       Runtime context (board, deck, logger).
        plate:         Deck key of the well plate (e.g. "plate_1").
        instrument:    Name of the instrument registered on the board.
        method:        Name of the method on the instrument to call per well.
        delay_s:       Seconds to pause between wells (default 0.0).
        entry_travel_height:
                       Optional absolute Z used only for the initial
                       transit into the first well of the scan.
        interwell_travel_height:
                       Optional absolute Z used between wells. When omitted,
                       defaults to ``method_kwargs.measurement_height`` if
                       set, otherwise scan delegates to
                       ``Board.move_to_labware``'s default approach
                       (``instr.safe_approach_height``).
        method_kwargs: Keyword arguments passed to the instrument method
                       on each well.

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
            entry_travel_height=entry_travel_height,
            interwell_travel_height=interwell_travel_height,
            method_kwargs=method_kwargs,
        )
    except ValueError as exc:
        raise ProtocolExecutionError(str(exc)) from exc

    # `measurement_height` in method_kwargs is a hybrid: it's the scan-level
    # descent target *and*, for closed-loop methods like ASMI.indentation,
    # the start Z passed into the method. Pop it out so we don't blindly
    # forward it to methods that don't declare the parameter (e.g. open-loop
    # `measure` would TypeError on the unexpected kwarg). The dispatch
    # helper re-injects it via signature inspection.
    forwarded_kwargs = dict(normalized.method_kwargs)
    per_well_measurement_height = forwarded_kwargs.pop("measurement_height", None)

    results: Dict[str, Any] = {}
    sorted_wells = sorted(plate_obj.wells, key=_row_major_key)
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
            measurement_height=per_well_measurement_height,
        )

        kwargs = inject_runtime_args(
            callable_method, forwarded_kwargs, context,
            measurement_height=per_well_measurement_height,
        )
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
