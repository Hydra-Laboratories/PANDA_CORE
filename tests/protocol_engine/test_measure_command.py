"""Tests for the single-position measure protocol command."""

from __future__ import annotations

import logging
import sqlite3
from unittest.mock import MagicMock, patch

from data.data_store import DataStore
from deck.labware.labware import Coordinate3D
from deck.labware.well_plate import WellPlate
from instruments.potentiostat.driver import Potentiostat
from protocol_engine.protocol import ProtocolContext


def _make_plate() -> WellPlate:
    return WellPlate(
        name="plate_1",
        model_name="test_plate",
        length_mm=127.71,
        width_mm=85.43,
        height_mm=14.10,
        rows=1,
        columns=1,
        wells={"A1": Coordinate3D(x=10.0, y=20.0, z=75.0)},
        capacity_ul=200.0,
        working_volume_ul=150.0,
    )


def _make_context(
    instrument: Potentiostat | None = None,
    store: DataStore | None = None,
    campaign_id: int | None = None,
) -> ProtocolContext:
    plate = _make_plate()
    instrument = instrument or Potentiostat(
        vendor="emstat",
        offline=True,
        measurement_height=3.0,
        name="potentiostat",
    )

    board = MagicMock()
    board.instruments = {"potentiostat": instrument}

    deck = MagicMock()
    deck.resolve = MagicMock(return_value=plate.wells["A1"])
    deck.__getitem__ = MagicMock(return_value=plate)

    return ProtocolContext(
        board=board,
        deck=deck,
        logger=logging.getLogger("test_measure_command"),
        data_store=store,
        campaign_id=campaign_id,
    )


class TestMeasureCommand:

    def test_measure_applies_measurement_height_offset(self):
        from protocol_engine.commands.measure import measure

        ctx = _make_context()

        measure(
            ctx,
            instrument="potentiostat",
            position="plate_1.A1",
            method="measure_ocp",
            method_kwargs={"duration_s": 1.0, "sample_period_s": 0.1},
        )

        ctx.board.move.assert_called_once_with(
            "potentiostat",
            (10.0, 20.0, 72.0),
        )

    def test_measure_logs_potentiostat_measurement_to_data_store(self):
        from protocol_engine.commands.measure import measure

        store = DataStore(db_path=":memory:")
        campaign_id = store.create_campaign(description="potentiostat test")
        plate = _make_plate()
        store.register_labware(campaign_id, "plate_1", plate)
        ctx = _make_context(store=store, campaign_id=campaign_id)

        result = measure(
            ctx,
            instrument="potentiostat",
            position="plate_1.A1",
            method="measure_ocp",
            method_kwargs={"duration_s": 1.0, "sample_period_s": 0.1},
        )

        assert result.technique == "ocp"

        experiment_count = store._conn.execute(
            "SELECT COUNT(*) FROM experiments"
        ).fetchone()[0]
        measurement_row = store._conn.execute(
            "SELECT technique, sample_period_s, duration_s "
            "FROM potentiostat_measurements"
        ).fetchone()

        assert experiment_count == 1
        assert measurement_row[0] == "ocp"
        assert measurement_row[1] == 0.1
        assert measurement_row[2] == 1.0

        store.close()

    def test_measure_logs_ca_to_data_store(self):
        from protocol_engine.commands.measure import measure

        store = DataStore(db_path=":memory:")
        campaign_id = store.create_campaign(description="ca test")
        plate = _make_plate()
        store.register_labware(campaign_id, "plate_1", plate)
        ctx = _make_context(store=store, campaign_id=campaign_id)

        result = measure(
            ctx,
            instrument="potentiostat",
            position="plate_1.A1",
            method="run_chronoamperometry",
            method_kwargs={"step_potential_v": -0.8, "duration_s": 1.0, "sample_period_s": 0.1},
        )

        assert result.technique == "ca"
        row = store._conn.execute(
            "SELECT technique, current_a FROM potentiostat_measurements"
        ).fetchone()
        assert row[0] == "ca"
        assert row[1] is not None  # current_a written as JSON

        store.close()

    def test_measure_logs_cv_to_data_store(self):
        from protocol_engine.commands.measure import measure

        store = DataStore(db_path=":memory:")
        campaign_id = store.create_campaign(description="cv test")
        plate = _make_plate()
        store.register_labware(campaign_id, "plate_1", plate)
        ctx = _make_context(store=store, campaign_id=campaign_id)

        result = measure(
            ctx,
            instrument="potentiostat",
            position="plate_1.A1",
            method="run_cyclic_voltammetry",
            method_kwargs={
                "initial_potential_v": 0.0,
                "vertex_potential_1_v": 0.5,
                "vertex_potential_2_v": -0.5,
                "final_potential_v": 0.0,
                "scan_rate_v_s": 0.1,
                "step_size_v": 0.05,
            },
        )

        assert result.technique == "cv"
        row = store._conn.execute(
            "SELECT technique, scan_rate_v_s FROM potentiostat_measurements"
        ).fetchone()
        assert row[0] == "cv"
        assert row[1] == 0.1

        store.close()

    def test_measure_returns_result_even_when_db_write_fails(self):
        from protocol_engine.commands.measure import measure

        store = DataStore(db_path=":memory:")
        campaign_id = store.create_campaign(description="db error test")
        plate = _make_plate()
        store.register_labware(campaign_id, "plate_1", plate)
        ctx = _make_context(store=store, campaign_id=campaign_id)

        with patch.object(store, "log_measurement", side_effect=sqlite3.OperationalError("disk full")):
            result = measure(
                ctx,
                instrument="potentiostat",
                position="plate_1.A1",
                method="measure_ocp",
                method_kwargs={"duration_s": 1.0, "sample_period_s": 0.1},
            )

        assert result.technique == "ocp"
        store.close()

    def test_measure_skips_logging_when_no_campaign_id(self):
        from protocol_engine.commands.measure import measure

        store = DataStore(db_path=":memory:")
        ctx = _make_context(store=store, campaign_id=None)

        result = measure(
            ctx,
            instrument="potentiostat",
            position="plate_1.A1",
            method="measure_ocp",
            method_kwargs={"duration_s": 1.0, "sample_period_s": 0.1},
        )

        assert result.technique == "ocp"
        count = store._conn.execute("SELECT COUNT(*) FROM potentiostat_measurements").fetchone()[0]
        assert count == 0
        store.close()
