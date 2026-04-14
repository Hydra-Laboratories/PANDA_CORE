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


def test_measure_routes_through_move_to_labware():
    """The measure command must go through Board.move_to_labware so the
    instrument's Z offsets are applied consistently with scan/aspirate."""
    instr = _mock_instr(measurement_height=3.0)
    coord = Coordinate3D(x=10.0, y=20.0, z=30.0)
    ctx = _ctx(instr, well_coord=coord)

    result = measure(ctx, instrument="uvvis", position="plate_1.A1")

    ctx.board.move_to_labware.assert_called_once_with("uvvis", coord)
    ctx.board.move.assert_not_called()
    instr.measure.assert_called_once()
    assert result == "spectrum"


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
    instr = _mock_instr()
    # Make hasattr return False for 'nonexistent_method' via spec
    del instr.nonexistent_method
    instr.nonexistent_method = MagicMock(side_effect=AttributeError)
    # Use spec-less mock without the method attribute
    instr = MagicMock(spec=BaseInstrument)
    instr.name = "uvvis"
    instr.offset_x = instr.offset_y = instr.depth = 0.0
    instr.measurement_height = 0.0
    instr.safe_approach_height = 0.0
    ctx = _ctx(instr)
    with pytest.raises(ProtocolExecutionError, match="has no method"):
        measure(ctx, instrument="uvvis", position="plate_1.A1", method="nope")
