"""Tests for the VolumeTracker in-memory volume state manager."""

import math

import pytest

from deck.labware.labware import Coordinate3D
from deck.labware.vial import Vial
from deck.labware.well_plate import WellPlate
from protocol_engine.errors import (
    InvalidVolumeError,
    OverflowVolumeError,
    PipetteVolumeError,
    UnderflowVolumeError,
)
from protocol_engine.volume_tracker import VolumeTracker


# ── Fixtures ─────────────────────────────────────────────────────────────────


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


def _make_plate(
    rows: int = 2, columns: int = 2, capacity: float = 200.0, working: float = 150.0,
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
    )


# ── Registration tests ───────────────────────────────────────────────────────


class TestRegistration:

    def test_register_well_plate_creates_entries_for_all_wells(self):
        tracker = VolumeTracker()
        plate = _make_plate(rows=2, columns=2)
        tracker.register_labware("plate_1", plate)

        for well_id in ["A1", "A2", "B1", "B2"]:
            assert tracker.get_volume("plate_1", well_id) == 0.0

    def test_register_vial_creates_single_entry(self):
        tracker = VolumeTracker()
        vial = _make_vial()
        tracker.register_labware("vial_1", vial)

        assert tracker.get_volume("vial_1") == 0.0

    def test_register_vial_with_initial_volume(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=5000.0, working=4000.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=3000.0)

        assert tracker.get_volume("vial_1") == 3000.0

    def test_register_well_plate_with_initial_volumes_dict(self):
        tracker = VolumeTracker()
        plate = _make_plate()
        initial = {"A1": 50.0, "B2": 100.0}
        tracker.register_labware("plate_1", plate, initial_volumes=initial)

        assert tracker.get_volume("plate_1", "A1") == 50.0
        assert tracker.get_volume("plate_1", "A2") == 0.0
        assert tracker.get_volume("plate_1", "B2") == 100.0

    def test_duplicate_registration_raises(self):
        tracker = VolumeTracker()
        vial = _make_vial()
        tracker.register_labware("vial_1", vial)

        with pytest.raises(ValueError, match="already registered"):
            tracker.register_labware("vial_1", vial)

    def test_register_stores_capacity(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)
        tracker.register_labware("vial_1", vial)

        assert tracker.get_capacity("vial_1") == 1500.0

    def test_register_plate_stores_per_well_capacity(self):
        tracker = VolumeTracker()
        plate = _make_plate(capacity=200.0)
        tracker.register_labware("plate_1", plate)

        assert tracker.get_capacity("plate_1", "A1") == 200.0
        assert tracker.get_capacity("plate_1", "B2") == 200.0

    def test_initial_volume_exceeding_capacity_raises(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)

        with pytest.raises(ValueError, match="exceeds capacity"):
            tracker.register_labware("vial_1", vial, initial_volume_ul=2000.0)

    def test_initial_volumes_dict_exceeding_capacity_raises(self):
        tracker = VolumeTracker()
        plate = _make_plate(capacity=200.0)

        with pytest.raises(ValueError, match="exceeds capacity"):
            tracker.register_labware("plate_1", plate, initial_volumes={"A1": 300.0})

    def test_negative_initial_volume_raises(self):
        tracker = VolumeTracker()
        vial = _make_vial()

        with pytest.raises(ValueError, match="non-negative"):
            tracker.register_labware("vial_1", vial, initial_volume_ul=-10.0)


# ── Query tests ──────────────────────────────────────────────────────────────


class TestQueries:

    def test_get_volume_returns_current(self):
        tracker = VolumeTracker()
        vial = _make_vial()
        tracker.register_labware("vial_1", vial, initial_volume_ul=500.0)

        assert tracker.get_volume("vial_1") == 500.0

    def test_get_volume_unknown_labware_raises(self):
        tracker = VolumeTracker()

        with pytest.raises(KeyError, match="not registered"):
            tracker.get_volume("nonexistent")

    def test_get_volume_unknown_well_raises(self):
        tracker = VolumeTracker()
        plate = _make_plate()
        tracker.register_labware("plate_1", plate)

        with pytest.raises(KeyError, match="not registered"):
            tracker.get_volume("plate_1", "Z99")

    def test_get_capacity_unknown_labware_raises(self):
        tracker = VolumeTracker()

        with pytest.raises(KeyError, match="not registered"):
            tracker.get_capacity("nonexistent")

    def test_get_available_capacity(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=500.0)

        assert tracker.get_available_capacity("vial_1") == 1000.0


# ── Aspirate validation tests ────────────────────────────────────────────────


class TestValidateAspirate:

    def test_sufficient_volume_succeeds(self):
        tracker = VolumeTracker()
        vial = _make_vial()
        tracker.register_labware("vial_1", vial, initial_volume_ul=500.0)

        tracker.validate_aspirate("vial_1", None, 100.0)

    def test_exact_volume_succeeds(self):
        tracker = VolumeTracker()
        vial = _make_vial()
        tracker.register_labware("vial_1", vial, initial_volume_ul=100.0)

        tracker.validate_aspirate("vial_1", None, 100.0)

    def test_underflow_raises(self):
        tracker = VolumeTracker()
        vial = _make_vial()
        tracker.register_labware("vial_1", vial, initial_volume_ul=10.0)

        with pytest.raises(UnderflowVolumeError):
            tracker.validate_aspirate("vial_1", None, 50.0)

    def test_negative_volume_raises(self):
        tracker = VolumeTracker()
        vial = _make_vial()
        tracker.register_labware("vial_1", vial, initial_volume_ul=500.0)

        with pytest.raises(InvalidVolumeError, match="positive"):
            tracker.validate_aspirate("vial_1", None, -5.0)

    def test_zero_volume_raises(self):
        tracker = VolumeTracker()
        vial = _make_vial()
        tracker.register_labware("vial_1", vial, initial_volume_ul=500.0)

        with pytest.raises(InvalidVolumeError, match="positive"):
            tracker.validate_aspirate("vial_1", None, 0.0)

    def test_nan_volume_raises(self):
        tracker = VolumeTracker()
        vial = _make_vial()
        tracker.register_labware("vial_1", vial, initial_volume_ul=500.0)

        with pytest.raises(InvalidVolumeError, match="finite"):
            tracker.validate_aspirate("vial_1", None, float("nan"))

    def test_infinity_volume_raises(self):
        tracker = VolumeTracker()
        vial = _make_vial()
        tracker.register_labware("vial_1", vial, initial_volume_ul=500.0)

        with pytest.raises(InvalidVolumeError, match="finite"):
            tracker.validate_aspirate("vial_1", None, float("inf"))

    def test_aspirate_from_well_plate(self):
        tracker = VolumeTracker()
        plate = _make_plate(capacity=200.0)
        tracker.register_labware("plate_1", plate, initial_volumes={"A1": 100.0})

        tracker.validate_aspirate("plate_1", "A1", 50.0)

    def test_aspirate_from_empty_well_raises(self):
        tracker = VolumeTracker()
        plate = _make_plate()
        tracker.register_labware("plate_1", plate)

        with pytest.raises(UnderflowVolumeError):
            tracker.validate_aspirate("plate_1", "A1", 10.0)


# ── Dispense validation tests ────────────────────────────────────────────────


class TestValidateDispense:

    def test_within_capacity_succeeds(self):
        tracker = VolumeTracker()
        plate = _make_plate(capacity=200.0)
        tracker.register_labware("plate_1", plate)

        tracker.validate_dispense("plate_1", "A1", 100.0)

    def test_to_exact_capacity_succeeds(self):
        tracker = VolumeTracker()
        plate = _make_plate(capacity=200.0)
        tracker.register_labware("plate_1", plate)

        tracker.validate_dispense("plate_1", "A1", 200.0)

    def test_overflow_raises(self):
        tracker = VolumeTracker()
        plate = _make_plate(capacity=200.0)
        tracker.register_labware("plate_1", plate, initial_volumes={"A1": 180.0})

        with pytest.raises(OverflowVolumeError):
            tracker.validate_dispense("plate_1", "A1", 50.0)

    def test_negative_volume_raises(self):
        tracker = VolumeTracker()
        plate = _make_plate()
        tracker.register_labware("plate_1", plate)

        with pytest.raises(InvalidVolumeError, match="positive"):
            tracker.validate_dispense("plate_1", "A1", -10.0)

    def test_zero_volume_raises(self):
        tracker = VolumeTracker()
        plate = _make_plate()
        tracker.register_labware("plate_1", plate)

        with pytest.raises(InvalidVolumeError, match="positive"):
            tracker.validate_dispense("plate_1", "A1", 0.0)

    def test_nan_volume_raises(self):
        tracker = VolumeTracker()
        plate = _make_plate()
        tracker.register_labware("plate_1", plate)

        with pytest.raises(InvalidVolumeError, match="finite"):
            tracker.validate_dispense("plate_1", "A1", float("nan"))

    def test_dispense_to_vial(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)
        tracker.register_labware("vial_1", vial)

        tracker.validate_dispense("vial_1", None, 500.0)


# ── Record (state mutation) tests ────────────────────────────────────────────


class TestRecordOperations:

    def test_record_aspirate_decreases_volume(self):
        tracker = VolumeTracker()
        vial = _make_vial()
        tracker.register_labware("vial_1", vial, initial_volume_ul=500.0)

        tracker.record_aspirate("vial_1", None, 100.0)
        assert tracker.get_volume("vial_1") == pytest.approx(400.0)

    def test_record_dispense_increases_volume(self):
        tracker = VolumeTracker()
        plate = _make_plate(capacity=200.0)
        tracker.register_labware("plate_1", plate)

        tracker.record_dispense("plate_1", "A1", 50.0)
        assert tracker.get_volume("plate_1", "A1") == pytest.approx(50.0)

    def test_aspirate_then_dispense_roundtrip(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)
        plate = _make_plate(capacity=200.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=1000.0)
        tracker.register_labware("plate_1", plate)

        tracker.record_aspirate("vial_1", None, 75.0)
        tracker.record_dispense("plate_1", "A1", 75.0)

        assert tracker.get_volume("vial_1") == pytest.approx(925.0)
        assert tracker.get_volume("plate_1", "A1") == pytest.approx(75.0)

    def test_multiple_dispenses_accumulate(self):
        tracker = VolumeTracker()
        plate = _make_plate(capacity=200.0)
        tracker.register_labware("plate_1", plate)

        tracker.record_dispense("plate_1", "A1", 50.0)
        tracker.record_dispense("plate_1", "A1", 30.0)
        tracker.record_dispense("plate_1", "A1", 20.0)

        assert tracker.get_volume("plate_1", "A1") == pytest.approx(100.0)

    def test_record_aspirate_validates_first(self):
        tracker = VolumeTracker()
        vial = _make_vial()
        tracker.register_labware("vial_1", vial, initial_volume_ul=10.0)

        with pytest.raises(UnderflowVolumeError):
            tracker.record_aspirate("vial_1", None, 50.0)

        # Volume unchanged after failed aspirate
        assert tracker.get_volume("vial_1") == pytest.approx(10.0)

    def test_record_dispense_validates_first(self):
        tracker = VolumeTracker()
        plate = _make_plate(capacity=200.0)
        tracker.register_labware("plate_1", plate, initial_volumes={"A1": 190.0})

        with pytest.raises(OverflowVolumeError):
            tracker.record_dispense("plate_1", "A1", 50.0)

        # Volume unchanged after failed dispense
        assert tracker.get_volume("plate_1", "A1") == pytest.approx(190.0)

    def test_sequential_aspirates_deplete_source(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=200.0)

        tracker.record_aspirate("vial_1", None, 100.0)
        tracker.record_aspirate("vial_1", None, 80.0)

        assert tracker.get_volume("vial_1") == pytest.approx(20.0)

        with pytest.raises(UnderflowVolumeError):
            tracker.record_aspirate("vial_1", None, 50.0)


# ── Pipette validation tests ─────────────────────────────────────────────────


class TestValidatePipetteVolume:

    def test_within_range_succeeds(self):
        VolumeTracker.validate_pipette_volume(100.0, min_ul=20.0, max_ul=200.0)

    def test_at_min_succeeds(self):
        VolumeTracker.validate_pipette_volume(20.0, min_ul=20.0, max_ul=200.0)

    def test_at_max_succeeds(self):
        VolumeTracker.validate_pipette_volume(200.0, min_ul=20.0, max_ul=200.0)

    def test_below_min_raises(self):
        with pytest.raises(PipetteVolumeError):
            VolumeTracker.validate_pipette_volume(5.0, min_ul=20.0, max_ul=200.0)

    def test_above_max_raises(self):
        with pytest.raises(PipetteVolumeError):
            VolumeTracker.validate_pipette_volume(300.0, min_ul=20.0, max_ul=200.0)

    def test_invalid_volume_raises_before_range_check(self):
        with pytest.raises(InvalidVolumeError):
            VolumeTracker.validate_pipette_volume(-5.0, min_ul=20.0, max_ul=200.0)

    def test_nan_raises(self):
        with pytest.raises(InvalidVolumeError):
            VolumeTracker.validate_pipette_volume(float("nan"), min_ul=20.0, max_ul=200.0)
