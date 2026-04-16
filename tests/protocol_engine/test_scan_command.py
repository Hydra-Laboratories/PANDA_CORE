"""Tests for the scan protocol command."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from deck.labware.labware import Coordinate3D
from deck.labware.well_plate import WellPlate
from instruments.base_instrument import BaseInstrument
from instruments.uvvis_ccs.models import UVVisSpectrum
from protocol_engine.errors import ProtocolExecutionError
from protocol_engine.measurements import InstrumentMeasurement
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
            "A1": Coordinate3D(x=0.0, y=0.0, z=75.0),
            "A2": Coordinate3D(x=10.0, y=0.0, z=75.0),
            "B1": Coordinate3D(x=0.0, y=8.0, z=75.0),
            "B2": Coordinate3D(x=10.0, y=8.0, z=75.0),
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
            "A1": Coordinate3D(x=0.0, y=0.0, z=75.0),
            "A2": Coordinate3D(x=10.0, y=0.0, z=75.0),
            "A3": Coordinate3D(x=20.0, y=0.0, z=75.0),
            "B1": Coordinate3D(x=0.0, y=8.0, z=75.0),
            "B2": Coordinate3D(x=10.0, y=8.0, z=75.0),
            "B3": Coordinate3D(x=20.0, y=8.0, z=75.0),
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

    def measure(self) -> bool:
        self.call_count += 1
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

        assert ctx.board.move_to_labware.call_count == 4

    def test_visits_wells_in_row_major_order(self):
        from protocol_engine.commands.scan import scan

        plate = _make_2x3_plate()
        sensor = _make_sensor()
        ctx = _mock_context(plate=plate, sensor=sensor)

        scan(ctx, plate="plate_2", instrument="uvvis", method="measure")

        # Row-major: A1, A2, A3, B1, B2, B3
        move_calls = ctx.board.move_to_labware.call_args_list
        positions = [c.args[1] for c in move_calls]
        xs = [p.x for p in positions]
        assert xs == [0.0, 10.0, 20.0, 0.0, 10.0, 20.0]

    def test_passes_raw_well_coord_to_move_to_labware(self):
        # scan delegates safe approach to Board.move_to_labware; descent
        # to action Z happens in scan's subsequent raw board.move call.
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()  # wells at z=75.0
        sensor = _make_sensor(measurement_height=3.0)
        ctx = _mock_context(plate=plate, sensor=sensor)

        scan(ctx, plate="plate_1", instrument="uvvis", method="measure")

        move_calls = ctx.board.move_to_labware.call_args_list
        zs = [c.args[1].z for c in move_calls]
        # Raw well z — offset is applied inside move_to_labware.
        assert zs == [75.0, 75.0, 75.0, 75.0]

    def test_descends_to_action_z_after_approach_per_well(self):
        """scan must emit the descent raw-move per well at
        well.z - measurement_height. A regression dropping this line
        would leave the instrument floating at safe_approach_height."""
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()  # wells at z=75.0
        sensor = _make_sensor(measurement_height=3.0)
        ctx = _mock_context(plate=plate, sensor=sensor)

        scan(ctx, plate="plate_1", instrument="uvvis", method="measure")

        # 4 wells => 4 descent calls.
        assert ctx.board.move.call_count == 4
        descent_zs = [c.args[1][2] for c in ctx.board.move.call_args_list]
        # User-space is positive-down: action_z = well.z - measurement_height
        # = 75 - 3 = 72 (probe held 3 mm above the well).
        assert descent_zs == [72.0, 72.0, 72.0, 72.0]

    def test_descent_move_does_not_pass_travel_z(self):
        """Regression guard: the raw descent after move_to_labware must
        NOT pass a travel_z. If it did, the gantry would lift to
        travel_z before descending to action z — reintroducing the
        original bug where the tip detoured up instead of going
        straight down from safe_approach_height to measurement_height."""
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()
        sensor = _make_sensor(measurement_height=3.0, safe_approach_height=10.0)
        ctx = _mock_context(plate=plate, sensor=sensor)

        scan(ctx, plate="plate_1", instrument="uvvis", method="measure")

        for call in ctx.board.move.call_args_list:
            assert call.kwargs.get("travel_z") is None, (
                f"descent move must not pass travel_z; got {call.kwargs!r}"
            )

    def test_approach_then_descend_then_method_per_well(self):
        """Per-well call order: move_to_labware -> move (descent) -> method."""
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()
        sensor = _make_sensor(measurement_height=3.0)
        ctx = _mock_context(plate=plate, sensor=sensor)
        # Track call order via a shared list.
        order = []
        ctx.board.move_to_labware.side_effect = lambda *a, **k: order.append("approach")
        ctx.board.move.side_effect = lambda *a, **k: order.append("descent")
        sensor.measure = lambda *a, **k: (order.append("measure") or "ok")

        scan(ctx, plate="plate_1", instrument="uvvis", method="measure")

        # Four wells; per-well sequence repeats.
        assert order == ["approach", "descent", "measure"] * 4

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

    def test_method_called_with_no_args(self):
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()
        sensor = _make_sensor()
        ctx = _mock_context(plate=plate, sensor=sensor)

        scan(ctx, plate="plate_1", instrument="uvvis", method="measure")

        assert sensor.call_count == 4

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

        for c in ctx.board.move_to_labware.call_args_list:
            assert c.args[0] == "uvvis"

    def test_logs_normalized_instrument_measurement(self):
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()
        sensor = _make_sensor()
        sensor._return_value = UVVisSpectrum(
            wavelengths=(400.0, 500.0),
            intensities=(0.1, 0.2),
            integration_time_s=0.24,
        )
        ctx = _mock_context(plate=plate, sensor=sensor)
        ctx.data_store = MagicMock()
        ctx.data_store.get_contents.return_value = []
        ctx.data_store.create_experiment.return_value = 101
        ctx.campaign_id = 77

        scan(ctx, plate="plate_1", instrument="uvvis", method="measure")

        assert ctx.data_store.log_measurement.call_count == 4
        measurement = ctx.data_store.log_measurement.call_args_list[0].args[1]
        assert isinstance(measurement, InstrumentMeasurement)

    def test_delay_sleeps_between_wells(self):
        from unittest.mock import patch
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()
        sensor = _make_sensor()
        ctx = _mock_context(plate=plate, sensor=sensor)

        with patch("protocol_engine.commands.scan.time.sleep") as mock_sleep:
            scan(ctx, plate="plate_1", instrument="uvvis", method="measure", delay_s=5.0)
            # 4 wells, delay between wells = 3 sleeps (not before first)
            assert mock_sleep.call_count == 3
            mock_sleep.assert_called_with(5.0)

    def test_no_delay_by_default(self):
        from unittest.mock import patch
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()
        sensor = _make_sensor()
        ctx = _mock_context(plate=plate, sensor=sensor)

        with patch("protocol_engine.commands.scan.time.sleep") as mock_sleep:
            scan(ctx, plate="plate_1", instrument="uvvis", method="measure")
            mock_sleep.assert_not_called()
