import pytest
from unittest.mock import MagicMock

from src.deck.labware import Coordinate3D
from src.deck.labware.well_plate import WellPlate
from src.instruments.base_instrument import BaseInstrument
from src.instruments.pipette.exceptions import PipetteError
from src.instruments.pipette.models import AspirateResult, MixResult
from src.protocol_engine.board import Board


def _mock_gantry(x=0.0, y=0.0, z=0.0):
    gantry = MagicMock()
    gantry.get_coordinates.return_value = {"x": x, "y": y, "z": z}
    return gantry


def _mock_instrument(name="mock", offset_x=0.0, offset_y=0.0, depth=0.0):
    instr = MagicMock(spec=BaseInstrument)
    instr.name = name
    instr.offset_x = offset_x
    instr.offset_y = offset_y
    instr.depth = depth
    return instr


def _mock_labware(x=-150.0, y=-75.0, z=-10.0):
    """Create a mock labware object with x, y, z deck position."""
    lw = MagicMock()
    lw.x = x
    lw.y = y
    lw.z = z
    return lw


# ─── Construction tests ──────────────────────────────────────────────────────

class TestBoardConstruction:

    def test_creates_with_gantry_only(self):
        gantry = _mock_gantry()
        board = Board(gantry=gantry)
        assert board.gantry is gantry
        assert board.instruments == {}

    def test_creates_with_instruments(self):
        gantry = _mock_gantry()
        pip = _mock_instrument("pipette", offset_x=-10.0, offset_y=5.0)
        fm = _mock_instrument("filmetrics", offset_x=-20.0, offset_y=0.0)
        board = Board(gantry=gantry, instruments={"pipette": pip, "filmetrics": fm})
        assert len(board.instruments) == 2
        assert board.instruments["pipette"] is pip
        assert board.instruments["filmetrics"] is fm

    def test_instruments_defaults_to_empty_dict(self):
        board = Board(gantry=_mock_gantry())
        assert isinstance(board.instruments, dict)
        assert len(board.instruments) == 0

    def test_instruments_dict_is_mutable(self):
        board = Board(gantry=_mock_gantry())
        instr = _mock_instrument("uvvis")
        board.instruments["uvvis"] = instr
        assert board.instruments["uvvis"] is instr

    def test_instrument_offsets_accessible(self):
        pip = _mock_instrument("pipette", offset_x=-15.0, offset_y=3.5, depth=-8.0)
        board = Board(gantry=_mock_gantry(), instruments={"pipette": pip})
        assert board.instruments["pipette"].offset_x == -15.0
        assert board.instruments["pipette"].offset_y == 3.5
        assert board.instruments["pipette"].depth == -8.0


# ─── move() tests ────────────────────────────────────────────────────────────

class TestBoardMove:

    def test_move_by_name_calls_gantry_move_to(self):
        gantry = _mock_gantry()
        pip = _mock_instrument("pipette", offset_x=-10.0, offset_y=5.0, depth=-2.0)
        board = Board(gantry=gantry, instruments={"pipette": pip})

        board.move("pipette", (-100.0, -50.0, -20.0))

        gantry.move_to.assert_called_once_with(-90.0, -55.0, -18.0)

    def test_move_by_instance_calls_gantry_move_to(self):
        gantry = _mock_gantry()
        pip = _mock_instrument("pipette", offset_x=-10.0, offset_y=5.0, depth=-2.0)
        board = Board(gantry=gantry, instruments={"pipette": pip})

        board.move(pip, (-100.0, -50.0, -20.0))

        gantry.move_to.assert_called_once_with(-90.0, -55.0, -18.0)

    def test_move_zero_offset_passes_position_through(self):
        gantry = _mock_gantry()
        instr = _mock_instrument("router", offset_x=0.0, offset_y=0.0, depth=0.0)
        board = Board(gantry=gantry, instruments={"router": instr})

        board.move("router", (-200.0, -100.0, -10.0))

        gantry.move_to.assert_called_once_with(-200.0, -100.0, -10.0)

    def test_move_positive_offset(self):
        """Instrument mounted to the right (+x) of the router."""
        gantry = _mock_gantry()
        instr = _mock_instrument("sensor", offset_x=15.0, offset_y=10.0, depth=3.0)
        board = Board(gantry=gantry, instruments={"sensor": instr})

        board.move("sensor", (-50.0, -30.0, -5.0))

        # gantry_x = -50 - 15 = -65, gantry_y = -30 - 10 = -40, gantry_z = -5 - 3 = -8
        gantry.move_to.assert_called_once_with(-65.0, -40.0, -8.0)

    def test_move_unknown_instrument_raises(self):
        board = Board(gantry=_mock_gantry())
        with pytest.raises(KeyError, match="Unknown instrument 'nope'"):
            board.move("nope", (0.0, 0.0, 0.0))

    def test_move_does_not_call_other_gantry_methods(self):
        gantry = _mock_gantry()
        instr = _mock_instrument("pipette")
        board = Board(gantry=gantry, instruments={"pipette": instr})

        board.move("pipette", (0.0, 0.0, 0.0))

        gantry.move_to.assert_called_once()
        gantry.get_coordinates.assert_not_called()

    def test_move_accepts_labware_object(self):
        gantry = _mock_gantry()
        instr = _mock_instrument("pipette", offset_x=-10.0, offset_y=5.0, depth=-2.0)
        board = Board(gantry=gantry, instruments={"pipette": instr})
        lw = _mock_labware(x=-150.0, y=-75.0, z=-10.0)

        board.move("pipette", lw)

        gantry.move_to.assert_called_once_with(-140.0, -80.0, -8.0)


# ─── object_position() tests ─────────────────────────────────────────────────

class TestBoardObjectPosition:

    def test_instrument_position_by_name(self):
        gantry = _mock_gantry(x=-100.0, y=-50.0, z=-10.0)
        pip = _mock_instrument("pipette", offset_x=-10.0, offset_y=5.0)
        board = Board(gantry=gantry, instruments={"pipette": pip})

        pos = board.object_position("pipette")

        assert pos == pytest.approx((-110.0, -45.0))

    def test_instrument_position_by_instance(self):
        gantry = _mock_gantry(x=-100.0, y=-50.0, z=-10.0)
        pip = _mock_instrument("pipette", offset_x=-10.0, offset_y=5.0)
        board = Board(gantry=gantry, instruments={"pipette": pip})

        pos = board.object_position(pip)

        assert pos == pytest.approx((-110.0, -45.0))

    def test_instrument_position_zero_offset(self):
        gantry = _mock_gantry(x=-200.0, y=-80.0)
        instr = _mock_instrument("router", offset_x=0.0, offset_y=0.0)
        board = Board(gantry=gantry, instruments={"router": instr})

        pos = board.object_position("router")

        assert pos == pytest.approx((-200.0, -80.0))

    def test_instrument_position_reads_gantry_coordinates(self):
        gantry = _mock_gantry(x=-50.0, y=-25.0)
        instr = _mock_instrument("sensor")
        board = Board(gantry=gantry, instruments={"sensor": instr})

        board.object_position("sensor")

        gantry.get_coordinates.assert_called_once()

    def test_labware_position_from_xy_attributes(self):
        gantry = _mock_gantry()
        board = Board(gantry=gantry)

        labware = MagicMock()
        labware.x = -150.0
        labware.y = -75.0

        pos = board.object_position(labware)

        assert pos == pytest.approx((-150.0, -75.0))
        gantry.get_coordinates.assert_not_called()

    def test_unknown_instrument_name_raises(self):
        board = Board(gantry=_mock_gantry())
        with pytest.raises(KeyError, match="Unknown instrument 'nope'"):
            board.object_position("nope")


# ─── Pipette helper tests ────────────────────────────────────────────────────

def _mock_pipette(offset_x=-10.0, offset_y=5.0, depth=-2.0):
    """Create a MagicMock that behaves like a Pipette instrument."""
    pip = MagicMock()
    pip.name = "pipette"
    pip.offset_x = offset_x
    pip.offset_y = offset_y
    pip.depth = depth
    pip.aspirate.return_value = AspirateResult(success=True, volume_ul=100.0, position_mm=46.98)
    pip.dispense.return_value = AspirateResult(success=True, volume_ul=100.0, position_mm=36.0)
    pip.mix.return_value = MixResult(success=True, volume_ul=50.0, repetitions=3)
    return pip


def _board_with_pipette(offset_x=-10.0, offset_y=5.0, depth=-2.0):
    """Create a Board with a mock gantry and a mock pipette."""
    gantry = _mock_gantry()
    pip = _mock_pipette(offset_x=offset_x, offset_y=offset_y, depth=depth)
    board = Board(gantry=gantry, instruments={"pipette": pip})
    return board, gantry, pip


class TestBoardPipetteNoInstrument:
    """All pipette helpers must raise PipetteError when no pipette is registered."""

    def test_aspirate_raises(self):
        board = Board(gantry=_mock_gantry())
        with pytest.raises(PipetteError, match="No pipette"):
            board.aspirate((0.0, 0.0, 0.0), 100.0)

    def test_dispense_raises(self):
        board = Board(gantry=_mock_gantry())
        with pytest.raises(PipetteError, match="No pipette"):
            board.dispense((0.0, 0.0, 0.0), 100.0)

    def test_blowout_raises(self):
        board = Board(gantry=_mock_gantry())
        with pytest.raises(PipetteError, match="No pipette"):
            board.blowout((0.0, 0.0, 0.0))

    def test_mix_raises(self):
        board = Board(gantry=_mock_gantry())
        with pytest.raises(PipetteError, match="No pipette"):
            board.mix((0.0, 0.0, 0.0), 50.0)

    def test_pick_up_tip_raises(self):
        board = Board(gantry=_mock_gantry())
        with pytest.raises(PipetteError, match="No pipette"):
            board.pick_up_tip((0.0, 0.0, 0.0))

    def test_drop_tip_raises(self):
        board = Board(gantry=_mock_gantry())
        with pytest.raises(PipetteError, match="No pipette"):
            board.drop_tip((0.0, 0.0, 0.0))


class TestBoardAspirate:

    def test_moves_then_aspirates(self):
        board, gantry, pip = _board_with_pipette()
        result = board.aspirate((-100.0, -50.0, -20.0), 100.0)

        gantry.move_to.assert_called_once_with(-90.0, -55.0, -18.0)
        pip.aspirate.assert_called_once_with(100.0, 50.0)
        assert result.success is True
        assert result.volume_ul == 100.0

    def test_custom_speed(self):
        board, _, pip = _board_with_pipette()
        board.aspirate((-100.0, -50.0, -20.0), 75.0, speed=25.0)
        pip.aspirate.assert_called_once_with(75.0, 25.0)

    def test_move_before_aspirate(self):
        """Gantry move must happen before the pipette command."""
        board, gantry, pip = _board_with_pipette()
        call_order = []
        gantry.move_to.side_effect = lambda *a: call_order.append("move")
        pip.aspirate.side_effect = lambda *a: call_order.append("aspirate")
        board.aspirate((-100.0, -50.0, -20.0), 100.0)
        assert call_order == ["move", "aspirate"]

    def test_accepts_labware_object(self):
        board, gantry, pip = _board_with_pipette()
        lw = _mock_labware(x=-100.0, y=-50.0, z=-20.0)
        board.aspirate(lw, 100.0)

        gantry.move_to.assert_called_once_with(-90.0, -55.0, -18.0)
        pip.aspirate.assert_called_once_with(100.0, 50.0)


class TestBoardDispense:

    def test_moves_then_dispenses(self):
        board, gantry, pip = _board_with_pipette()
        result = board.dispense((-100.0, -50.0, -20.0), 100.0)

        gantry.move_to.assert_called_once_with(-90.0, -55.0, -18.0)
        pip.dispense.assert_called_once_with(100.0, 50.0)
        assert result.success is True

    def test_custom_speed(self):
        board, _, pip = _board_with_pipette()
        board.dispense((-100.0, -50.0, -20.0), 80.0, speed=30.0)
        pip.dispense.assert_called_once_with(80.0, 30.0)

    def test_accepts_labware_object(self):
        board, gantry, pip = _board_with_pipette()
        lw = _mock_labware(x=-100.0, y=-50.0, z=-20.0)
        board.dispense(lw, 100.0)

        gantry.move_to.assert_called_once_with(-90.0, -55.0, -18.0)
        pip.dispense.assert_called_once_with(100.0, 50.0)


class TestBoardBlowout:

    def test_moves_then_blows_out(self):
        board, gantry, pip = _board_with_pipette()
        board.blowout((-100.0, -50.0, -20.0))

        gantry.move_to.assert_called_once_with(-90.0, -55.0, -18.0)
        pip.blowout.assert_called_once_with(50.0)

    def test_custom_speed(self):
        board, _, pip = _board_with_pipette()
        board.blowout((-100.0, -50.0, -20.0), speed=25.0)
        pip.blowout.assert_called_once_with(25.0)

    def test_accepts_labware_object(self):
        board, gantry, pip = _board_with_pipette()
        lw = _mock_labware(x=-100.0, y=-50.0, z=-20.0)
        board.blowout(lw)

        gantry.move_to.assert_called_once_with(-90.0, -55.0, -18.0)
        pip.blowout.assert_called_once_with(50.0)


class TestBoardMix:

    def test_moves_then_mixes(self):
        board, gantry, pip = _board_with_pipette()
        result = board.mix((-100.0, -50.0, -20.0), 50.0, repetitions=5)

        gantry.move_to.assert_called_once_with(-90.0, -55.0, -18.0)
        pip.mix.assert_called_once_with(50.0, 5, 50.0)
        assert result.success is True

    def test_default_repetitions(self):
        board, _, pip = _board_with_pipette()
        board.mix((-100.0, -50.0, -20.0), 50.0)
        pip.mix.assert_called_once_with(50.0, 3, 50.0)

    def test_custom_speed(self):
        board, _, pip = _board_with_pipette()
        board.mix((-100.0, -50.0, -20.0), 50.0, speed=20.0)
        pip.mix.assert_called_once_with(50.0, 3, 20.0)

    def test_accepts_labware_object(self):
        board, gantry, pip = _board_with_pipette()
        lw = _mock_labware(x=-100.0, y=-50.0, z=-20.0)
        board.mix(lw, 50.0, repetitions=5)

        gantry.move_to.assert_called_once_with(-90.0, -55.0, -18.0)
        pip.mix.assert_called_once_with(50.0, 5, 50.0)


class TestBoardPickUpTip:

    def test_moves_then_picks_up(self):
        board, gantry, pip = _board_with_pipette()
        board.pick_up_tip((-100.0, -50.0, -20.0))

        gantry.move_to.assert_called_once_with(-90.0, -55.0, -18.0)
        pip.pick_up_tip.assert_called_once_with(50.0)

    def test_custom_speed(self):
        board, _, pip = _board_with_pipette()
        board.pick_up_tip((-100.0, -50.0, -20.0), speed=10.0)
        pip.pick_up_tip.assert_called_once_with(10.0)

    def test_accepts_labware_object(self):
        board, gantry, pip = _board_with_pipette()
        lw = _mock_labware(x=-100.0, y=-50.0, z=-20.0)
        board.pick_up_tip(lw)

        gantry.move_to.assert_called_once_with(-90.0, -55.0, -18.0)
        pip.pick_up_tip.assert_called_once_with(50.0)


class TestBoardDropTip:

    def test_moves_then_drops(self):
        board, gantry, pip = _board_with_pipette()
        board.drop_tip((-100.0, -50.0, -20.0))

        gantry.move_to.assert_called_once_with(-90.0, -55.0, -18.0)
        pip.drop_tip.assert_called_once_with(50.0)

    def test_custom_speed(self):
        board, _, pip = _board_with_pipette()
        board.drop_tip((-100.0, -50.0, -20.0), speed=10.0)
        pip.drop_tip.assert_called_once_with(10.0)

    def test_accepts_labware_object(self):
        board, gantry, pip = _board_with_pipette()
        lw = _mock_labware(x=-100.0, y=-50.0, z=-20.0)
        board.drop_tip(lw)

        gantry.move_to.assert_called_once_with(-90.0, -55.0, -18.0)
        pip.drop_tip.assert_called_once_with(50.0)


# ─── scan() tests ───────────────────────────────────────────────────────────

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


class TestBoardScan:

    def test_scan_moves_instrument_to_each_well(self):
        """scan moves the instrument over each well before calling method."""
        gantry = _mock_gantry()
        sensor = _make_sensor()
        board = Board(gantry=gantry, instruments={"sensor": sensor})
        plate = _make_2x2_plate()

        board.scan(plate, sensor.measure)

        assert gantry.move_to.call_count == 4

    def test_scan_moves_to_correct_coordinates(self):
        """scan sends the gantry to each well's position (adjusted for offset)."""
        gantry = _mock_gantry()
        sensor = _make_sensor(offset_x=-5.0, offset_y=2.0, depth=-1.0)
        board = Board(gantry=gantry, instruments={"sensor": sensor})
        plate = _make_2x2_plate()

        board.scan(plate, sensor.measure)

        # A1 at (0, 0, -5): gantry = (0 - -5, 0 - 2, -5 - -1) = (5, -2, -4)
        # A2 at (10, 0, -5): gantry = (15, -2, -4)
        # B1 at (0, -8, -5): gantry = (5, -10, -4)
        # B2 at (10, -8, -5): gantry = (15, -10, -4)
        calls = [c.args for c in gantry.move_to.call_args_list]
        assert calls == [
            (5.0, -2.0, -4.0),
            (15.0, -2.0, -4.0),
            (5.0, -10.0, -4.0),
            (15.0, -10.0, -4.0),
        ]

    def test_scan_moves_before_calling_method(self):
        """For each well, the gantry moves first, then the method fires."""
        gantry = _mock_gantry()
        sensor = _make_sensor()
        board = Board(gantry=gantry, instruments={"sensor": sensor})
        plate = _make_2x2_plate()
        call_order = []

        gantry.move_to.side_effect = lambda *a: call_order.append("move")
        original_measure = sensor.measure.__func__

        def tracking_measure(self_inner, p):
            call_order.append("method")
            return original_measure(self_inner, p)

        import types
        sensor.measure = types.MethodType(tracking_measure, sensor)
        board.scan(plate, sensor.measure)
        assert call_order == ["move", "method"] * 4

    def test_scan_calls_method_once_per_well(self):
        """scan calls the method exactly once for each well."""
        gantry = _mock_gantry()
        sensor = _make_sensor()
        board = Board(gantry=gantry, instruments={"sensor": sensor})
        plate = _make_2x2_plate()

        board.scan(plate, sensor.measure)
        assert sensor.call_count == 4

    def test_scan_returns_dict_of_bool_per_well(self):
        """scan returns a Dict[str, bool] mapping each well ID to its result."""
        gantry = _mock_gantry()
        sensor = _make_sensor()
        board = Board(gantry=gantry, instruments={"sensor": sensor})
        plate = _make_2x2_plate()

        result = board.scan(plate, sensor.measure)
        assert isinstance(result, dict)
        assert set(result.keys()) == {"A1", "A2", "B1", "B2"}
        assert all(v is True for v in result.values())

    def test_scan_captures_false_results(self):
        """scan faithfully records False returns from the method."""
        gantry = _mock_gantry()
        sensor = _make_sensor()
        sensor._return_value = False
        board = Board(gantry=gantry, instruments={"sensor": sensor})
        plate = _make_2x2_plate()

        result = board.scan(plate, sensor.measure)
        assert all(v is False for v in result.values())

    def test_scan_visits_wells_in_row_major_order(self):
        """scan iterates A1, A2, A3, B1, B2, B3 (row-major)."""
        gantry = _mock_gantry()
        sensor = _make_sensor()
        board = Board(gantry=gantry, instruments={"sensor": sensor})
        plate = _make_2x3_plate()

        # Track move order via gantry calls — A1(0,0), A2(10,0), A3(20,0), B1(0,-8), ...
        board.scan(plate, sensor.measure)
        xs = [c.args[0] for c in gantry.move_to.call_args_list]
        assert xs == [0.0, 10.0, 20.0, 0.0, 10.0, 20.0]

    def test_scan_passes_plate_to_method(self):
        """The method receives the wellplate instance."""
        gantry = _mock_gantry()
        sensor = _make_sensor()
        board = Board(gantry=gantry, instruments={"sensor": sensor})
        plate = _make_2x2_plate()

        board.scan(plate, sensor.measure)
        assert all(p is plate for p in sensor.received_plates)

    def test_scan_propagates_exceptions(self):
        """If the method raises, scan does not swallow the exception."""
        import types
        gantry = _mock_gantry()
        sensor = _make_sensor()
        board = Board(gantry=gantry, instruments={"sensor": sensor})
        plate = _make_2x2_plate()

        def exploding_measure(self_inner, p):
            raise RuntimeError("sensor failure")

        sensor.measure = types.MethodType(exploding_measure, sensor)
        with pytest.raises(RuntimeError, match="sensor failure"):
            board.scan(plate, sensor.measure)

    def test_scan_rejects_unbound_callable(self):
        """scan raises AttributeError for a plain function (no __self__)."""
        board = Board(gantry=_mock_gantry())
        plate = _make_2x2_plate()

        def loose_func(p):
            return True

        with pytest.raises(AttributeError, match="bound method"):
            board.scan(plate, loose_func)

    def test_scan_applies_measurement_height(self):
        """scan adjusts the z coordinate by the instrument's measurement_height."""
        gantry = _mock_gantry()
        # depth=-1.0, measurement_height=3.0
        sensor = _make_sensor(offset_x=0.0, offset_y=0.0, depth=-1.0, measurement_height=3.0)
        board = Board(gantry=gantry, instruments={"sensor": sensor})
        plate = _make_2x2_plate()  # wells at z=-5.0

        board.scan(plate, sensor.measure)

        # Well z=-5.0, measurement_height=+3.0 → target z=-2.0
        # Then Board.move subtracts depth: gantry_z = -2.0 - (-1.0) = -1.0
        zs = [c.args[2] for c in gantry.move_to.call_args_list]
        assert zs == [-1.0, -1.0, -1.0, -1.0]

    def test_scan_zero_measurement_height_unchanged(self):
        """measurement_height=0 leaves z unchanged (default behavior)."""
        gantry = _mock_gantry()
        sensor = _make_sensor(offset_x=0.0, offset_y=0.0, depth=0.0, measurement_height=0.0)
        board = Board(gantry=gantry, instruments={"sensor": sensor})
        plate = _make_2x2_plate()  # wells at z=-5.0

        board.scan(plate, sensor.measure)

        zs = [c.args[2] for c in gantry.move_to.call_args_list]
        assert zs == [-5.0, -5.0, -5.0, -5.0]

    def test_scan_rejects_non_instrument_bound_method(self):
        """scan raises TypeError if __self__ is not a BaseInstrument."""
        board = Board(gantry=_mock_gantry())
        plate = _make_2x2_plate()

        class NotAnInstrument:
            def measure(self, plate):
                return True

        obj = NotAnInstrument()
        with pytest.raises(TypeError, match="BaseInstrument"):
            board.scan(plate, obj.measure)
