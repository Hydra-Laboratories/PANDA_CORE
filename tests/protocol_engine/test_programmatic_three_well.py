"""Tests for programmatic (non-YAML) three-well protocol builder."""

from src.protocol_engine.programmatic_three_well import (
    SAMPLE_THREE_WELL_TARGETS,
    build_three_well_protocol,
)


def test_sample_targets_match_expected_sequence():
    assert SAMPLE_THREE_WELL_TARGETS == (
        "plate_1.A1",
        "plate_1.C8",
        "plate_1.B1",
    )


def test_build_three_well_protocol_creates_three_move_steps():
    protocol = build_three_well_protocol(instrument="pipette")
    steps = protocol.steps

    assert len(steps) == 3
    assert [s.command_name for s in steps] == ["move", "move", "move"]
    assert [s.args["position"] for s in steps] == list(SAMPLE_THREE_WELL_TARGETS)
    assert all(s.args["instrument"] == "pipette" for s in steps)
