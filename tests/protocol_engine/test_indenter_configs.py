"""Tests for imported indenter ASMI configs."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from board.loader import load_board_from_yaml
from deck.loader import load_deck_from_yaml
from gantry.loader import load_gantry_from_yaml
from protocol_engine.loader import load_protocol_from_yaml
from protocol_engine.setup import setup_protocol


ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"


def test_indenter_imported_raw_workframe_config_validates_setup():
    gantry_path = CONFIGS / "gantry/indenter_raw_workframe.yaml"
    deck_path = CONFIGS / "deck/indenter_plate_raw_workframe.yaml"
    board_path = CONFIGS / "board/indenter_asmi_raw_workframe.yaml"
    protocol_path = CONFIGS / "protocol/indenter_asmi_indentation_raw_workframe.yaml"

    gantry_config = load_gantry_from_yaml(gantry_path)
    deck = load_deck_from_yaml(deck_path, total_z_height=gantry_config.total_z_height)
    board = load_board_from_yaml(board_path, MagicMock(), mock_mode=True)
    protocol = load_protocol_from_yaml(protocol_path)

    plate = deck["plate"]
    a1 = plate.get_well_center("A1")
    a2 = plate.get_well_center("A2")
    h12 = plate.get_well_center("H12")

    assert (a1.x, a1.y, a1.z) == pytest.approx((26.1, 58.7, 19.0))
    assert (a2.x, a2.y, a2.z) == pytest.approx((26.1, 67.7, 19.0))
    assert (h12.x, h12.y, h12.z) == pytest.approx((89.1, 157.7, 19.0))
    assert board.instruments["asmi"].safe_approach_height == pytest.approx(9.0)
    assert board.instruments["asmi"].measurement_height == pytest.approx(0.0)

    scan_step = next(step for step in protocol.steps if step.command_name == "scan")
    assert scan_step.args["entry_travel_z"] == pytest.approx(10.0)
    assert scan_step.args["safe_approach_height"] == pytest.approx(10.0)
    assert scan_step.args["method_kwargs"]["measurement_height"] == pytest.approx(19.0)
    assert scan_step.args["method_kwargs"]["z_limit"] == pytest.approx(19.5)
    assert scan_step.args["method_kwargs"]["well_bottom_z"] == pytest.approx(24.3)

    setup_protocol(
        gantry_path,
        deck_path,
        board_path,
        protocol_path,
        mock_mode=True,
    )
