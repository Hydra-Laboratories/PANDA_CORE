"""Tests for the move protocol command — unit and end-to-end."""

import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.deck.labware.labware import Coordinate3D
from src.protocol_engine.loader import load_protocol_from_yaml
from src.protocol_engine.protocol import Protocol, ProtocolContext, ProtocolStep


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _mock_context(
    resolve_return: Coordinate3D | None = None,
) -> ProtocolContext:
    """Create a ProtocolContext with mock board and deck."""
    coord = resolve_return or Coordinate3D(x=-10.0, y=-10.0, z=-15.0)

    board = MagicMock()
    deck = MagicMock()
    deck.resolve.return_value = coord

    return ProtocolContext(
        board=board,
        deck=deck,
        logger=logging.getLogger("test_move"),
    )


# ─── Unit tests for the move handler ─────────────────────────────────────────


class TestMoveCommand:

    def test_move_resolves_position(self):
        # Import here so the registry is populated
        from src.protocol_engine.commands.move import move

        ctx = _mock_context()
        move(ctx, instrument="pipette", position="plate_1.A1")

        ctx.deck.resolve.assert_called_once_with("plate_1.A1")

    def test_move_calls_board_move_with_instrument_and_coord(self):
        from src.protocol_engine.commands.move import move

        coord = Coordinate3D(x=-10.0, y=-20.0, z=-5.0)
        ctx = _mock_context(resolve_return=coord)

        move(ctx, instrument="pipette", position="plate_1.A1")

        ctx.board.move.assert_called_once_with("pipette", coord)

    def test_move_passes_instrument_name_through(self):
        from src.protocol_engine.commands.move import move

        ctx = _mock_context()
        move(ctx, instrument="filmetrics", position="vial_1")

        ctx.board.move.assert_called_once()
        call_args = ctx.board.move.call_args
        assert call_args[0][0] == "filmetrics"

    def test_move_invalid_target_propagates_error(self):
        from src.protocol_engine.commands.move import move

        ctx = _mock_context()
        ctx.deck.resolve.side_effect = KeyError("No labware 'bad' on deck.")

        with pytest.raises(KeyError, match="bad"):
            move(ctx, instrument="pipette", position="bad.A1")


# ─── End-to-end: YAML → load → run ──────────────────────────────────────────


class TestMoveEndToEnd:

    def test_yaml_to_execution(self):
        yaml_content = """
protocol:
  - move:
      instrument: pipette
      position: plate_1.A1
  - move:
      instrument: pipette
      position: plate_1.C9
"""
        coord_a1 = Coordinate3D(x=-10.0, y=-10.0, z=-15.0)
        coord_c9 = Coordinate3D(x=62.0, y=-28.0, z=-15.0)

        # Set up deck to return different coords based on target
        deck = MagicMock()

        def resolve_side_effect(target: str) -> Coordinate3D:
            if target == "plate_1.A1":
                return coord_a1
            if target == "plate_1.C9":
                return coord_c9
            raise KeyError(f"No labware for '{target}'")

        deck.resolve.side_effect = resolve_side_effect
        board = MagicMock()

        ctx = ProtocolContext(
            board=board,
            deck=deck,
            logger=logging.getLogger("test_e2e"),
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            path = f.name
        try:
            protocol = load_protocol_from_yaml(path)
            assert len(protocol) == 2

            protocol.run(ctx)

            # deck.resolve called once per step
            assert deck.resolve.call_count == 2
            deck.resolve.assert_any_call("plate_1.A1")
            deck.resolve.assert_any_call("plate_1.C9")

            # board.move called once per step with correct args
            assert board.move.call_count == 2
            board.move.assert_any_call("pipette", coord_a1)
            board.move.assert_any_call("pipette", coord_c9)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_yaml_single_move_runs(self):
        yaml_content = """
protocol:
  - move:
      instrument: pipette
      position: vial_1
"""
        coord = Coordinate3D(x=-30.0, y=-40.0, z=-20.0)
        ctx = _mock_context(resolve_return=coord)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            path = f.name
        try:
            protocol = load_protocol_from_yaml(path)
            results = protocol.run(ctx)

            assert len(results) == 1
            ctx.deck.resolve.assert_called_once_with("vial_1")
            ctx.board.move.assert_called_once_with("pipette", coord)
        finally:
            Path(path).unlink(missing_ok=True)
