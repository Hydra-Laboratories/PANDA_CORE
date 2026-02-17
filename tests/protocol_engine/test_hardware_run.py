"""Tests for hardware protocol runner orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from src.protocol_engine.hardware_run import HardwareRunOptions, run_protocol_on_gantry


def test_run_protocol_on_gantry_connects_homes_runs_and_disconnects(monkeypatch):
    deck = MagicMock()
    protocol = MagicMock()
    protocol.run.return_value = ["ok"]
    gantry = MagicMock()
    gantry.is_healthy.return_value = True

    monkeypatch.setattr(
        "src.protocol_engine.hardware_run.load_deck_from_yaml_safe",
        lambda _path: deck,
    )
    monkeypatch.setattr(
        "src.protocol_engine.hardware_run.load_protocol_from_yaml_safe",
        lambda _path: protocol,
    )
    monkeypatch.setattr(
        "src.protocol_engine.hardware_run._load_gantry_config",
        lambda _path: {"cnc": {"homing_strategy": "xy_hard_limits"}},
    )
    monkeypatch.setattr(
        "src.protocol_engine.hardware_run.Gantry",
        lambda config: gantry,
    )

    options = HardwareRunOptions(
        deck_path=Path("configs/deck.sample.yaml"),
        protocol_path=Path("experiments/sample_three_well_protocol.yaml"),
        gantry_config_path=Path("configs/genmitsu_3018_PROver_v2.yaml"),
        instrument_name="pipette",
        instrument_offset_x=-10.0,
        instrument_offset_y=5.0,
        instrument_depth=-2.0,
        home_before_run=True,
        require_healthy=True,
    )

    results = run_protocol_on_gantry(options)

    assert results == ["ok"]
    gantry.connect.assert_called_once_with()
    gantry.is_healthy.assert_called_once_with()
    gantry.home.assert_called_once_with()
    protocol.run.assert_called_once()
    gantry.disconnect.assert_called_once_with()

    context = protocol.run.call_args.args[0]
    assert context.deck is deck
    assert context.board.instruments["pipette"].offset_x == -10.0
    assert context.board.instruments["pipette"].offset_y == 5.0
    assert context.board.instruments["pipette"].depth == -2.0


def test_run_protocol_on_gantry_raises_when_health_check_fails(monkeypatch):
    protocol = MagicMock()
    gantry = MagicMock()
    gantry.is_healthy.return_value = False

    monkeypatch.setattr(
        "src.protocol_engine.hardware_run.load_deck_from_yaml_safe",
        lambda _path: MagicMock(),
    )
    monkeypatch.setattr(
        "src.protocol_engine.hardware_run.load_protocol_from_yaml_safe",
        lambda _path: protocol,
    )
    monkeypatch.setattr(
        "src.protocol_engine.hardware_run._load_gantry_config",
        lambda _path: {},
    )
    monkeypatch.setattr(
        "src.protocol_engine.hardware_run.Gantry",
        lambda config: gantry,
    )

    options = HardwareRunOptions(
        deck_path=Path("configs/deck.sample.yaml"),
        protocol_path=Path("experiments/sample_three_well_protocol.yaml"),
        gantry_config_path=Path("configs/genmitsu_3018_PROver_v2.yaml"),
        require_healthy=True,
    )

    try:
        run_protocol_on_gantry(options)
        assert False, "Expected RuntimeError for unhealthy gantry."
    except RuntimeError as exc:
        assert "health check failed" in str(exc).lower()

    protocol.run.assert_not_called()
    gantry.disconnect.assert_called_once_with()
