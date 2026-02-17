"""Tests for the scan protocol command."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from deck.labware.labware import Coordinate3D
from deck.labware.well_plate import WellPlate
from instruments.base_instrument import BaseInstrument
from protocol_engine.errors import ProtocolExecutionError
from protocol_engine.protocol import ProtocolContext


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_2x2_plate() -> WellPlate:
    return WellPlate(
        name="plate_1",
        model_name="test_96",
        length_mm=127.71,
        width_mm=85.43,
        height_mm=14.10,
        rows=2,
        columns=2,
        wells={
            "A1": Coordinate3D(x=0.0, y=0.0, z=-5.0),
            "A2": Coordinate3D(x=10.0, y=0.0, z=-5.0),
            "B1": Coordinate3D(x=0.0, y=-8.0, z=-5.0),
            "B2": Coordinate3D(x=10.0, y=-8.0, z=-5.0),
        },
        capacity_ul=200.0,
        working_volume_ul=150.0,
    )


def _make_2x3_plate() -> WellPlate:
    return WellPlate(
        name="plate_2",
        model_name="test_model",
        length_mm=127.71,
        width_mm=85.43,
        height_mm=14.10,
        rows=2,
        columns=3,
        wells={
            "A1": Coordinate3D(x=0.0, y=0.0, z=-5.0),
            "A2": Coordinate3D(x=10.0, y=0.0, z=-5.0),
            "A3": Coordinate3D(x=20.0, y=0.0, z=-5.0),
            "B1": Coordinate3D(x=0.0, y=-8.0, z=-5.0),
            "B2": Coordinate3D(x=10.0, y=-8.0, z=-5.0),
            "B3": Coordinate3D(x=20.0, y=-8.0, z=-5.0),
        },
        capacity_ul=200.0,
        working_volume_ul=150.0,
    )


class _FakeSensor(BaseInstrument):
    """Concrete BaseInstrument subclass for scan tests."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.call_count = 0
        self.received_plates = []
        self._return_value = True

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def health_check(self) -> bool:
        return True

    def measure(self, plate: WellPlate) -> bool:
        self.call_count += 1
        self.received_plates.append(plate)
        return self._return_value


def _make_sensor(**kwargs) -> _FakeSensor:
    defaults = dict(name="sensor", offset_x=0.0, offset_y=0.0, depth=0.0)
    defaults.update(kwargs)
    return _FakeSensor(**defaults)


def _mock_context(
    plate: WellPlate | None = None,
    sensor: _FakeSensor | None = None,
) -> ProtocolContext:
    plate = plate or _make_2x2_plate()
    sensor = sensor or _make_sensor()

    board = MagicMock()
    board.instruments = {"uvvis": sensor}

    deck = MagicMock()
    deck.__getitem__ = MagicMock(return_value=plate)

    return ProtocolContext(
        board=board,
        deck=deck,
        logger=logging.getLogger("test_scan_command"),
    )


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestScanCommand:

    def test_moves_instrument_to_each_well(self):
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()
        sensor = _make_sensor()
        ctx = _mock_context(plate=plate, sensor=sensor)

        scan(ctx, plate="plate_1", instrument="uvvis", method="measure")

        assert ctx.board.move.call_count == 4

    def test_visits_wells_in_row_major_order(self):
        from protocol_engine.commands.scan import scan

        plate = _make_2x3_plate()
        sensor = _make_sensor()
        ctx = _mock_context(plate=plate, sensor=sensor)

        scan(ctx, plate="plate_2", instrument="uvvis", method="measure")

        # Row-major: A1, A2, A3, B1, B2, B3
        move_calls = ctx.board.move.call_args_list
        positions = [c.args[1] for c in move_calls]
        xs = [p[0] for p in positions]
        assert xs == [0.0, 10.0, 20.0, 0.0, 10.0, 20.0]

    def test_applies_measurement_height_offset(self):
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()  # wells at z=-5.0
        sensor = _make_sensor(measurement_height=3.0)
        ctx = _mock_context(plate=plate, sensor=sensor)

        scan(ctx, plate="plate_1", instrument="uvvis", method="measure")

        # target z = well.z + measurement_height = -5.0 + 3.0 = -2.0
        move_calls = ctx.board.move.call_args_list
        zs = [c.args[1][2] for c in move_calls]
        assert zs == [-2.0, -2.0, -2.0, -2.0]

    def test_returns_dict_of_results_per_well(self):
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()
        sensor = _make_sensor()
        ctx = _mock_context(plate=plate, sensor=sensor)

        result = scan(ctx, plate="plate_1", instrument="uvvis", method="measure")

        assert isinstance(result, dict)
        assert set(result.keys()) == {"A1", "A2", "B1", "B2"}
        assert all(v is True for v in result.values())

    def test_captures_false_results(self):
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()
        sensor = _make_sensor()
        sensor._return_value = False
        ctx = _mock_context(plate=plate, sensor=sensor)

        result = scan(ctx, plate="plate_1", instrument="uvvis", method="measure")

        assert all(v is False for v in result.values())

    def test_calls_method_once_per_well(self):
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()
        sensor = _make_sensor()
        ctx = _mock_context(plate=plate, sensor=sensor)

        scan(ctx, plate="plate_1", instrument="uvvis", method="measure")

        assert sensor.call_count == 4

    def test_passes_plate_to_method(self):
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()
        sensor = _make_sensor()
        ctx = _mock_context(plate=plate, sensor=sensor)

        scan(ctx, plate="plate_1", instrument="uvvis", method="measure")

        assert all(p is plate for p in sensor.received_plates)

    def test_validates_plate_is_wellplate(self):
        from protocol_engine.commands.scan import scan

        sensor = _make_sensor()
        ctx = _mock_context(sensor=sensor)
        # Make deck return a non-WellPlate object
        ctx.deck.__getitem__ = MagicMock(return_value=MagicMock(spec=[]))

        with pytest.raises(ProtocolExecutionError, match="WellPlate"):
            scan(ctx, plate="vial_1", instrument="uvvis", method="measure")

    def test_unknown_instrument_raises(self):
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()
        sensor = _make_sensor()
        ctx = _mock_context(plate=plate, sensor=sensor)

        with pytest.raises(ProtocolExecutionError, match="instrument"):
            scan(ctx, plate="plate_1", instrument="nonexistent", method="measure")

    def test_unknown_method_raises(self):
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()
        sensor = _make_sensor()
        ctx = _mock_context(plate=plate, sensor=sensor)

        with pytest.raises(ProtocolExecutionError, match="method"):
            scan(ctx, plate="plate_1", instrument="uvvis", method="nonexistent")

    def test_moves_with_correct_instrument_name(self):
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()
        sensor = _make_sensor()
        ctx = _mock_context(plate=plate, sensor=sensor)

        scan(ctx, plate="plate_1", instrument="uvvis", method="measure")

        for c in ctx.board.move.call_args_list:
            assert c.args[0] == "uvvis"
