"""Tests for the ``measure`` protocol command."""

from unittest.mock import MagicMock

import pytest

from deck.labware.labware import Coordinate3D
from instruments.base_instrument import BaseInstrument
from protocol_engine.commands.measure import measure
from protocol_engine.errors import ProtocolExecutionError
from protocol_engine.protocol import ProtocolContext


HEIGHT_MM = 14.10


def _mock_instr():
    instr = MagicMock(spec=BaseInstrument)
    instr.name = "uvvis"
    instr.offset_x = 0.0
    instr.offset_y = 0.0
    instr.depth = 0.0
    instr.measure = MagicMock(return_value="spectrum")
    return instr


def _ctx(instr, well_coord=None, height_mm=HEIGHT_MM):
    well_coord = well_coord or Coordinate3D(x=10.0, y=20.0, z=height_mm or 0.0)
    board = MagicMock()
    board.instruments = {"uvvis": instr}
    deck = MagicMock()
    deck.resolve = MagicMock(return_value=well_coord)
    labware = MagicMock(height_mm=height_mm)
    deck.__getitem__ = MagicMock(return_value=labware)
    return ProtocolContext(board=board, deck=deck)


def test_measure_travels_at_safe_z_then_descends():
    """measure: move_to_labware (XY at safe_z), then descend to
    height_mm + measurement_height, then call the method."""
    instr = _mock_instr()
    coord = Coordinate3D(x=10.0, y=20.0, z=HEIGHT_MM)
    ctx = _ctx(instr, well_coord=coord)

    result = measure(
        ctx, instrument="uvvis", position="plate_1.A1",
        measurement_height=2.0,
    )

    ctx.board.move_to_labware.assert_called_once_with("uvvis", coord)
    ctx.board.move.assert_called_once_with("uvvis", (10.0, 20.0, HEIGHT_MM + 2.0))
    instr.measure.assert_called_once()
    assert result == "spectrum"


def test_measure_with_negative_offset_descends_below_surface():
    """Negative measurement_height = below the labware surface."""
    instr = _mock_instr()
    coord = Coordinate3D(x=10.0, y=20.0, z=HEIGHT_MM)
    ctx = _ctx(instr, well_coord=coord)

    measure(
        ctx, instrument="uvvis", position="plate_1.A1",
        measurement_height=-1.0,
    )

    ctx.board.move.assert_called_once_with("uvvis", (10.0, 20.0, HEIGHT_MM - 1.0))


def test_measure_passes_method_kwargs():
    instr = _mock_instr()
    ctx = _ctx(instr)
    measure(
        ctx, instrument="uvvis", position="plate_1.A1",
        measurement_height=0.0,
        method="measure", method_kwargs={"intensity": 50},
    )
    instr.measure.assert_called_once_with(intensity=50)


def test_measure_unknown_instrument_raises():
    instr = _mock_instr()
    ctx = _ctx(instr)
    with pytest.raises(ProtocolExecutionError, match="Unknown instrument"):
        measure(
            ctx, instrument="not_a_thing", position="plate_1.A1",
            measurement_height=0.0,
        )


def test_measure_unknown_method_raises():
    instr = MagicMock(spec=BaseInstrument)
    instr.name = "uvvis"
    instr.offset_x = instr.offset_y = instr.depth = 0.0
    ctx = _ctx(instr)
    with pytest.raises(ProtocolExecutionError, match="has no method"):
        measure(
            ctx, instrument="uvvis", position="plate_1.A1",
            measurement_height=0.0, method="nope",
        )


@pytest.mark.parametrize("bad", ["", "1.0", float("nan"), True])
def test_measure_rejects_non_finite_measurement_height(bad):
    instr = _mock_instr()
    ctx = _ctx(instr)
    with pytest.raises(ProtocolExecutionError, match="finite number"):
        measure(
            ctx, instrument="uvvis", position="plate_1.A1",
            measurement_height=bad,
        )
