"""Tests for tip tracking in VolumeTracker."""

from __future__ import annotations

import pytest

from deck.labware import Coordinate3D
from deck.labware.tip_rack import TipRack
from protocol_engine.errors import TipNotAvailableError, TipRackDepletedError
from protocol_engine.volume_tracker import VolumeTracker


def _make_tip_rack(rows: int = 2, columns: int = 3) -> TipRack:
    """Build a tip rack with the given grid dimensions."""
    row_labels = [chr(65 + i) for i in range(rows)]
    wells = {}
    for r_idx, label in enumerate(row_labels):
        for c in range(1, columns + 1):
            wells[f"{label}{c}"] = Coordinate3D(
                x=float(c * 9), y=float(-r_idx * 9), z=-5.0,
            )
    return TipRack(
        name="test_rack",
        model_name="tiprack_300ul",
        rows=rows,
        columns=columns,
        length_mm=127.0,
        width_mm=85.0,
        height_mm=65.0,
        wells=wells,
    )


class TestRegisterTipRack:

    def test_register_creates_entries_for_all_wells(self):
        tracker = VolumeTracker()
        rack = _make_tip_rack(2, 3)
        tracker.register_tip_rack("rack_1", rack)
        assert tracker.tips_remaining("rack_1") == 6

    def test_register_duplicate_raises(self):
        tracker = VolumeTracker()
        rack = _make_tip_rack(1, 1)
        tracker.register_tip_rack("rack_1", rack)
        with pytest.raises(ValueError, match="already registered"):
            tracker.register_tip_rack("rack_1", rack)


class TestPickUpTip:

    def test_pick_up_marks_slot_as_used(self):
        tracker = VolumeTracker()
        rack = _make_tip_rack(2, 3)
        tracker.register_tip_rack("rack_1", rack)
        tracker.pick_up_tip("rack_1", "A1")
        assert tracker.tips_remaining("rack_1") == 5

    def test_pick_up_same_slot_twice_raises(self):
        tracker = VolumeTracker()
        rack = _make_tip_rack(1, 1)
        tracker.register_tip_rack("rack_1", rack)
        tracker.pick_up_tip("rack_1", "A1")
        with pytest.raises(TipNotAvailableError):
            tracker.pick_up_tip("rack_1", "A1")

    def test_pick_up_tip_error_has_fields(self):
        tracker = VolumeTracker()
        rack = _make_tip_rack(1, 1)
        tracker.register_tip_rack("rack_1", rack)
        tracker.pick_up_tip("rack_1", "A1")
        with pytest.raises(TipNotAvailableError) as exc_info:
            tracker.pick_up_tip("rack_1", "A1")
        assert exc_info.value.labware_key == "rack_1"
        assert exc_info.value.well_id == "A1"

    def test_pick_up_unregistered_rack_raises(self):
        tracker = VolumeTracker()
        with pytest.raises(KeyError):
            tracker.pick_up_tip("nonexistent", "A1")

    def test_pick_up_unknown_well_raises(self):
        tracker = VolumeTracker()
        rack = _make_tip_rack(1, 1)
        tracker.register_tip_rack("rack_1", rack)
        with pytest.raises(KeyError):
            tracker.pick_up_tip("rack_1", "Z9")


class TestTipsRemaining:

    def test_decrements_correctly(self):
        tracker = VolumeTracker()
        rack = _make_tip_rack(1, 3)
        tracker.register_tip_rack("rack_1", rack)
        assert tracker.tips_remaining("rack_1") == 3
        tracker.pick_up_tip("rack_1", "A1")
        assert tracker.tips_remaining("rack_1") == 2
        tracker.pick_up_tip("rack_1", "A2")
        assert tracker.tips_remaining("rack_1") == 1
        tracker.pick_up_tip("rack_1", "A3")
        assert tracker.tips_remaining("rack_1") == 0

    def test_unregistered_rack_raises(self):
        tracker = VolumeTracker()
        with pytest.raises(KeyError):
            tracker.tips_remaining("nonexistent")


class TestNextAvailableTip:

    def test_returns_column_major_order(self):
        """Column-major: A1, B1, A2, B2, A3, B3."""
        tracker = VolumeTracker()
        rack = _make_tip_rack(2, 3)
        tracker.register_tip_rack("rack_1", rack)

        expected_order = ["A1", "B1", "A2", "B2", "A3", "B3"]
        for expected_well in expected_order:
            next_tip = tracker.next_available_tip("rack_1")
            assert next_tip == expected_well, (
                f"Expected {expected_well}, got {next_tip}"
            )
            tracker.pick_up_tip("rack_1", next_tip)

    def test_returns_none_when_depleted(self):
        tracker = VolumeTracker()
        rack = _make_tip_rack(1, 1)
        tracker.register_tip_rack("rack_1", rack)
        tracker.pick_up_tip("rack_1", "A1")
        assert tracker.next_available_tip("rack_1") is None

    def test_skips_used_tips(self):
        tracker = VolumeTracker()
        rack = _make_tip_rack(2, 2)
        tracker.register_tip_rack("rack_1", rack)
        # Use A1 first
        tracker.pick_up_tip("rack_1", "A1")
        # Next should be B1 (column-major)
        assert tracker.next_available_tip("rack_1") == "B1"

    def test_unregistered_rack_raises(self):
        tracker = VolumeTracker()
        with pytest.raises(KeyError):
            tracker.next_available_tip("nonexistent")


class TestTipRackDepletedError:

    def test_error_has_labware_key(self):
        err = TipRackDepletedError("rack_1")
        assert err.labware_key == "rack_1"
        assert "rack_1" in str(err)


class TestTipNotAvailableError:

    def test_error_has_fields(self):
        err = TipNotAvailableError("rack_1", "A1")
        assert err.labware_key == "rack_1"
        assert err.well_id == "A1"
        assert "A1" in str(err)
