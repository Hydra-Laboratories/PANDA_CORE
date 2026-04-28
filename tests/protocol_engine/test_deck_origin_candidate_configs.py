"""Movement-plan checks for issue #87 deck-origin candidate configs."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from board.loader import load_board_from_yaml
from board.yaml_schema import BoardYamlSchema
from deck.loader import load_deck_from_yaml
from gantry.loader import load_gantry_from_yaml
from protocol_engine.commands.scan import scan
from protocol_engine.loader import load_protocol_from_yaml
from protocol_engine.protocol import ProtocolContext
from protocol_engine.setup import setup_protocol
from validation.protocol_semantics import validate_protocol_semantics


ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"


def test_asmi_candidate_config_generates_deck_origin_scan_waypoints():
    gantry_config = load_gantry_from_yaml(
        CONFIGS / "gantry/cub_xl_asmi.yaml"
    )
    deck = load_deck_from_yaml(
        CONFIGS / "deck/asmi_deck.yaml",
        total_z_height=gantry_config.total_z_height,
    )
    mock_gantry = MagicMock()
    mock_gantry.get_coordinates.return_value = {"x": 0.0, "y": 0.0, "z": 85.0}
    board = load_board_from_yaml(
        CONFIGS / "board/asmi_board.yaml",
        mock_gantry,
        mock_mode=True,
    )
    indentation_calls = []

    def fake_indentation(
        *,
        measurement_height=None,
        indentation_limit=None,
        gantry=None,
        **kwargs,
    ):
        indentation_calls.append({
            "measurement_height": measurement_height,
            "indentation_limit": indentation_limit,
            "gantry": gantry,
            **kwargs,
        })
        return {"ok": True}

    board.instruments["asmi"].indentation = fake_indentation
    protocol = load_protocol_from_yaml(
        CONFIGS / "protocol/asmi_indentation.yaml"
    )

    scan_step = next(step for step in protocol.steps if step.command_name == "scan")
    assert validate_protocol_semantics(protocol, board, deck, gantry_config) == []

    ctx = ProtocolContext(
        board=board,
        deck=deck,
        positions=protocol.positions,
        gantry=gantry_config,
        logger=logging.getLogger("test_asmi_candidate_config"),
    )
    scan(ctx, **scan_step.args)

    moves = mock_gantry.move_to.call_args_list
    first_well = deck["plate"].get_well_center("A1")
    second_well = deck["plate"].get_well_center("A2")
    last_well = deck["plate"].get_well_center("H12")
    entry_travel_height = scan_step.args["entry_travel_height"]
    interwell_travel_height = scan_step.args["interwell_travel_height"]
    measurement_height = scan_step.args["measurement_height"]
    indentation_limit = scan_step.args["indentation_limit"]

    assert moves[0].args == pytest.approx(
        (first_well.x, first_well.y, entry_travel_height)
    )
    assert moves[0].kwargs == {"travel_z": entry_travel_height}
    assert moves[1].args == pytest.approx(
        (first_well.x, first_well.y, measurement_height)
    )
    assert moves[1].kwargs == {"travel_z": None}
    assert moves[2].args == pytest.approx(
        (second_well.x, second_well.y, interwell_travel_height)
    )
    assert moves[2].kwargs == {"travel_z": interwell_travel_height}
    assert moves[-1].args == pytest.approx(
        (last_well.x, last_well.y, interwell_travel_height)
    )
    assert moves[-1].kwargs == {"travel_z": None}

    assert indentation_calls[0]["measurement_height"] == measurement_height
    assert indentation_calls[0]["indentation_limit"] == indentation_limit
    assert indentation_calls[0]["gantry"] is mock_gantry


def test_panda_candidate_deck_origin_layout_and_placeholders_parse():
    gantry_config = load_gantry_from_yaml(
        CONFIGS / "gantry/cub_xl_panda.yaml"
    )
    deck = load_deck_from_yaml(
        CONFIGS / "deck/panda_deck.yaml",
        total_z_height=gantry_config.total_z_height,
    )
    with (CONFIGS / "board/panda_board.yaml").open() as handle:
        board_schema = BoardYamlSchema.model_validate(yaml.safe_load(handle))

    plate = deck.resolve("well_plate_holder.plate.A1")
    plate_a2 = deck.resolve("well_plate_holder.plate.A2")
    tip_a1 = deck.resolve("tip_rack_left.A1")
    tip_a2 = deck.resolve("tip_rack_left.A2")

    assert plate_a2.x == pytest.approx(plate.x)
    assert plate_a2.y > plate.y
    assert tip_a2.x == pytest.approx(tip_a1.x)
    assert tip_a2.y > tip_a1.y
    assert deck.resolve("vial_holder.vial_9").z > deck["vial_holder"].location.z
    assert set(board_schema.instruments) == {
        "potentiostat",
        "camera",
        "vial_capper_decapper",
    }


def test_filmetrics_candidate_translates_legacy_deck_and_validates_setup():
    gantry_path = CONFIGS / "gantry/cub_filmetrics.yaml"
    deck_path = CONFIGS / "deck/filmetrics_deck.yaml"
    board_path = CONFIGS / "board/filmetrics_board.yaml"
    protocol_path = CONFIGS / "protocol/filmetrics_scan.yaml"

    gantry_config = load_gantry_from_yaml(gantry_path)
    deck = load_deck_from_yaml(deck_path, total_z_height=gantry_config.total_z_height)
    board = load_board_from_yaml(board_path, MagicMock(), mock_mode=True)
    protocol = load_protocol_from_yaml(protocol_path)

    plate = deck["plate_1"]
    a1 = plate.get_well_center("A1")
    a2 = plate.get_well_center("A2")

    assert (a1.x, a1.y, a1.z) == pytest.approx((270.0, 140.0, 70.0))
    assert (a2.x, a2.y, a2.z) == pytest.approx((270.0, 131.0, 70.0))
    assert board.instruments["filmetrics"].measurement_height == 80.0
    assert board.instruments["filmetrics"].safe_approach_height == 80.0
    assert validate_protocol_semantics(protocol, board, deck, gantry_config) == []

    setup_protocol(
        gantry_path,
        deck_path,
        board_path,
        protocol_path,
        mock_mode=True,
    )
