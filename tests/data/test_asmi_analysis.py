"""Tests for ASMI SQL read/unpack helpers."""

from __future__ import annotations

import pytest

from data.analysis.asmi import (
    ASMIRecord,
    load_asmi_by_campaign,
    load_asmi_by_experiment,
    load_asmi_by_well,
    unpack_asmi_measurement,
)
from data.data_reader import DataReader
from data.data_store import DataStore
from protocol_engine.measurements import InstrumentMeasurement, MeasurementType


def _seed_asmi_store() -> DataStore:
    store = DataStore(db_path=":memory:")
    campaign_id = store.create_campaign(description="asmi test")
    exp_a1 = store.create_experiment(campaign_id, "plate_1", "A1", "[]")
    exp_b2 = store.create_experiment(campaign_id, "plate_1", "B2", "[]")

    first = InstrumentMeasurement(
        measurement_type=MeasurementType.ASMI_INDENTATION,
        payload={
            "z_positions_mm": [0.0, -0.1, -0.2],
            "raw_forces_n": [0.01, 0.04, 0.08],
            "corrected_forces_n": [0.0, 0.03, 0.07],
        },
        metadata={
            "baseline_avg": 0.01,
            "baseline_std": 0.002,
            "force_exceeded": False,
            "data_points": 3,
        },
    )
    second = InstrumentMeasurement(
        measurement_type=MeasurementType.ASMI_INDENTATION,
        payload={
            "z_positions_mm": [0.0, -0.2, -0.4],
            "raw_forces_n": [0.02, 0.08, 0.16],
            "corrected_forces_n": [0.0, 0.06, 0.14],
        },
        metadata={
            "baseline_avg": 0.02,
            "baseline_std": 0.003,
            "force_exceeded": True,
            "data_points": 3,
        },
    )

    measurement_a1 = store.log_measurement(exp_a1, first)
    measurement_b2 = store.log_measurement(exp_b2, second)
    store._conn.execute(
        "UPDATE asmi_measurements "
        "SET step_size_mm = ?, z_target_mm = ?, force_limit_n = ? "
        "WHERE id = ?",
        (0.01, -1.5, 0.25, measurement_a1),
    )
    store._conn.execute(
        "UPDATE asmi_measurements "
        "SET step_size_mm = ?, z_target_mm = ?, force_limit_n = ? "
        "WHERE id = ?",
        (0.02, -2.0, 0.50, measurement_b2),
    )
    store._conn.commit()
    return store


@pytest.fixture()
def seeded_reader() -> DataReader:
    store = _seed_asmi_store()
    reader = DataReader(connection=store._conn)
    yield reader
    store.close()


class TestUnpackASMIMeasurement:

    def test_unpacks_blob_fields_and_metadata(self, seeded_reader: DataReader):
        row = seeded_reader.get_measurements(1, table="asmi_measurements")[0]

        record = unpack_asmi_measurement(
            z_positions_blob=row["z_positions"],
            raw_forces_blob=row["raw_forces"],
            corrected_forces_blob=row["corrected_forces"],
            baseline_avg=row["baseline_avg"],
            baseline_std=row["baseline_std"],
            force_exceeded=row["force_exceeded"],
            data_points=row["data_points"],
            step_size_mm=row["step_size_mm"],
            z_target_mm=row["z_target_mm"],
            force_limit_n=row["force_limit_n"],
            timestamp=row["timestamp"],
            experiment_id=row["experiment_id"],
            measurement_id=row["id"],
        )

        assert isinstance(record, ASMIRecord)
        assert record.z_positions == (0.0, -0.1, -0.2)
        assert record.raw_forces == (0.01, 0.04, 0.08)
        assert record.corrected_forces == (0.0, 0.03, 0.07)
        assert record.baseline_avg == pytest.approx(0.01)
        assert record.baseline_std == pytest.approx(0.002)
        assert record.force_exceeded is False
        assert record.step_size_mm == pytest.approx(0.01)
        assert record.z_target_mm == pytest.approx(-1.5)
        assert record.force_limit_n == pytest.approx(0.25)


class TestLoadASMI:

    def test_load_by_experiment(self, seeded_reader: DataReader):
        records = load_asmi_by_experiment(seeded_reader, experiment_id=1)
        assert len(records) == 1
        assert records[0].experiment_id == 1
        assert records[0].timestamp is not None

    def test_load_by_campaign(self, seeded_reader: DataReader):
        records = load_asmi_by_campaign(seeded_reader, campaign_id=1)
        assert len(records) == 2
        assert {record.well_id for record in records} == {"A1", "B2"}
        assert {record.labware_name for record in records} == {"plate_1"}

    def test_load_by_well(self, seeded_reader: DataReader):
        records = load_asmi_by_well(seeded_reader, campaign_id=1, well_id="b2")
        assert len(records) == 1
        assert records[0].well_id == "B2"
        assert records[0].force_exceeded is True

    def test_load_empty_results(self, seeded_reader: DataReader):
        assert load_asmi_by_experiment(seeded_reader, experiment_id=999) == []
        assert load_asmi_by_campaign(seeded_reader, campaign_id=999) == []
        assert load_asmi_by_well(seeded_reader, campaign_id=1, well_id="H12") == []
