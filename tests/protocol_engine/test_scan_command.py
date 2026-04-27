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

    def test_scans_selected_wells_in_requested_order(self):
        from protocol_engine.commands.scan import scan

        plate = _make_2x3_plate()
        sensor = _make_sensor()
        ctx = _mock_context(plate=plate, sensor=sensor)

        result = scan(
            ctx,
            plate="plate_2",
            instrument="uvvis",
            method="measure",
            wells=["B2", "A1"],
        )

        assert list(result) == ["B2", "A1"]
        move_calls = ctx.board.move_to_labware.call_args_list
        positions = [c.args[1] for c in move_calls]
        assert [(p.x, p.y) for p in positions] == [(10.0, 8.0), (0.0, 0.0)]
        last_move = ctx.board.move.call_args_list[-1]
        assert last_move.args[1] == (0.0, 0.0, 75.0)

    def test_unknown_selected_well_raises(self):
        from protocol_engine.commands.scan import scan

        plate = _make_2x3_plate()
        sensor = _make_sensor()
        ctx = _mock_context(plate=plate, sensor=sensor)

        with pytest.raises(ProtocolExecutionError, match="Unknown scan wells"):
            scan(
                ctx,
                plate="plate_2",
                instrument="uvvis",
                method="measure",
                wells=["Z99"],
            )

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
        sensor = _make_sensor(measurement_height=3.0, safe_approach_height=10.0)
        ctx = _mock_context(plate=plate, sensor=sensor)

        scan(ctx, plate="plate_1", instrument="uvvis", method="measure")

        # 4 wells => 4 descent calls + 1 retract after last well.
        assert ctx.board.move.call_count == 5
        move_zs = [c.args[1][2] for c in ctx.board.move.call_args_list]
        # First 4: action_z = 75 - 3 = 72 (descent to measurement_height).
        # Last: approach_z = 75 - 10 = 65 (retract to safe_approach_height).
        assert move_zs == [72.0, 72.0, 72.0, 72.0, 65.0]

    def test_protocol_safe_approach_height_override_is_used_for_every_well(self):
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()  # wells at z=75.0
        sensor = _make_sensor(measurement_height=3.0, safe_approach_height=10.0)
        ctx = _mock_context(plate=plate, sensor=sensor)

        scan(
            ctx,
            plate="plate_1",
            instrument="uvvis",
            method="measure",
            safe_approach_height=20.0,
        )

        ctx.board.move_to_labware.assert_not_called()
        # 4 wells => 4 approach calls + 4 descent calls + 1 final retract.
        assert ctx.board.move.call_count == 9
        move_zs = [c.args[1][2] for c in ctx.board.move.call_args_list]
        assert move_zs == [20.0, 72.0, 20.0, 72.0, 20.0, 72.0, 20.0, 72.0, 20.0]
        approach_calls = ctx.board.move.call_args_list[:-1:2]
        for call in approach_calls:
            assert call.kwargs["travel_z"] == 20.0

    def test_final_retract_uses_protocol_safe_approach_height_override(self):
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()  # wells at z=75.0
        sensor = _make_sensor(measurement_height=3.0, safe_approach_height=10.0)
        ctx = _mock_context(plate=plate, sensor=sensor)

        scan(
            ctx,
            plate="plate_1",
            instrument="uvvis",
            method="measure",
            safe_approach_height=20.0,
        )

        last_move = ctx.board.move.call_args_list[-1]
        instr_name, position = last_move.args
        assert instr_name == "uvvis"
        assert position == (10.0, 8.0, 20.0)
        assert last_move.kwargs == {}

    def test_entry_travel_z_applies_only_to_first_well(self):
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()  # wells at z=75.0
        sensor = _make_sensor(measurement_height=3.0, safe_approach_height=10.0)
        ctx = _mock_context(plate=plate, sensor=sensor)

        scan(
            ctx,
            plate="plate_1",
            instrument="uvvis",
            method="measure",
            entry_travel_z=30.0,
            safe_approach_height=20.0,
        )

        move_zs = [c.args[1][2] for c in ctx.board.move.call_args_list]
        assert move_zs == [30.0, 72.0, 20.0, 72.0, 20.0, 72.0, 20.0, 72.0, 20.0]

        first_move = ctx.board.move.call_args_list[0]
        assert first_move.kwargs == {"travel_z": 30.0}
        later_approaches = ctx.board.move.call_args_list[2:-1:2]
        for call in later_approaches:
            assert call.kwargs == {"travel_z": 20.0}

    def test_descent_and_retract_moves_do_not_pass_travel_z(self):
        """Regression guard: raw moves (descent per well + final retract)
        must NOT pass a travel_z. If they did, the gantry would lift to
        travel_z before moving — reintroducing the original detour bug."""
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()
        sensor = _make_sensor(measurement_height=3.0, safe_approach_height=10.0)
        ctx = _mock_context(plate=plate, sensor=sensor)

        scan(ctx, plate="plate_1", instrument="uvvis", method="measure")

        for call in ctx.board.move.call_args_list:
            assert call.kwargs.get("travel_z") is None, (
                f"raw move must not pass travel_z; got {call.kwargs!r}"
            )

    def test_approach_then_descend_then_method_per_well(self):
        """Per-well call order: move_to_labware -> move (descent) -> method,
        followed by a final retract move after the last well."""
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()
        sensor = _make_sensor(measurement_height=3.0)
        ctx = _mock_context(plate=plate, sensor=sensor)
        order = []
        ctx.board.move_to_labware.side_effect = lambda *a, **k: order.append("approach")
        ctx.board.move.side_effect = lambda *a, **k: order.append("move")
        sensor.measure = lambda *a, **k: (order.append("measure") or "ok")

        scan(ctx, plate="plate_1", instrument="uvvis", method="measure")

        assert order == ["approach", "move", "measure"] * 4 + ["move"]

    def test_retracts_to_safe_approach_height_after_last_well(self):
        """After the last measurement, the gantry must retract to
        safe_approach_height above the last well."""
        from protocol_engine.commands.scan import scan

        plate = _make_2x2_plate()  # wells at z=75.0
        sensor = _make_sensor(measurement_height=3.0, safe_approach_height=10.0)
        ctx = _mock_context(plate=plate, sensor=sensor)

        scan(ctx, plate="plate_1", instrument="uvvis", method="measure")

        last_move = ctx.board.move.call_args_list[-1]
        instr_name, position = last_move.args
        assert instr_name == "uvvis"
        # Last well in row-major order is B2 at (10, 8, 75).
        # Retract z = 75 - 10 = 65.
        assert position == (10.0, 8.0, 65.0)

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
