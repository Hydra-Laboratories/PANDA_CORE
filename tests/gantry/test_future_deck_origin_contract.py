"""Future deck-origin coordinate contract tests.

These intentionally describe the target convention from issue #87. They are
xfail during Phase 0 because the implementation still uses the current
positive-down user-space Z translation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from board.board import Board
from gantry.gantry import Gantry


@pytest.mark.xfail(strict=True, reason="deck-origin coordinate refactor pending")
@patch("gantry.gantry.Mill")
def test_future_gantry_move_to_sends_deck_origin_z_without_sign_flip(mock_mill_cls):
    gantry = Gantry(config={})

    gantry.move_to(10.0, 20.0, -5.0)

    mock_mill_cls.return_value.move_to_position.assert_called_once_with(
        x_coordinate=10.0,
        y_coordinate=20.0,
        z_coordinate=-5.0,
        travel_z=None,
    )


@pytest.mark.xfail(strict=True, reason="deck-origin coordinate refactor pending")
def test_future_board_move_to_labware_uses_positive_clearance_above_deck():
    instr = MagicMock()
    instr.name = "probe"
    instr.offset_x = 0.0
    instr.offset_y = 0.0
    instr.depth = 0.0
    instr.measurement_height = 0.0
    instr.safe_approach_height = 20.0
    gantry = MagicMock()
    board = Board(gantry=gantry, instruments={"probe": instr})
    labware = MagicMock()
    labware.x = 1.0
    labware.y = 2.0
    labware.z = 0.0

    board.move_to_labware("probe", labware)

    gantry.move_to.assert_called_once_with(1.0, 2.0, 20.0, travel_z=20.0)
