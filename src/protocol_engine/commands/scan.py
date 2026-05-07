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
from ._movement import (
    resolve_instrument_measurement_height,
    resolve_labware_height,
)

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
    safe_approach_height: float | None = None,
    indentation_limit: float | None = None,
    delay_s: float = 0.0,
    method_kwargs: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Scan every well on *plate* using *instrument*'s *method*.

    Iterates wells in row-major order (A1, A2, ..., B1, B2, ...).

    Motion per well, with ``ref_z = plate.height_mm``:

    * **First well of the plate.** Travel at the gantry's ``safe_z``
      (absolute) → descend to ``ref_z + safe_approach_height`` →
      descend to ``ref_z + instr.measurement_height`` → act.
    * **Subsequent wells.** Rise to ``ref_z + safe_approach_height`` at
      the current XY → travel XY at that height → descend to
      ``ref_z + instr.measurement_height`` → act.

    Args:
        context:              Runtime context (board, deck, logger).
        plate:                Deck key of the well plate.
        instrument:           Name of the instrument registered on the board.
        method:               Method on the instrument to call per well.
        safe_approach_height: Labware-relative offset for between-wells XY
                              travel (mm above ``labware.height_mm``).
                              May be set here or on the instrument config;
                              at least one source must define it, and
                              conflicting values across sources are rejected.
        indentation_limit:    ASMI indentation stopping bound (magnitude).
        delay_s:              Seconds to pause between wells (default 0.0).
        method_kwargs:        Keyword arguments passed per well.

    Returns:
        Mapping of well ID to the result of each method call.
    """
    plate_obj = context.deck[plate]
    if not isinstance(plate_obj, WellPlate):
        raise ProtocolExecutionError(
            f"scan requires a WellPlate, but '{plate}' is "
            f"{type(plate_obj).__name__}."
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
            safe_approach_height=safe_approach_height,
            indentation_limit=indentation_limit,
            method_kwargs=method_kwargs,
        )
        ref_z = resolve_labware_height(plate_obj, plate)
        relative_action = resolve_instrument_measurement_height(
            instrument_value=instr.measurement_height,
            instrument_name=instrument,
            command_label="scan",
        )
        # safe_approach_height may still be on either source; reuse a small
        # local dual-source check rather than dragging the resolver back.
        instr_approach = getattr(instr, "safe_approach_height", None)
        cmd_approach = normalized.safe_approach_height
        if instr_approach is not None and cmd_approach is not None:
            if instr_approach != cmd_approach:
                raise ValueError(
                    f"scan: `safe_approach_height` set on instrument "
                    f"'{instrument}' ({instr_approach}) and on the command "
                    f"({cmd_approach}) with conflicting values. When both "
                    "sources are set they must match."
                )
            relative_approach = float(instr_approach)
        elif instr_approach is None and cmd_approach is None:
            raise ValueError(
                f"scan: `safe_approach_height` is not set. Provide it on "
                f"the command or on instrument '{instrument}'."
            )
        else:
            relative_approach = float(
                instr_approach if instr_approach is not None else cmd_approach
            )
    except ValueError as exc:
        raise ProtocolExecutionError(str(exc)) from exc

    action_z = ref_z + relative_action
    approach_z = ref_z + relative_approach

    if approach_z < action_z:
        raise ProtocolExecutionError(
            f"scan: safe_approach_height ({relative_approach}) resolves "
            f"below measurement_height ({relative_action}) for plate "
            f"'{plate}'. Approach must be at or above the action plane."
        )

    results: Dict[str, Any] = {}
    sorted_wells = sorted(plate_obj.wells, key=_row_major_key)

    for i, well_id in enumerate(sorted_wells):
        if i > 0 and delay_s > 0:
            context.logger.info("Pausing %.1fs between wells", delay_s)
            time.sleep(delay_s)

        well = plate_obj.get_well_center(well_id)
        if i == 0:
            context.board.move_to_labware(instrument, well)
            context.board.move(instrument, (well.x, well.y, approach_z))
        else:
            context.board.move(
                instrument, (well.x, well.y, approach_z), travel_z=approach_z,
            )
        context.board.move(instrument, (well.x, well.y, action_z))

        # Use the shared dispatch helper so closed-loop methods get the
        # same gantry-injection + None-gantry guard + finite-number guard
        # as `measure`, instead of scan reimplementing them inline.
        kwargs = inject_runtime_args(
            callable_method, normalized.method_kwargs, context,
            measurement_height=action_z,
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
        context.board.move(
            instrument, (last_well.x, last_well.y, approach_z),
            travel_z=approach_z,
        )

    return results
