"""Tests for dead volume support in VolumeTracker and labware models."""

from __future__ import annotations

import pytest

from deck.labware.labware import Coordinate3D
from deck.labware.vial import Vial
from deck.labware.well_plate import WellPlate
from protocol_engine.errors import UnderflowVolumeError
from protocol_engine.volume_tracker import VolumeTracker


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_vial(
    capacity: float = 1500.0,
    working: float = 1200.0,
    dead_volume_ul: float = 0.0,
) -> Vial:
    return Vial(
        name="vial_1",
        model_name="standard_vial",
        height_mm=66.75,
        diameter_mm=28.0,
        location=Coordinate3D(x=-30.0, y=-40.0, z=-20.0),
        capacity_ul=capacity,
        working_volume_ul=working,
        dead_volume_ul=dead_volume_ul,
    )


def _make_plate(
    rows: int = 2,
    columns: int = 2,
    capacity: float = 200.0,
    working: float = 150.0,
    dead_volume_ul: float = 0.0,
) -> WellPlate:
    wells = {}
    for r in range(rows):
        for c in range(1, columns + 1):
            label = f"{chr(65 + r)}{c}"
            wells[label] = Coordinate3D(
                x=float(c * 10), y=float(-r * 10), z=-5.0,
            )
    return WellPlate(
        name="plate_1",
        model_name="test_plate",
        length_mm=127.0,
        width_mm=85.0,
        height_mm=14.0,
        rows=rows,
        columns=columns,
        wells=wells,
        capacity_ul=capacity,
        working_volume_ul=working,
        dead_volume_ul=dead_volume_ul,
    )


# ── Labware model tests ─────────────────────────────────────────────────────


class TestVialDeadVolume:

    def test_default_dead_volume_is_zero(self):
        vial = _make_vial()
        assert vial.dead_volume_ul == 0.0

    def test_dead_volume_accepted(self):
        vial = _make_vial(dead_volume_ul=50.0)
        assert vial.dead_volume_ul == 50.0

    def test_negative_dead_volume_rejected(self):
        with pytest.raises(ValueError):
            _make_vial(dead_volume_ul=-1.0)

    def test_dead_volume_exceeding_capacity_rejected(self):
        with pytest.raises(ValueError):
            _make_vial(capacity=1500.0, dead_volume_ul=1500.0)


class TestWellPlateDeadVolume:

    def test_default_dead_volume_is_zero(self):
        plate = _make_plate()
        assert plate.dead_volume_ul == 0.0

    def test_dead_volume_accepted(self):
        plate = _make_plate(dead_volume_ul=10.0)
        assert plate.dead_volume_ul == 10.0

    def test_negative_dead_volume_rejected(self):
        with pytest.raises(ValueError):
            _make_plate(dead_volume_ul=-5.0)

    def test_dead_volume_exceeding_capacity_rejected(self):
        with pytest.raises(ValueError):
            _make_plate(capacity=200.0, dead_volume_ul=200.0)


# ── VolumeTracker dead volume tests ─────────────────────────────────────────


class TestTrackerDeadVolume:

    def test_aspirate_below_dead_volume_raises(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0, dead_volume_ul=100.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=150.0)

        with pytest.raises(UnderflowVolumeError):
            tracker.record_aspirate("vial_1", None, 100.0)

    def test_aspirate_to_dead_volume_succeeds(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0, dead_volume_ul=100.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=200.0)

        tracker.record_aspirate("vial_1", None, 100.0)
        assert tracker.get_volume("vial_1") == pytest.approx(100.0)

    def test_dead_volume_zero_allows_aspiration_to_zero(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0, dead_volume_ul=0.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=50.0)

        tracker.record_aspirate("vial_1", None, 50.0)
        assert tracker.get_volume("vial_1") == pytest.approx(0.0)

    def test_dead_volume_on_well_plate_per_well(self):
        tracker = VolumeTracker()
        plate = _make_plate(capacity=200.0, dead_volume_ul=20.0)
        tracker.register_labware(
            "plate_1", plate, initial_volumes={"A1": 50.0, "A2": 100.0},
        )

        # A1 has 50 uL, dead = 20, so max aspirate is 30
        with pytest.raises(UnderflowVolumeError):
            tracker.record_aspirate("plate_1", "A1", 40.0)

        tracker.record_aspirate("plate_1", "A1", 30.0)
        assert tracker.get_volume("plate_1", "A1") == pytest.approx(20.0)

    def test_underflow_error_includes_dead_volume_info(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0, dead_volume_ul=100.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=120.0)

        with pytest.raises(UnderflowVolumeError, match="dead volume"):
            tracker.record_aspirate("vial_1", None, 50.0)

    def test_get_dead_volume(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0, dead_volume_ul=100.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=500.0)

        assert tracker.get_dead_volume("vial_1") == 100.0

    def test_get_dead_volume_well_plate(self):
        tracker = VolumeTracker()
        plate = _make_plate(capacity=200.0, dead_volume_ul=15.0)
        tracker.register_labware("plate_1", plate)

        assert tracker.get_dead_volume("plate_1", "A1") == 15.0
