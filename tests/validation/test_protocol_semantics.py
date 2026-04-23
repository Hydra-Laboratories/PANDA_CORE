"""Tests for semantic protocol validation beyond static bounds."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

from board.board import Board
from deck.deck import Deck
from deck.labware.labware import Coordinate3D
from deck.labware.well_plate import WellPlate
from protocol_engine.protocol import Protocol, ProtocolStep
from validation.protocol_semantics import validate_protocol_semantics


def _plate() -> WellPlate:
    return WellPlate(
        name="plate",
        model_name="test_plate",
        length_mm=127.71,
        width_mm=85.43,
        height_mm=14.10,
        rows=1,
        columns=1,
        wells={"A1": Coordinate3D(x=0.0, y=0.0, z=73.0)},
        capacity_ul=200.0,
        working_volume_ul=150.0,
    )


def _instrument(name: str = "asmi", measurement_height: float = 0.0):
    instr = MagicMock()
    instr.name = name
    instr.offset_x = 0.0
    instr.offset_y = 0.0
    instr.depth = 0.0
    instr.measurement_height = measurement_height
    instr.safe_approach_height = measurement_height
    return instr


def _protocol(args: dict) -> Protocol:
    return Protocol([
        ProtocolStep(
            index=0,
            command_name="scan",
            handler=lambda *a, **k: None,
            args=args,
        )
    ])


def _board_and_deck():
    board = Board(
        gantry=MagicMock(),
        instruments={"asmi": _instrument("asmi", measurement_height=0.0)},
    )
    deck = Deck({"plate": _plate()})
    return board, deck


def test_asmi_indentation_limit_must_exceed_measurement_height():
    board, deck = _board_and_deck()
    protocol = _protocol({
        "plate": "plate",
        "instrument": "asmi",
        "method": "indentation",
        "method_kwargs": {
            "measurement_height": 73.0,
            "indentation_limit": 70.0,
            "step_size": 0.01,
        },
    })

    violations = validate_protocol_semantics(protocol, board, deck)

    assert len(violations) == 1
    assert "indentation_limit must be greater" in violations[0].message


def test_scan_travel_height_must_not_be_below_action_height():
    board, deck = _board_and_deck()
    protocol = _protocol({
        "plate": "plate",
        "instrument": "asmi",
        "method": "indentation",
        "interwell_travel_height": 80.0,
        "method_kwargs": {
            "measurement_height": 73.0,
            "indentation_limit": 83.0,
            "step_size": 0.01,
        },
    })

    violations = validate_protocol_semantics(protocol, board, deck)

    assert len(violations) == 1
    assert "interwell_travel_height" in violations[0].message


def test_valid_asmi_scan_semantics_pass():
    board, deck = _board_and_deck()
    protocol = _protocol({
        "plate": "plate",
        "instrument": "asmi",
        "method": "indentation",
        "entry_travel_height": 20.0,
        "interwell_travel_height": 70.0,
        "method_kwargs": {
            "measurement_height": 73.0,
            "indentation_limit": 83.0,
            "step_size": 0.01,
        },
    })

    assert validate_protocol_semantics(protocol, board, deck) == []


def test_legacy_scan_travel_names_are_semantic_violations():
    board, deck = _board_and_deck()
    protocol = _protocol({
        "plate": "plate",
        "instrument": "asmi",
        "method": "indentation",
        "entry_travel_z": 20.0,
        "safe_approach_height": 70.0,
        "method_kwargs": {
            "measurement_height": 73.0,
            "indentation_limit": 83.0,
            "step_size": 0.01,
        },
    })

    violations = validate_protocol_semantics(protocol, board, deck)

    assert len(violations) == 2
    assert "`entry_travel_z` is no longer supported" in violations[0].message
    assert "`safe_approach_height` is no longer supported" in violations[1].message


def test_legacy_asmi_z_limit_is_semantic_violation():
    board, deck = _board_and_deck()
    protocol = _protocol({
        "plate": "plate",
        "instrument": "asmi",
        "method": "indentation",
        "interwell_travel_height": 70.0,
        "method_kwargs": {
            "measurement_height": 73.0,
            "z_limit": 83.0,
            "step_size": 0.01,
        },
    })

    violations = validate_protocol_semantics(protocol, board, deck)

    assert len(violations) == 1
    assert "`z_limit` is no longer supported" in violations[0].message
