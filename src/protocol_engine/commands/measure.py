"""Protocol command: measure with an instrument at the current position."""

from __future__ import annotations

import inspect
import json
import logging
import sqlite3
from typing import Any, Dict, Optional, TYPE_CHECKING

from ..errors import ProtocolExecutionError
from ..measurements import normalize_measurement
from ..registry import protocol_command

if TYPE_CHECKING:
    from ..protocol import ProtocolContext

logger = logging.getLogger(__name__)


def _parse_position(position: str) -> tuple[str, str | None]:
    parts = position.split(".", 1)
    if len(parts) == 2:
        return (parts[0], parts[1])
    return (parts[0], None)


@protocol_command("measure")
def measure(
    context: ProtocolContext,
    instrument: str,
    position: str,
    method: str = "measure",
    method_kwargs: Optional[Dict[str, Any]] = None,
) -> Any:
    """Measure at a deck position using *instrument*.

    Resolves *position* on the deck, applies the instrument's
    measurement_height offset to Z, moves the instrument there,
    then calls the instrument method with any provided kwargs.

    Args:
        context:       Runtime context (board, deck, logger).
        instrument:    Name of the instrument registered on the board.
        position:      Deck target string (e.g. "plate_1.A1").
        method:        Name of the callable on the instrument (default "measure").
        method_kwargs: Keyword arguments passed to the instrument method
                       (e.g. {"intensity": 50, "exposure_time": 10.0}).

    Returns:
        Whatever the instrument method returns.
    """
    if method_kwargs is None:
        method_kwargs = {}

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

    coord = context.deck.resolve(position)
    target = (coord.x, coord.y, coord.z - instr.measurement_height)
    context.board.move(instrument, target)

    callable_method = getattr(instr, method)
    kwargs: Dict[str, Any] = dict(method_kwargs)
    sig = inspect.signature(callable_method)
    if "gantry" in sig.parameters:
        kwargs["gantry"] = context.board.gantry

    context.logger.info("measure: %s.%s(%s) at %s", instrument, method, kwargs, position)
    result = callable_method(**kwargs)

    if context.data_store is not None and context.campaign_id is not None:
        try:
            labware_key, well_id = _parse_position(position)
            contents = context.data_store.get_contents(
                context.campaign_id,
                labware_key,
                well_id,
            )
            contents_json = json.dumps(contents) if contents else "[]"
            exp_id = context.data_store.create_experiment(
                campaign_id=context.campaign_id,
                labware_name=context.deck[labware_key].name,
                well_id=well_id,
                contents_json=contents_json,
            )
            measurement = normalize_measurement(
                instrument_name=instrument,
                method_name=method,
                raw_result=result,
            )
            context.data_store.log_measurement(exp_id, measurement)
        except sqlite3.Error as exc:
            logger.error(
                "Database error logging measurement for %s — data was NOT saved. "
                "Check disk space and database integrity. Error: %s",
                position,
                exc,
            )

    return result
