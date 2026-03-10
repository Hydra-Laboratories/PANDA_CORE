"""Tests for the DataReader read-side query layer."""

from __future__ import annotations

import json
import sqlite3

import pytest

from data.data_reader import CampaignRecord, DataReader, ExperimentRecord, LabwareRecord
from data.data_store import DataStore
from protocol_engine.measurements import InstrumentMeasurement, MeasurementType


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _seed_store() -> DataStore:
    """Create an in-memory DataStore with seeded data."""
    store = DataStore(db_path=":memory:")
    cid = store.create_campaign(
        description="test campaign",
        deck_config='{"labware": {}}',
        board_config='{"instruments": {}}',
        gantry_config='{"serial_port": "/dev/null"}',
        protocol_config='{"protocol": []}',
    )
    eid1 = store.create_experiment(cid, "plate_1", "A1", '[{"source": "dye", "volume_ul": 50}]')
    eid2 = store.create_experiment(cid, "plate_1", "A2", "[]")

    measurement = InstrumentMeasurement(
        measurement_type=MeasurementType.UVVIS_SPECTRUM,
        payload={
            "wavelength_nm": [400.0, 500.0, 600.0],
            "intensity_au": [0.1, 0.5, 0.3],
        },
        metadata={"integration_time_s": 0.24},
    )
    store.log_measurement(eid1, measurement)
    store.log_measurement(eid2, measurement)
    return store


@pytest.fixture()
def seeded_reader() -> DataReader:
    store = _seed_store()
    reader = DataReader(connection=store._conn)
    yield reader
    store.close()


# ─── Campaign queries ────────────────────────────────────────────────────────


class TestGetCampaign:

    def test_returns_campaign_record(self, seeded_reader: DataReader):
        campaign = seeded_reader.get_campaign(1)
        assert isinstance(campaign, CampaignRecord)
        assert campaign.id == 1
        assert campaign.description == "test campaign"

    def test_returns_none_for_missing_campaign(self, seeded_reader: DataReader):
        assert seeded_reader.get_campaign(999) is None

    def test_campaign_has_config_snapshots(self, seeded_reader: DataReader):
        campaign = seeded_reader.get_campaign(1)
        assert campaign.deck_config == '{"labware": {}}'
        assert campaign.board_config == '{"instruments": {}}'
        assert campaign.gantry_config == '{"serial_port": "/dev/null"}'
        assert campaign.protocol_config == '{"protocol": []}'

    def test_campaign_has_created_at(self, seeded_reader: DataReader):
        campaign = seeded_reader.get_campaign(1)
        assert campaign.created_at is not None


class TestListCampaigns:

    def test_returns_all_campaigns(self, seeded_reader: DataReader):
        campaigns = seeded_reader.list_campaigns()
        assert len(campaigns) == 1
        assert campaigns[0].description == "test campaign"


# ─── Experiment queries ──────────────────────────────────────────────────────


class TestGetExperiments:

    def test_returns_experiments_for_campaign(self, seeded_reader: DataReader):
        experiments = seeded_reader.get_experiments(campaign_id=1)
        assert len(experiments) == 2
        assert all(isinstance(e, ExperimentRecord) for e in experiments)

    def test_filter_by_well_id(self, seeded_reader: DataReader):
        experiments = seeded_reader.get_experiments(campaign_id=1, well_id="A1")
        assert len(experiments) == 1
        assert experiments[0].well_id == "A1"

    def test_filter_by_labware_name(self, seeded_reader: DataReader):
        experiments = seeded_reader.get_experiments(campaign_id=1, labware_name="plate_1")
        assert len(experiments) == 2

    def test_returns_empty_for_missing_campaign(self, seeded_reader: DataReader):
        assert seeded_reader.get_experiments(campaign_id=999) == []

    def test_experiment_has_contents(self, seeded_reader: DataReader):
        experiments = seeded_reader.get_experiments(campaign_id=1, well_id="A1")
        contents = json.loads(experiments[0].contents)
        assert contents[0]["source"] == "dye"


# ─── Labware queries ─────────────────────────────────────────────────────────


class TestGetLabware:

    def test_returns_labware_for_campaign(self):
        store = DataStore(db_path=":memory:")
        cid = store.create_campaign(description="labware test")

        from deck.labware.vial import Vial
        from deck.labware.labware import Coordinate3D

        vial = Vial(
            name="test_vial",
            model_name="standard",
            height_mm=66.75,
            diameter_mm=28.0,
            location=Coordinate3D(x=-30.0, y=-40.0, z=-20.0),
            capacity_ul=1500.0,
            working_volume_ul=1200.0,
        )
        store.register_labware(cid, "vial_1", vial)

        reader = DataReader(connection=store._conn)
        labware = reader.get_labware(campaign_id=cid)
        assert len(labware) == 1
        assert isinstance(labware[0], LabwareRecord)
        assert labware[0].labware_key == "vial_1"
        assert labware[0].labware_type == "vial"
        assert labware[0].total_volume_ul == 1500.0

        store.close()

    def test_returns_empty_for_no_labware(self, seeded_reader: DataReader):
        assert seeded_reader.get_labware(campaign_id=1) == []


# ─── Measurement queries ─────────────────────────────────────────────────────


class TestGetMeasurementsByExperiment:

    def test_returns_raw_rows(self, seeded_reader: DataReader):
        rows = seeded_reader.get_measurements(experiment_id=1, table="uvvis_measurements")
        assert len(rows) == 1
        assert "experiment_id" in rows[0]
        assert "wavelengths" in rows[0]

    def test_returns_empty_for_no_measurements(self, seeded_reader: DataReader):
        rows = seeded_reader.get_measurements(experiment_id=999, table="uvvis_measurements")
        assert rows == []

    def test_rejects_invalid_table_name(self, seeded_reader: DataReader):
        with pytest.raises(ValueError, match="not a valid measurement table"):
            seeded_reader.get_measurements(experiment_id=1, table="users; DROP TABLE--")


class TestGetMeasurementsByCampaign:

    def test_returns_all_measurements_for_campaign(self, seeded_reader: DataReader):
        rows = seeded_reader.get_measurements_by_campaign(
            campaign_id=1, table="uvvis_measurements",
        )
        assert len(rows) == 2

    def test_includes_well_id_in_results(self, seeded_reader: DataReader):
        rows = seeded_reader.get_measurements_by_campaign(
            campaign_id=1, table="uvvis_measurements",
        )
        well_ids = {r["well_id"] for r in rows}
        assert well_ids == {"A1", "A2"}

    def test_returns_empty_for_missing_campaign(self, seeded_reader: DataReader):
        rows = seeded_reader.get_measurements_by_campaign(
            campaign_id=999, table="uvvis_measurements",
        )
        assert rows == []


# ─── Context manager ─────────────────────────────────────────────────────────


class TestContextManager:

    def test_context_manager(self):
        store = _seed_store()
        with DataReader(connection=store._conn) as reader:
            campaign = reader.get_campaign(1)
            assert campaign is not None
        store.close()


class TestConstructor:

    def test_requires_db_path_or_connection(self):
        with pytest.raises(ValueError, match="Either db_path or connection"):
            DataReader()
