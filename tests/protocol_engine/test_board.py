import pytest
from unittest.mock import MagicMock

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
