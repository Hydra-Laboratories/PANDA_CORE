"""Deck-origin movement contracts."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

from board.board import Board
from deck.labware.labware import Coordinate3D
from deck.labware.well_plate import WellPlate
from protocol_engine.protocol import ProtocolContext


def _instrument(name: str = "tool", measurement_height: float = 0.0):
    return SimpleNamespace(
        name=name,
        offset_x=0.0,
        offset_y=0.0,
        depth=0.0,
        measurement_height=measurement_height,
        safe_approach_height=measurement_height,
    )


def _plate() -> WellPlate:
    return WellPlate(
        name="plate_1",
        model_name="test_plate",
        length_mm=127.71,
        width_mm=85.43,
        height_mm=14.10,
        rows=1,
        columns=2,
        wells={
            "A1": Coordinate3D(x=10.0, y=20.0, z=75.0),
            "A2": Coordinate3D(x=19.0, y=20.0, z=75.0),
        },
        capacity_ul=200.0,
        working_volume_ul=150.0,
    )


def test_board_move_to_labware_uses_absolute_safe_approach_height():
    gantry = MagicMock()
    instr = _instrument(measurement_height=3.0)
    instr.safe_approach_height = 10.0
    board = Board(gantry=gantry, instruments={"tool": instr})

    board.move_to_labware("tool", Coordinate3D(x=10.0, y=20.0, z=75.0))

    gantry.move_to.assert_called_once_with(10.0, 20.0, 10.0, travel_z=10.0)


def test_measure_uses_absolute_measurement_height():
    from protocol_engine.commands.measure import measure

    instr = _instrument(name="uvvis", measurement_height=3.0)
    instr.measure = MagicMock(return_value="ok")
    board = MagicMock()
    board.instruments = {"uvvis": instr}
    deck = MagicMock()
    deck.resolve.return_value = Coordinate3D(x=10.0, y=20.0, z=75.0)
    ctx = ProtocolContext(board=board, deck=deck, logger=logging.getLogger("test"))

    measure(ctx, instrument="uvvis", position="plate_1.A1")

    board.move_to_labware.assert_called_once_with("uvvis", deck.resolve.return_value)
    board.move.assert_called_once_with("uvvis", (10.0, 20.0, 3.0))


def test_scan_new_travel_names_are_absolute_deck_frame_planes():
    from protocol_engine.commands.scan import scan

    instr = _instrument(name="uvvis", measurement_height=3.0)
    instr.measure = MagicMock(return_value="ok")
    board = MagicMock()
    board.instruments = {"uvvis": instr}
    deck = MagicMock()
    deck.__getitem__ = MagicMock(return_value=_plate())
    ctx = ProtocolContext(
        board=board,
        deck=deck,
        logger=logging.getLogger("test"),
    )

    scan(
        ctx,
        plate="plate_1",
        instrument="uvvis",
        method="measure",
        entry_travel_height=30.0,
        interwell_travel_height=20.0,
    )

    assert ctx.board.move.call_args_list[0].args == ("uvvis", (10.0, 20.0, 30.0))
    assert ctx.board.move.call_args_list[-1].args == ("uvvis", (19.0, 20.0, 20.0))


def test_pipette_aspirate_uses_absolute_measurement_height():
    from protocol_engine.commands.pipette import aspirate

    pipette = _instrument(name="pipette", measurement_height=-5.0)
    pipette.aspirate = MagicMock(return_value="ok")
    board = MagicMock()
    board.instruments = {"pipette": pipette}
    deck = MagicMock()
    deck.resolve.return_value = Coordinate3D(x=10.0, y=20.0, z=75.0)
    ctx = ProtocolContext(board=board, deck=deck, logger=logging.getLogger("test"))

    aspirate(ctx, position="plate_1.A1", volume_ul=10.0)

    board.move_to_labware.assert_called_once_with("pipette", deck.resolve.return_value)
    board.move.assert_called_once_with("pipette", (10.0, 20.0, -5.0))


def test_move_named_park_position_current_contract():
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
