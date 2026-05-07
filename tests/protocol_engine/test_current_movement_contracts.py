"""Cross-command movement contracts under the labware-relative model.

These are smoke-level guards that the move/measure/scan/pipette commands
agree on the same motion primitives:

* ``Board.move_to_labware`` travels XY at the gantry's ``safe_z``
  (absolute deck-frame).
* Engaging commands read ``measurement_height`` from the instrument
  config and descend to ``labware.height_mm + measurement_height``
  (relative).
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

from board.board import Board
from deck.labware.labware import Coordinate3D
from deck.labware.well_plate import WellPlate
from protocol_engine.protocol import ProtocolContext


HEIGHT_MM = 14.10


def _instrument(name: str = "tool", measurement_height: float | None = None):
    return SimpleNamespace(
        name=name,
        offset_x=0.0,
        offset_y=0.0,
        depth=0.0,
        measurement_height=measurement_height,
    )


def _plate() -> WellPlate:
    return WellPlate(
        name="plate_1",
        model_name="test_plate",
        length_mm=127.71,
        width_mm=85.43,
        height_mm=HEIGHT_MM,
        rows=1,
        columns=2,
        wells={
            "A1": Coordinate3D(x=10.0, y=20.0, z=HEIGHT_MM),
            "A2": Coordinate3D(x=19.0, y=20.0, z=HEIGHT_MM),
        },
        capacity_ul=200.0,
        working_volume_ul=150.0,
    )


def _ctx(instr_name: str, instr, plate=None):
    board = MagicMock()
    board.instruments = {instr_name: instr}
    deck = MagicMock()
    deck.__getitem__ = MagicMock(return_value=plate or _plate())
    deck.resolve.return_value = Coordinate3D(x=10.0, y=20.0, z=HEIGHT_MM)
    return ProtocolContext(board=board, deck=deck, logger=logging.getLogger("test"))


def test_board_move_to_labware_uses_absolute_safe_z():
    gantry = MagicMock()
    instr = _instrument()
    board = Board(gantry=gantry, instruments={"tool": instr}, safe_z=20.0)

    board.move_to_labware("tool", Coordinate3D(x=10.0, y=20.0, z=HEIGHT_MM))

    gantry.move_to.assert_called_once_with(10.0, 20.0, 20.0, travel_z=20.0)


def test_measure_descends_to_height_mm_plus_relative_offset():
    from protocol_engine.commands.measure import measure

    instr = _instrument(name="uvvis", measurement_height=2.0)
    instr.measure = MagicMock(return_value="ok")
    ctx = _ctx("uvvis", instr)

    measure(ctx, instrument="uvvis", position="plate_1.A1")

    ctx.board.move_to_labware.assert_called_once()
    ctx.board.move.assert_called_once_with("uvvis", (10.0, 20.0, HEIGHT_MM + 2.0))


def test_scan_first_well_descends_to_height_mm_plus_relative_offset():
    from protocol_engine.commands.scan import scan

    instr = _instrument(name="uvvis", measurement_height=1.0)
    instr.measure = MagicMock(return_value="ok")
    ctx = _ctx("uvvis", instr)

    scan(
        ctx,
        plate="plate_1",
        instrument="uvvis",
        method="measure",
        safe_approach_height=10.0,
    )

    # First call to board.move is the descent to approach_z, then to action_z.
    move_calls = ctx.board.move.call_args_list
    assert move_calls[0].args == ("uvvis", (10.0, 20.0, HEIGHT_MM + 10.0))
    assert move_calls[1].args == ("uvvis", (10.0, 20.0, HEIGHT_MM + 1.0))


def test_pipette_aspirate_descends_to_height_mm_plus_relative_offset():
    from protocol_engine.commands.pipette import aspirate

    pipette = _instrument(name="pipette", measurement_height=-2.0)
    pipette.aspirate = MagicMock(return_value="ok")
    ctx = _ctx("pipette", pipette)

    aspirate(ctx, position="plate_1.A1", volume_ul=10.0)

    ctx.board.move_to_labware.assert_called_once()
    ctx.board.move.assert_called_once_with(
        "pipette", (10.0, 20.0, HEIGHT_MM - 2.0),
    )


def test_move_named_park_position_passes_travel_z_unchanged():
    from protocol_engine.commands.move import move

    board = MagicMock()
    board.instruments = {"uvvis": _instrument(name="uvvis")}
    ctx = ProtocolContext(
        board=board,
        deck=MagicMock(),
        positions={"park_position": [0.0, 0.0, 20.0]},
        logger=logging.getLogger("test"),
    )

    move(ctx, instrument="uvvis", position="park_position", travel_z=20.0)

    board.move.assert_called_once_with(
        "uvvis",
        (0.0, 0.0, 20.0),
        travel_z=20.0,
    )
