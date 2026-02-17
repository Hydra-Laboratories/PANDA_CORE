"""Tests for DataStore.record_aspirate — source volume tracking."""

from __future__ import annotations

import pytest

from data.data_store import DataStore
from deck.labware.labware import Coordinate3D
from deck.labware.vial import Vial
from deck.labware.well_plate import WellPlate


def _store() -> DataStore:
    return DataStore(db_path=":memory:")


def _make_vial() -> Vial:
    return Vial(
        name="vial_1",
        model_name="test_vial",
        height_mm=50.0,
        diameter_mm=20.0,
        location=Coordinate3D(x=0.0, y=0.0, z=0.0),
        capacity_ul=5000.0,
        working_volume_ul=4000.0,
    )


def _make_plate() -> WellPlate:
    return WellPlate(
        name="plate_1",
        model_name="test_96",
        length_mm=127.71,
        width_mm=85.43,
        height_mm=14.10,
        rows=2,
        columns=2,
        wells={
            "A1": Coordinate3D(x=0.0, y=0.0, z=-5.0),
            "A2": Coordinate3D(x=10.0, y=0.0, z=-5.0),
            "B1": Coordinate3D(x=0.0, y=-8.0, z=-5.0),
            "B2": Coordinate3D(x=10.0, y=-8.0, z=-5.0),
        },
        capacity_ul=200.0,
        working_volume_ul=150.0,
    )


class TestRecordAspirate:

    def test_decrements_current_volume(self):
        store = _store()
        cid = store.create_campaign(description="test")
        store.register_labware(cid, "vial_1", _make_vial())

        # Seed volume first via dispense
        store.record_dispense(cid, "vial_1", None, "initial", 1000.0)
        store.record_aspirate(cid, "vial_1", None, 200.0)

        row = store._conn.execute(
            "SELECT current_volume_ul FROM labware "
            "WHERE campaign_id = ? AND labware_key = ? AND well_id IS NULL",
            (cid, "vial_1"),
        ).fetchone()
        assert row[0] == pytest.approx(800.0)
        store.close()

    def test_aspirate_from_well_plate(self):
        store = _store()
        cid = store.create_campaign(description="test")
        store.register_labware(cid, "plate_1", _make_plate())

        store.record_dispense(cid, "plate_1", "A1", "vial_1", 100.0)
        store.record_aspirate(cid, "plate_1", "A1", 30.0)

        row = store._conn.execute(
            "SELECT current_volume_ul FROM labware "
            "WHERE campaign_id = ? AND labware_key = ? AND well_id = ?",
            (cid, "plate_1", "A1"),
        ).fetchone()
        assert row[0] == pytest.approx(70.0)
        store.close()

    def test_multiple_aspirates_deplete(self):
        store = _store()
        cid = store.create_campaign(description="test")
        store.register_labware(cid, "vial_1", _make_vial())

        store.record_dispense(cid, "vial_1", None, "initial", 500.0)
        store.record_aspirate(cid, "vial_1", None, 100.0)
        store.record_aspirate(cid, "vial_1", None, 150.0)

        row = store._conn.execute(
            "SELECT current_volume_ul FROM labware "
            "WHERE campaign_id = ? AND labware_key = ? AND well_id IS NULL",
            (cid, "vial_1"),
        ).fetchone()
        assert row[0] == pytest.approx(250.0)
        store.close()

    def test_aspirate_unknown_labware_raises(self):
        store = _store()
        cid = store.create_campaign(description="test")

        with pytest.raises(ValueError, match="not registered"):
            store.record_aspirate(cid, "nonexistent", None, 50.0)
        store.close()

    def test_aspirate_and_dispense_roundtrip(self):
        store = _store()
        cid = store.create_campaign(description="test")
        store.register_labware(cid, "vial_1", _make_vial())
        store.register_labware(cid, "plate_1", _make_plate())

        # Seed source vial
        store.record_dispense(cid, "vial_1", None, "initial", 1000.0)

        # Transfer: aspirate from vial, dispense to plate
        store.record_aspirate(cid, "vial_1", None, 75.0)
        store.record_dispense(cid, "plate_1", "A1", "vial_1", 75.0)

        vial_vol = store._conn.execute(
            "SELECT current_volume_ul FROM labware "
            "WHERE campaign_id = ? AND labware_key = ? AND well_id IS NULL",
            (cid, "vial_1"),
        ).fetchone()[0]
        well_vol = store._conn.execute(
            "SELECT current_volume_ul FROM labware "
            "WHERE campaign_id = ? AND labware_key = ? AND well_id = ?",
            (cid, "plate_1", "A1"),
        ).fetchone()[0]

        assert vial_vol == pytest.approx(925.0)
        assert well_vol == pytest.approx(75.0)
        store.close()
