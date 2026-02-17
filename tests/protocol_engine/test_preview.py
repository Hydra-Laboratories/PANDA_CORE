"""Tests for protocol coordinate preview mock runs."""

from pathlib import Path

from src.protocol_engine.preview import format_move_preview, preview_protocol_moves


REPO_ROOT = Path(__file__).resolve().parents[2]
DECK_SAMPLE_PATH = REPO_ROOT / "configs" / "deck.sample.yaml"
THREE_WELL_PROTOCOL_PATH = REPO_ROOT / "experiments" / "sample_three_well_protocol.yaml"


def test_preview_protocol_moves_resolves_three_sample_wells():
    preview = preview_protocol_moves(
        deck_path=DECK_SAMPLE_PATH,
        protocol_path=THREE_WELL_PROTOCOL_PATH,
    )

    assert len(preview) == 3
    assert [step.target for step in preview] == [
        "plate_1.A1",
        "plate_1.C8",
        "plate_1.B1",
    ]
    assert [step.instrument for step in preview] == ["pipette", "pipette", "pipette"]

    first, second, third = preview
    assert (first.coordinate.x, first.coordinate.y, first.coordinate.z) == (-10.0, -10.0, -15.0)
    assert (second.coordinate.x, second.coordinate.y, second.coordinate.z) == (53.0, -28.0, -15.0)
    assert (third.coordinate.x, third.coordinate.y, third.coordinate.z) == (-10.0, -19.0, -15.0)


def test_format_move_preview_includes_rows_for_each_step():
    preview = preview_protocol_moves(
        deck_path=DECK_SAMPLE_PATH,
        protocol_path=THREE_WELL_PROTOCOL_PATH,
    )

    rendered = format_move_preview(preview)

    assert "MOCK RUN ONLY" in rendered
    assert "plate_1.A1" in rendered
    assert "plate_1.C8" in rendered
    assert "plate_1.B1" in rendered
    assert "-10.000" in rendered
    assert "53.000" in rendered
    assert "-19.000" in rendered
