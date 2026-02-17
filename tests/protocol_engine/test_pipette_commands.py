"""Tests for pipette protocol commands (aspirate, dispense, blowout, mix, pick_up_tip, drop_tip)."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, call

import pytest

from src.deck.labware.labware import Coordinate3D
from src.protocol_engine.errors import ProtocolExecutionError
from src.protocol_engine.protocol import ProtocolContext


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _mock_context(
    resolve_return: Coordinate3D | None = None,
    has_pipette: bool = True,
) -> ProtocolContext:
    coord = resolve_return or Coordinate3D(x=-100.0, y=-50.0, z=-20.0)

    board = MagicMock()
    deck = MagicMock()
    deck.resolve.return_value = coord

    if has_pipette:
        pipette = MagicMock()
        pipette.aspirate.return_value = MagicMock(success=True, volume_ul=100.0)
        pipette.dispense.return_value = MagicMock(success=True, volume_ul=100.0)
        pipette.mix.return_value = MagicMock(success=True, volume_ul=50.0, repetitions=3)
        board.instruments = {"pipette": pipette}
    else:
        board.instruments = {}

    return ProtocolContext(
        board=board,
        deck=deck,
        logger=logging.getLogger("test_pipette_commands"),
    )


def _get_pipette(ctx: ProtocolContext) -> MagicMock:
    return ctx.board.instruments["pipette"]


# ─── aspirate tests ──────────────────────────────────────────────────────────


class TestAspirateCommand:

    def test_resolves_position_via_deck(self):
        from src.protocol_engine.commands.pipette import aspirate

        ctx = _mock_context()
        aspirate(ctx, position="plate_1.A1", volume_ul=100.0)
        ctx.deck.resolve.assert_called_once_with("plate_1.A1")

    def test_moves_then_aspirates(self):
        from src.protocol_engine.commands.pipette import aspirate

        ctx = _mock_context()
        call_order = []
        ctx.board.move.side_effect = lambda *a, **kw: call_order.append("move")
        _get_pipette(ctx).aspirate.side_effect = lambda *a: call_order.append("aspirate")

        aspirate(ctx, position="plate_1.A1", volume_ul=100.0)
        assert call_order == ["move", "aspirate"]

    def test_passes_volume_and_speed(self):
        from src.protocol_engine.commands.pipette import aspirate

        ctx = _mock_context()
        aspirate(ctx, position="plate_1.A1", volume_ul=75.0, speed=25.0)
        _get_pipette(ctx).aspirate.assert_called_once_with(75.0, 25.0)

    def test_default_speed(self):
        from src.protocol_engine.commands.pipette import aspirate

        ctx = _mock_context()
        aspirate(ctx, position="plate_1.A1", volume_ul=100.0)
        _get_pipette(ctx).aspirate.assert_called_once_with(100.0, 50.0)

    def test_moves_pipette_to_resolved_coord(self):
        from src.protocol_engine.commands.pipette import aspirate

        coord = Coordinate3D(x=-10.0, y=-20.0, z=-5.0)
        ctx = _mock_context(resolve_return=coord)
        aspirate(ctx, position="plate_1.A1", volume_ul=100.0)
        ctx.board.move.assert_called_once_with("pipette", coord)

    def test_raises_when_no_pipette(self):
        from src.protocol_engine.commands.pipette import aspirate

        ctx = _mock_context(has_pipette=False)
        with pytest.raises(ProtocolExecutionError, match="[Nn]o pipette"):
            aspirate(ctx, position="plate_1.A1", volume_ul=100.0)


# ─── dispense tests ──────────────────────────────────────────────────────────


class TestDispenseCommand:

    def test_resolves_position_via_deck(self):
        from src.protocol_engine.commands.pipette import dispense

        ctx = _mock_context()
        dispense(ctx, position="plate_1.A1", volume_ul=100.0)
        ctx.deck.resolve.assert_called_once_with("plate_1.A1")

    def test_moves_then_dispenses(self):
        from src.protocol_engine.commands.pipette import dispense

        ctx = _mock_context()
        call_order = []
        ctx.board.move.side_effect = lambda *a, **kw: call_order.append("move")
        _get_pipette(ctx).dispense.side_effect = lambda *a: call_order.append("dispense")

        dispense(ctx, position="plate_1.A1", volume_ul=100.0)
        assert call_order == ["move", "dispense"]

    def test_passes_volume_and_speed(self):
        from src.protocol_engine.commands.pipette import dispense

        ctx = _mock_context()
        dispense(ctx, position="plate_1.A1", volume_ul=80.0, speed=30.0)
        _get_pipette(ctx).dispense.assert_called_once_with(80.0, 30.0)

    def test_default_speed(self):
        from src.protocol_engine.commands.pipette import dispense

        ctx = _mock_context()
        dispense(ctx, position="plate_1.A1", volume_ul=100.0)
        _get_pipette(ctx).dispense.assert_called_once_with(100.0, 50.0)

    def test_raises_when_no_pipette(self):
        from src.protocol_engine.commands.pipette import dispense

        ctx = _mock_context(has_pipette=False)
        with pytest.raises(ProtocolExecutionError, match="[Nn]o pipette"):
            dispense(ctx, position="plate_1.A1", volume_ul=100.0)


# ─── blowout tests ───────────────────────────────────────────────────────────


class TestBlowoutCommand:

    def test_resolves_position_via_deck(self):
        from src.protocol_engine.commands.pipette import blowout

        ctx = _mock_context()
        blowout(ctx, position="plate_1.A1")
        ctx.deck.resolve.assert_called_once_with("plate_1.A1")

    def test_moves_then_blows_out(self):
        from src.protocol_engine.commands.pipette import blowout

        ctx = _mock_context()
        call_order = []
        ctx.board.move.side_effect = lambda *a, **kw: call_order.append("move")
        _get_pipette(ctx).blowout.side_effect = lambda *a: call_order.append("blowout")

        blowout(ctx, position="plate_1.A1")
        assert call_order == ["move", "blowout"]

    def test_passes_speed(self):
        from src.protocol_engine.commands.pipette import blowout

        ctx = _mock_context()
        blowout(ctx, position="plate_1.A1", speed=25.0)
        _get_pipette(ctx).blowout.assert_called_once_with(25.0)

    def test_default_speed(self):
        from src.protocol_engine.commands.pipette import blowout

        ctx = _mock_context()
        blowout(ctx, position="plate_1.A1")
        _get_pipette(ctx).blowout.assert_called_once_with(50.0)

    def test_raises_when_no_pipette(self):
        from src.protocol_engine.commands.pipette import blowout

        ctx = _mock_context(has_pipette=False)
        with pytest.raises(ProtocolExecutionError, match="[Nn]o pipette"):
            blowout(ctx, position="plate_1.A1")


# ─── mix tests ────────────────────────────────────────────────────────────────


class TestMixCommand:

    def test_resolves_position_via_deck(self):
        from src.protocol_engine.commands.pipette import mix

        ctx = _mock_context()
        mix(ctx, position="plate_1.A1", volume_ul=50.0)
        ctx.deck.resolve.assert_called_once_with("plate_1.A1")

    def test_moves_then_mixes(self):
        from src.protocol_engine.commands.pipette import mix

        ctx = _mock_context()
        call_order = []
        ctx.board.move.side_effect = lambda *a, **kw: call_order.append("move")
        _get_pipette(ctx).mix.side_effect = lambda *a: call_order.append("mix")

        mix(ctx, position="plate_1.A1", volume_ul=50.0)
        assert call_order == ["move", "mix"]

    def test_passes_volume_repetitions_and_speed(self):
        from src.protocol_engine.commands.pipette import mix

        ctx = _mock_context()
        mix(ctx, position="plate_1.A1", volume_ul=50.0, repetitions=5, speed=20.0)
        _get_pipette(ctx).mix.assert_called_once_with(50.0, 5, 20.0)

    def test_default_repetitions_and_speed(self):
        from src.protocol_engine.commands.pipette import mix

        ctx = _mock_context()
        mix(ctx, position="plate_1.A1", volume_ul=50.0)
        _get_pipette(ctx).mix.assert_called_once_with(50.0, 3, 50.0)

    def test_raises_when_no_pipette(self):
        from src.protocol_engine.commands.pipette import mix

        ctx = _mock_context(has_pipette=False)
        with pytest.raises(ProtocolExecutionError, match="[Nn]o pipette"):
            mix(ctx, position="plate_1.A1", volume_ul=50.0)


# ─── pick_up_tip tests ───────────────────────────────────────────────────────


class TestPickUpTipCommand:

    def test_resolves_position_via_deck(self):
        from src.protocol_engine.commands.pipette import pick_up_tip

        ctx = _mock_context()
        pick_up_tip(ctx, position="tiprack_1.A1")
        ctx.deck.resolve.assert_called_once_with("tiprack_1.A1")

    def test_moves_then_picks_up(self):
        from src.protocol_engine.commands.pipette import pick_up_tip

        ctx = _mock_context()
        call_order = []
        ctx.board.move.side_effect = lambda *a, **kw: call_order.append("move")
        _get_pipette(ctx).pick_up_tip.side_effect = lambda *a: call_order.append("pick_up_tip")

        pick_up_tip(ctx, position="tiprack_1.A1")
        assert call_order == ["move", "pick_up_tip"]

    def test_passes_speed(self):
        from src.protocol_engine.commands.pipette import pick_up_tip

        ctx = _mock_context()
        pick_up_tip(ctx, position="tiprack_1.A1", speed=10.0)
        _get_pipette(ctx).pick_up_tip.assert_called_once_with(10.0)

    def test_default_speed(self):
        from src.protocol_engine.commands.pipette import pick_up_tip

        ctx = _mock_context()
        pick_up_tip(ctx, position="tiprack_1.A1")
        _get_pipette(ctx).pick_up_tip.assert_called_once_with(50.0)

    def test_raises_when_no_pipette(self):
        from src.protocol_engine.commands.pipette import pick_up_tip

        ctx = _mock_context(has_pipette=False)
        with pytest.raises(ProtocolExecutionError, match="[Nn]o pipette"):
            pick_up_tip(ctx, position="tiprack_1.A1")


# ─── drop_tip tests ──────────────────────────────────────────────────────────


class TestDropTipCommand:

    def test_resolves_position_via_deck(self):
        from src.protocol_engine.commands.pipette import drop_tip

        ctx = _mock_context()
        drop_tip(ctx, position="waste_1")
        ctx.deck.resolve.assert_called_once_with("waste_1")

    def test_moves_then_drops(self):
        from src.protocol_engine.commands.pipette import drop_tip

        ctx = _mock_context()
        call_order = []
        ctx.board.move.side_effect = lambda *a, **kw: call_order.append("move")
        _get_pipette(ctx).drop_tip.side_effect = lambda *a: call_order.append("drop_tip")

        drop_tip(ctx, position="waste_1")
        assert call_order == ["move", "drop_tip"]

    def test_passes_speed(self):
        from src.protocol_engine.commands.pipette import drop_tip

        ctx = _mock_context()
        drop_tip(ctx, position="waste_1", speed=10.0)
        _get_pipette(ctx).drop_tip.assert_called_once_with(10.0)

    def test_default_speed(self):
        from src.protocol_engine.commands.pipette import drop_tip

        ctx = _mock_context()
        drop_tip(ctx, position="waste_1")
        _get_pipette(ctx).drop_tip.assert_called_once_with(50.0)

    def test_raises_when_no_pipette(self):
        from src.protocol_engine.commands.pipette import drop_tip

        ctx = _mock_context(has_pipette=False)
        with pytest.raises(ProtocolExecutionError, match="[Nn]o pipette"):
            drop_tip(ctx, position="waste_1")
