"""Tests for the `measure` protocol command."""

from unittest.mock import MagicMock

import pytest

from deck.labware.labware import Coordinate3D
from instruments.base_instrument import BaseInstrument
from protocol_engine.commands.measure import measure
from protocol_engine.errors import ProtocolExecutionError
from protocol_engine.protocol import ProtocolContext


def _mock_instr(measurement_height=0.0, safe_approach_height=None):
    resolved_safe = (
        safe_approach_height if safe_approach_height is not None else measurement_height
    )
    instr = MagicMock(spec=BaseInstrument)
    instr.name = "uvvis"
    instr.offset_x = 0.0
    instr.offset_y = 0.0
    instr.depth = 0.0
    instr.measurement_height = measurement_height
    instr.safe_approach_height = resolved_safe
    instr.measure = MagicMock(return_value="spectrum")
    return instr


def _ctx(instr, well_coord=Coordinate3D(x=10.0, y=20.0, z=30.0)):
    board = MagicMock()
    board.instruments = {"uvvis": instr}
    deck = MagicMock()
    deck.resolve = MagicMock(return_value=well_coord)
    return ProtocolContext(board=board, deck=deck)


def test_measure_approaches_then_descends_then_acts():
    """measure: approach above labware via move_to_labware, descend to
    action Z via raw move, then call the instrument method."""
    instr = _mock_instr(measurement_height=3.0)
    coord = Coordinate3D(x=10.0, y=20.0, z=30.0)
    ctx = _ctx(instr, well_coord=coord)

    result = measure(ctx, instrument="uvvis", position="plate_1.A1")

    # Step 1: approach.
    ctx.board.move_to_labware.assert_called_once_with("uvvis", coord)
    # Step 2: descend to action Z = 30 - 3 = 27 at same XY (user-space is
    # positive-down; a positive measurement_height lifts the probe above).
    ctx.board.move.assert_called_once_with("uvvis", (10.0, 20.0, 27.0))
    # Step 3: act.
    instr.measure.assert_called_once()
    assert result == "spectrum"


def test_measure_contact_instrument_descends_below_reference():
    """Contact instrument with negative measurement_height descends
    below the labware reference Z."""
    instr = _mock_instr(measurement_height=-5.0, safe_approach_height=20.0)
    coord = Coordinate3D(x=10.0, y=20.0, z=30.0)
    ctx = _ctx(instr, well_coord=coord)

    measure(ctx, instrument="uvvis", position="plate_1.A1")

    # Descent target = 30 - (-5) = 35 (tip dipped 5 mm into the sample).
    ctx.board.move.assert_called_once_with("uvvis", (10.0, 20.0, 35.0))


def test_measure_passes_method_kwargs():
    instr = _mock_instr()
    ctx = _ctx(instr)
    measure(
        ctx, instrument="uvvis", position="plate_1.A1",
        method="measure", method_kwargs={"intensity": 50},
    )
    instr.measure.assert_called_once_with(intensity=50)


def test_measure_unknown_instrument_raises():
    instr = _mock_instr()
    ctx = _ctx(instr)
    with pytest.raises(ProtocolExecutionError, match="Unknown instrument"):
        measure(ctx, instrument="not_a_thing", position="plate_1.A1")


def test_measure_unknown_method_raises():
    # Use a spec-bound mock so hasattr() returns False for methods
    # that aren't on BaseInstrument (i.e. "nope").
    instr = MagicMock(spec=BaseInstrument)
    instr.name = "uvvis"
    instr.offset_x = instr.offset_y = instr.depth = 0.0
    instr.measurement_height = 0.0
    instr.safe_approach_height = 0.0
    ctx = _ctx(instr)
    with pytest.raises(ProtocolExecutionError, match="has no method"):
        measure(ctx, instrument="uvvis", position="plate_1.A1", method="nope")
