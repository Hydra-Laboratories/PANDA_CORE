"""Tests for dry-run protocol simulation."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from deck.labware.labware import Coordinate3D
from deck.labware.vial import Vial
from deck.labware.well_plate import WellPlate
from protocol_engine.dry_run import DryRunResult, dry_run
from protocol_engine.protocol import Protocol, ProtocolStep
from protocol_engine.volume_tracker import VolumeTracker


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_vial(
    capacity: float = 1500.0,
    working: float = 1200.0,
) -> Vial:
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
    rows: int = 2,
    columns: int = 2,
    capacity: float = 200.0,
    working: float = 150.0,
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


def _make_context(tracker=None, deck_items=None):
    ctx = MagicMock()
    ctx.volume_tracker = tracker
    if deck_items:
        ctx.deck.__getitem__ = lambda self, key: deck_items[key]
    return ctx


def _noop_handler(context, **kwargs):
    pass


# ── Tests ────────────────────────────────────────────────────────────────────


class TestDryRunCleanProtocol:

    def test_no_volume_tracker_returns_success(self):
        protocol = Protocol(steps=[])
        ctx = _make_context(tracker=None)
        result = dry_run(protocol, ctx)

        assert result.success is True
        assert result.depletions == []

    def test_empty_protocol_returns_success(self):
        tracker = VolumeTracker()
        vial = _make_vial()
        tracker.register_labware("vial_1", vial, initial_volume_ul=500.0)

        protocol = Protocol(steps=[])
        ctx = _make_context(tracker=tracker)
        result = dry_run(protocol, ctx)

        assert result.success is True
        assert result.depletions == []

    def test_clean_aspirate_returns_success(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=500.0)

        steps = [
            ProtocolStep(
                index=0,
                command_name="aspirate",
                handler=_noop_handler,
                args={"position": "vial_1", "volume_ul": 100.0},
            ),
        ]
        protocol = Protocol(steps=steps)
        ctx = _make_context(tracker=tracker)
        result = dry_run(protocol, ctx)

        assert result.success is True
        assert result.depletions == []


class TestDryRunDetectsUnderflow:

    def test_underflow_detected_at_correct_step(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=50.0)

        steps = [
            ProtocolStep(
                index=0,
                command_name="aspirate",
                handler=_noop_handler,
                args={"position": "vial_1", "volume_ul": 100.0},
            ),
        ]
        protocol = Protocol(steps=steps)
        ctx = _make_context(tracker=tracker)
        result = dry_run(protocol, ctx)

        assert result.success is False
        assert len(result.depletions) == 1
        assert result.depletions[0].step_index == 0
        assert result.depletions[0].event_type == "underflow"
        assert result.depletions[0].labware_key == "vial_1"

    def test_multiple_depletions_all_found(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=50.0)

        steps = [
            ProtocolStep(
                index=0,
                command_name="aspirate",
                handler=_noop_handler,
                args={"position": "vial_1", "volume_ul": 100.0},
            ),
            ProtocolStep(
                index=1,
                command_name="aspirate",
                handler=_noop_handler,
                args={"position": "vial_1", "volume_ul": 200.0},
            ),
        ]
        protocol = Protocol(steps=steps)
        ctx = _make_context(tracker=tracker)
        result = dry_run(protocol, ctx)

        assert result.success is False
        assert len(result.depletions) == 2


class TestDryRunDoesNotModifyOriginal:

    def test_original_tracker_unchanged(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=500.0)

        steps = [
            ProtocolStep(
                index=0,
                command_name="aspirate",
                handler=_noop_handler,
                args={"position": "vial_1", "volume_ul": 100.0},
            ),
        ]
        protocol = Protocol(steps=steps)
        ctx = _make_context(tracker=tracker)
        dry_run(protocol, ctx)

        assert tracker.get_volume("vial_1") == pytest.approx(500.0)


class TestDryRunTransfer:

    def test_transfer_simulates_aspirate_and_dispense(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)
        plate = _make_plate(capacity=200.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=500.0)
        tracker.register_labware("plate_1", plate)

        steps = [
            ProtocolStep(
                index=0,
                command_name="transfer",
                handler=_noop_handler,
                args={
                    "source": "vial_1",
                    "destination": "plate_1.A1",
                    "volume_ul": 100.0,
                },
            ),
        ]
        protocol = Protocol(steps=steps)
        ctx = _make_context(tracker=tracker)
        result = dry_run(protocol, ctx)

        assert result.success is True
        # Check final volumes reflect the transfer
        assert result.final_volumes[("vial_1", None)] == pytest.approx(400.0)
        assert result.final_volumes[("plate_1", "A1")] == pytest.approx(100.0)

    def test_transfer_overflow_detected(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)
        plate = _make_plate(capacity=200.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=500.0)
        tracker.register_labware(
            "plate_1", plate, initial_volumes={"A1": 150.0},
        )

        steps = [
            ProtocolStep(
                index=0,
                command_name="transfer",
                handler=_noop_handler,
                args={
                    "source": "vial_1",
                    "destination": "plate_1.A1",
                    "volume_ul": 100.0,
                },
            ),
        ]
        protocol = Protocol(steps=steps)
        ctx = _make_context(tracker=tracker)
        result = dry_run(protocol, ctx)

        assert result.success is False
        assert any(d.event_type == "overflow" for d in result.depletions)


class TestDryRunSkipsUnknownCommands:

    def test_unknown_command_skipped(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=500.0)

        steps = [
            ProtocolStep(
                index=0,
                command_name="move",
                handler=_noop_handler,
                args={"instrument": "pipette", "position": "vial_1"},
            ),
        ]
        protocol = Protocol(steps=steps)
        ctx = _make_context(tracker=tracker)
        result = dry_run(protocol, ctx)

        assert result.success is True


class TestDryRunMix:

    def test_mix_validates_volume_available(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=10.0)

        steps = [
            ProtocolStep(
                index=0,
                command_name="mix",
                handler=_noop_handler,
                args={"position": "vial_1", "volume_ul": 100.0},
            ),
        ]
        protocol = Protocol(steps=steps)
        ctx = _make_context(tracker=tracker)
        result = dry_run(protocol, ctx)

        assert result.success is False
        assert len(result.depletions) == 1
        assert result.depletions[0].event_type == "underflow"


class TestDryRunFinalVolumes:

    def test_final_volumes_populated(self):
        tracker = VolumeTracker()
        vial = _make_vial(capacity=1500.0)
        tracker.register_labware("vial_1", vial, initial_volume_ul=500.0)

        protocol = Protocol(steps=[])
        ctx = _make_context(tracker=tracker)
        result = dry_run(protocol, ctx)

        assert ("vial_1", None) in result.final_volumes
        assert result.final_volumes[("vial_1", None)] == pytest.approx(500.0)
