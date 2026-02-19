"""Tests for volume validation integration in pipette commands."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

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
from protocol_engine.protocol import ProtocolContext
from protocol_engine.volume_tracker import VolumeTracker


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_vial(
    capacity: float = 1500.0, working: float = 1200.0,
) -> Vial:
    return Vial(
        name="vial_1",
        model_name="test_vial",
        height_mm=66.75,
        diameter_mm=28.0,
        location=Coordinate3D(x=-30.0, y=-40.0, z=-20.0),
        capacity_ul=capacity,
        working_volume_ul=working,
    )


def _make_plate(
    capacity: float = 200.0, working: float = 150.0,
) -> WellPlate:
    return WellPlate(
        name="plate_1",
        model_name="test_plate",
        length_mm=127.0,
        width_mm=85.0,
        height_mm=14.0,
        rows=2,
        columns=3,
        wells={
            "A1": Coordinate3D(x=0.0, y=0.0, z=-5.0),
            "A2": Coordinate3D(x=10.0, y=0.0, z=-5.0),
            "A3": Coordinate3D(x=20.0, y=0.0, z=-5.0),
            "B1": Coordinate3D(x=0.0, y=-8.0, z=-5.0),
            "B2": Coordinate3D(x=10.0, y=-8.0, z=-5.0),
            "B3": Coordinate3D(x=20.0, y=-8.0, z=-5.0),
        },
        capacity_ul=capacity,
        working_volume_ul=working,
    )


def _build_tracker(
    vial_initial: float = 1000.0,
    plate_capacity: float = 200.0,
    plate_initials: dict[str, float] | None = None,
) -> VolumeTracker:
    """Build a tracker with a vial and 2x3 plate registered."""
    tracker = VolumeTracker()
    tracker.register_labware(
        "vial_1", _make_vial(), initial_volume_ul=vial_initial,
    )
    tracker.register_labware(
        "plate_1", _make_plate(capacity=plate_capacity),
        initial_volumes=plate_initials,
    )
    return tracker


def _make_pipette_mock(min_vol: float = 20.0, max_vol: float = 200.0) -> MagicMock:
    """Return a mock pipette with config attributes for volume range."""
    pipette = MagicMock()
    pipette.config = MagicMock()
    pipette.config.min_volume = min_vol
    pipette.config.max_volume = max_vol
    pipette.aspirate.return_value = MagicMock(success=True, volume_ul=100.0)
    pipette.dispense.return_value = MagicMock(success=True, volume_ul=100.0)
    pipette.mix.return_value = MagicMock(success=True, volume_ul=50.0, repetitions=3)
    return pipette


def _ctx_with_tracker(
    tracker: VolumeTracker | None = None,
    min_vol: float = 20.0,
    max_vol: float = 200.0,
) -> ProtocolContext:
    """Build a ProtocolContext with a volume tracker and mock hardware."""
    board = MagicMock()
    deck = MagicMock()
    deck.resolve.return_value = Coordinate3D(x=0.0, y=0.0, z=-5.0)

    pipette = _make_pipette_mock(min_vol, max_vol)
    board.instruments = {"pipette": pipette}

    # deck.__getitem__ for serial_transfer
    deck.__getitem__ = MagicMock(return_value=_make_plate())

    return ProtocolContext(
        board=board,
        deck=deck,
        logger=logging.getLogger("test_vol_validation"),
        volume_tracker=tracker,
    )


# ── Backward compatibility ───────────────────────────────────────────────────


class TestBackwardCompatibility:
    """All commands must work unchanged when volume_tracker is None."""

    def test_transfer_works_without_tracker(self):
        from protocol_engine.commands.pipette import transfer

        ctx = _ctx_with_tracker(tracker=None)
        transfer(ctx, source="vial_1", destination="plate_1.A1", volume_ul=100.0)
        ctx.board.instruments["pipette"].aspirate.assert_called_once()
        ctx.board.instruments["pipette"].dispense.assert_called_once()

    def test_aspirate_works_without_tracker(self):
        from protocol_engine.commands.pipette import aspirate

        ctx = _ctx_with_tracker(tracker=None)
        aspirate(ctx, position="vial_1", volume_ul=100.0)
        ctx.board.instruments["pipette"].aspirate.assert_called_once()

    def test_dispense_works_without_tracker(self):
        from protocol_engine.commands.pipette import dispense

        ctx = _ctx_with_tracker(tracker=None)
        dispense(ctx, position="plate_1.A1", volume_ul=100.0)
        ctx.board.instruments["pipette"].dispense.assert_called_once()

    def test_mix_works_without_tracker(self):
        from protocol_engine.commands.pipette import mix

        ctx = _ctx_with_tracker(tracker=None)
        mix(ctx, position="plate_1.A1", volume_ul=50.0)
        ctx.board.instruments["pipette"].mix.assert_called_once()


# ── Transfer with volume tracking ────────────────────────────────────────────


class TestTransferVolumeValidation:

    def test_validates_source_underflow(self):
        from protocol_engine.commands.pipette import transfer

        tracker = _build_tracker(vial_initial=30.0)
        ctx = _ctx_with_tracker(tracker)

        with pytest.raises(UnderflowVolumeError):
            transfer(ctx, source="vial_1", destination="plate_1.A1", volume_ul=100.0)

        # Hardware should NOT have been called
        ctx.board.instruments["pipette"].aspirate.assert_not_called()

    def test_validates_destination_overflow(self):
        from protocol_engine.commands.pipette import transfer

        tracker = _build_tracker(
            vial_initial=1000.0,
            plate_capacity=200.0,
            plate_initials={"A1": 180.0},
        )
        ctx = _ctx_with_tracker(tracker)

        with pytest.raises(OverflowVolumeError):
            transfer(ctx, source="vial_1", destination="plate_1.A1", volume_ul=50.0)

        ctx.board.instruments["pipette"].aspirate.assert_not_called()

    def test_updates_both_volumes(self):
        from protocol_engine.commands.pipette import transfer

        tracker = _build_tracker(vial_initial=1000.0)
        ctx = _ctx_with_tracker(tracker)

        transfer(ctx, source="vial_1", destination="plate_1.A1", volume_ul=75.0)

        assert tracker.get_volume("vial_1") == pytest.approx(925.0)
        assert tracker.get_volume("plate_1", "A1") == pytest.approx(75.0)

    def test_validates_pipette_min_volume(self):
        from protocol_engine.commands.pipette import transfer

        tracker = _build_tracker(vial_initial=1000.0)
        ctx = _ctx_with_tracker(tracker, min_vol=20.0, max_vol=200.0)

        with pytest.raises(PipetteVolumeError):
            transfer(ctx, source="vial_1", destination="plate_1.A1", volume_ul=5.0)

    def test_validates_pipette_max_volume(self):
        from protocol_engine.commands.pipette import transfer

        tracker = _build_tracker(vial_initial=1000.0, plate_capacity=500.0)
        ctx = _ctx_with_tracker(tracker, min_vol=20.0, max_vol=200.0)

        with pytest.raises(PipetteVolumeError):
            transfer(ctx, source="vial_1", destination="plate_1.A1", volume_ul=300.0)

    def test_negative_volume_raises(self):
        from protocol_engine.commands.pipette import transfer

        tracker = _build_tracker()
        ctx = _ctx_with_tracker(tracker)

        with pytest.raises(InvalidVolumeError):
            transfer(ctx, source="vial_1", destination="plate_1.A1", volume_ul=-10.0)

    def test_zero_volume_raises(self):
        from protocol_engine.commands.pipette import transfer

        tracker = _build_tracker()
        ctx = _ctx_with_tracker(tracker)

        with pytest.raises(InvalidVolumeError):
            transfer(ctx, source="vial_1", destination="plate_1.A1", volume_ul=0.0)


# ── Aspirate with volume tracking ────────────────────────────────────────────


class TestAspirateVolumeValidation:

    def test_validates_source_volume(self):
        from protocol_engine.commands.pipette import aspirate

        tracker = _build_tracker(vial_initial=30.0)
        ctx = _ctx_with_tracker(tracker)

        with pytest.raises(UnderflowVolumeError):
            aspirate(ctx, position="vial_1", volume_ul=100.0)

        ctx.board.instruments["pipette"].aspirate.assert_not_called()

    def test_records_volume_decrease(self):
        from protocol_engine.commands.pipette import aspirate

        tracker = _build_tracker(vial_initial=500.0)
        ctx = _ctx_with_tracker(tracker)

        aspirate(ctx, position="vial_1", volume_ul=100.0)
        assert tracker.get_volume("vial_1") == pytest.approx(400.0)

    def test_validates_pipette_range(self):
        from protocol_engine.commands.pipette import aspirate

        tracker = _build_tracker(vial_initial=1000.0)
        ctx = _ctx_with_tracker(tracker, min_vol=20.0, max_vol=200.0)

        with pytest.raises(PipetteVolumeError):
            aspirate(ctx, position="vial_1", volume_ul=5.0)


# ── Dispense with volume tracking ────────────────────────────────────────────


class TestDispenseVolumeValidation:

    def test_validates_destination_overflow(self):
        from protocol_engine.commands.pipette import dispense

        tracker = _build_tracker(plate_capacity=200.0, plate_initials={"A1": 190.0})
        ctx = _ctx_with_tracker(tracker)

        with pytest.raises(OverflowVolumeError):
            dispense(ctx, position="plate_1.A1", volume_ul=50.0)

        ctx.board.instruments["pipette"].dispense.assert_not_called()

    def test_records_volume_increase(self):
        from protocol_engine.commands.pipette import dispense

        tracker = _build_tracker()
        ctx = _ctx_with_tracker(tracker)

        dispense(ctx, position="plate_1.A1", volume_ul=50.0)
        assert tracker.get_volume("plate_1", "A1") == pytest.approx(50.0)

    def test_validates_pipette_range(self):
        from protocol_engine.commands.pipette import dispense

        tracker = _build_tracker()
        ctx = _ctx_with_tracker(tracker, min_vol=20.0, max_vol=200.0)

        with pytest.raises(PipetteVolumeError):
            dispense(ctx, position="plate_1.A1", volume_ul=5.0)


# ── Mix with volume tracking ─────────────────────────────────────────────────


class TestMixVolumeValidation:

    def test_mix_does_not_change_tracked_volume(self):
        from protocol_engine.commands.pipette import mix

        tracker = _build_tracker(plate_initials={"A1": 100.0})
        ctx = _ctx_with_tracker(tracker)

        mix(ctx, position="plate_1.A1", volume_ul=50.0)
        assert tracker.get_volume("plate_1", "A1") == pytest.approx(100.0)

    def test_mix_validates_well_has_enough_volume(self):
        from protocol_engine.commands.pipette import mix

        tracker = _build_tracker(plate_initials={"A1": 10.0})
        ctx = _ctx_with_tracker(tracker)

        with pytest.raises(UnderflowVolumeError):
            mix(ctx, position="plate_1.A1", volume_ul=50.0)

        ctx.board.instruments["pipette"].mix.assert_not_called()

    def test_mix_validates_pipette_range(self):
        from protocol_engine.commands.pipette import mix

        tracker = _build_tracker(plate_initials={"A1": 100.0})
        ctx = _ctx_with_tracker(tracker, min_vol=20.0, max_vol=200.0)

        with pytest.raises(PipetteVolumeError):
            mix(ctx, position="plate_1.A1", volume_ul=5.0)


# ── Serial transfer with volume tracking ─────────────────────────────────────


class TestSerialTransferVolumeValidation:

    def test_cumulative_source_depletion(self):
        from protocol_engine.commands.pipette import serial_transfer

        tracker = _build_tracker(vial_initial=100.0, plate_capacity=200.0)
        ctx = _ctx_with_tracker(tracker)
        ctx.deck.__getitem__ = MagicMock(return_value=_make_plate())

        serial_transfer(
            ctx, source="vial_1", plate="plate_1", axis="A",
            volumes=[30.0, 30.0, 30.0],
        )

        assert tracker.get_volume("vial_1") == pytest.approx(10.0)
        assert tracker.get_volume("plate_1", "A1") == pytest.approx(30.0)
        assert tracker.get_volume("plate_1", "A2") == pytest.approx(30.0)
        assert tracker.get_volume("plate_1", "A3") == pytest.approx(30.0)

    def test_cumulative_source_underflow_raises_midway(self):
        from protocol_engine.commands.pipette import serial_transfer

        tracker = _build_tracker(vial_initial=50.0, plate_capacity=200.0)
        ctx = _ctx_with_tracker(tracker)
        ctx.deck.__getitem__ = MagicMock(return_value=_make_plate())

        with pytest.raises(UnderflowVolumeError):
            serial_transfer(
                ctx, source="vial_1", plate="plate_1", axis="A",
                volumes=[30.0, 30.0, 30.0],
            )

        # First transfer succeeded, second failed partway
        assert tracker.get_volume("plate_1", "A1") == pytest.approx(30.0)

    def test_destination_overflow_raises(self):
        from protocol_engine.commands.pipette import serial_transfer

        tracker = _build_tracker(
            vial_initial=1000.0,
            plate_capacity=200.0,
            plate_initials={"A2": 190.0},
        )
        ctx = _ctx_with_tracker(tracker)
        ctx.deck.__getitem__ = MagicMock(return_value=_make_plate())

        with pytest.raises(OverflowVolumeError):
            serial_transfer(
                ctx, source="vial_1", plate="plate_1", axis="A",
                volumes=[50.0, 50.0, 50.0],
            )
