import pytest
from unittest.mock import MagicMock

from src.instruments.base_instrument import BaseInstrument
from src.board import Board


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
