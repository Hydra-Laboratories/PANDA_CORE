"""Tests for the pause protocol command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from deck.labware.labware import Coordinate3D
from deck.labware.vial import Vial
from protocol_engine.commands.pause import pause
from protocol_engine.volume_tracker import VolumeTracker


def _make_context(volume_tracker=None):
    """Create a minimal mock ProtocolContext."""
    ctx = MagicMock()
    ctx.volume_tracker = volume_tracker
    ctx.logger = MagicMock()
    return ctx


def _make_vial(capacity: float = 1500.0, working: float = 1200.0) -> Vial:
    return Vial(
        name="vial_1",
        model_name="standard_vial",
        height_mm=66.75,
        diameter_mm=28.0,
        location=Coordinate3D(x=-30.0, y=-40.0, z=-20.0),
        capacity_ul=capacity,
        working_volume_ul=working,
    )


class TestPauseUserReason:

    @patch("builtins.input", return_value="")
    def test_user_pause_waits_for_input(self, mock_input):
        ctx = _make_context()
        pause(ctx, message="Test pause", reason="user")
        mock_input.assert_called_once()

    @patch("builtins.input", return_value="")
    def test_user_pause_logs_message(self, mock_input):
        ctx = _make_context()
        pause(ctx, message="Custom message", reason="user")
        ctx.logger.info.assert_called()


class TestPauseRefillReason:

    @patch("builtins.input", return_value="500")
    def test_refill_with_specific_volume_updates_tracker(self, mock_input):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=100.0)

        ctx = _make_context(volume_tracker=tracker)
        pause(
            ctx,
            message="Refill vial",
            reason="refill",
            labware_key="vial_1",
            capacity_ul=1500.0,
        )

        assert tracker.get_volume("vial_1") == pytest.approx(600.0)

    @patch("builtins.input", return_value="")
    def test_refill_empty_input_does_full_refill_to_capacity(self, mock_input):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=100.0)

        ctx = _make_context(volume_tracker=tracker)
        pause(
            ctx,
            message="Refill vial",
            reason="refill",
            labware_key="vial_1",
            capacity_ul=1500.0,
        )

        assert tracker.get_volume("vial_1") == pytest.approx(1500.0)

    @patch("builtins.input", return_value="")
    def test_refill_without_tracker_does_not_error(self, mock_input):
        ctx = _make_context(volume_tracker=None)
        pause(
            ctx,
            message="Refill vial",
            reason="refill",
            labware_key="vial_1",
            capacity_ul=1500.0,
        )


class TestPauseTipSwapReason:

    @patch("builtins.input", return_value="")
    def test_tip_swap_waits_for_input(self, mock_input):
        ctx = _make_context()
        pause(ctx, message="Swap tips", reason="tip_swap")
        mock_input.assert_called_once()


class TestVolumeTrackerRefill:

    def test_refill_adds_volume(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=200.0)

        tracker.refill("vial_1", None, 500.0)
        assert tracker.get_volume("vial_1") == pytest.approx(700.0)

    def test_refill_capped_at_capacity(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=1400.0)

        tracker.refill("vial_1", None, 500.0)
        assert tracker.get_volume("vial_1") == pytest.approx(1500.0)

    def test_refill_well_plate(self):
        from deck.labware.well_plate import WellPlate

        wells = {
            "A1": Coordinate3D(x=10.0, y=0.0, z=-5.0),
            "A2": Coordinate3D(x=20.0, y=0.0, z=-5.0),
            "B1": Coordinate3D(x=10.0, y=-10.0, z=-5.0),
            "B2": Coordinate3D(x=20.0, y=-10.0, z=-5.0),
        }
        plate = WellPlate(
            name="plate_1",
            model_name="test_plate",
            length_mm=127.0,
            width_mm=85.0,
            height_mm=14.0,
            rows=2,
            columns=2,
            wells=wells,
            capacity_ul=200.0,
            working_volume_ul=150.0,
        )
        tracker = VolumeTracker()
        tracker.register_labware("plate_1", plate, initial_volumes={"A1": 50.0})

        tracker.refill("plate_1", "A1", 100.0)
        assert tracker.get_volume("plate_1", "A1") == pytest.approx(150.0)
