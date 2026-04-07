"""Demo script: seed an in-memory DB and read it back in every DataReader format.

Run with:
    python demo_data_reader.py
"""

from __future__ import annotations

import json
import pprint
import tempfile
from pathlib import Path

from data.data_store import DataStore
from data.data_reader import DataReader
from protocol_engine.measurements import InstrumentMeasurement, MeasurementType


# ─── Seed helpers ─────────────────────────────────────────────────────────────

def _uvvis_measurement(wavelengths, intensities, integration_time_s=0.24):
    return InstrumentMeasurement(
        measurement_type=MeasurementType.UVVIS_SPECTRUM,
        payload={"wavelength_nm": wavelengths, "intensity_au": intensities},
        metadata={"integration_time_s": integration_time_s},
    )


def _asmi_measurement(z_positions, raw_forces, corrected_forces):
    return InstrumentMeasurement(
        measurement_type=MeasurementType.ASMI_INDENTATION,
        payload={
            "z_positions_mm": z_positions,
            "raw_forces_n": raw_forces,
            "corrected_forces_n": corrected_forces,
        },
        metadata={
            "baseline_avg": 0.005,
            "baseline_std": 0.001,
            "force_exceeded": False,
            "data_points": len(z_positions),
        },
    )


def seed_store() -> DataStore:
    store = DataStore(db_path=":memory:")

    # Campaign 1 — dye absorption screen
    cid1 = store.create_campaign(
        description="Dye absorption screen",
        deck_config='{"labware": {"plate_1": "96well"}}',
        board_config='{"instruments": {"uvvis": "ocean_ccs175"}}',
        gantry_config='{"serial_port": "/dev/ttyUSB0"}',
        protocol_config='{"protocol": ["dispense", "measure"]}',
    )
    eid_a1 = store.create_experiment(
        cid1, "plate_1", "A1",
        json.dumps([{"source": "methylene_blue", "volume_ul": 50}]),
    )
    eid_a2 = store.create_experiment(
        cid1, "plate_1", "A2",
        json.dumps([{"source": "rhodamine_b", "volume_ul": 50}]),
    )
    eid_a3 = store.create_experiment(
        cid1, "plate_1", "A3",
        json.dumps([]),
    )

    # UVVis measurements
    store.log_measurement(eid_a1, _uvvis_measurement(
        [400.0, 500.0, 600.0, 700.0], [0.08, 0.65, 0.12, 0.03],
    ))
    store.log_measurement(eid_a1, _uvvis_measurement(  # second scan same well
        [400.0, 500.0, 600.0, 700.0], [0.09, 0.66, 0.13, 0.03],
    ))
    store.log_measurement(eid_a2, _uvvis_measurement(
        [400.0, 500.0, 600.0, 700.0], [0.02, 0.03, 0.04, 0.55],
    ))
    # A3 is blank — no measurement logged

    # Campaign 2 — thin-film indentation
    cid2 = store.create_campaign(
        description="Thin-film indentation study",
        board_config='{"instruments": {"asmi": "asmi_v1"}}',
    )
    eid_b1 = store.create_experiment(
        cid2, "film_plate", "B1",
        json.dumps([{"film": "PEDOT", "thickness_nm": 120}]),
    )
    eid_b2 = store.create_experiment(
        cid2, "film_plate", "B2",
        json.dumps([{"film": "P3HT", "thickness_nm": 85}]),
    )

    z = [0.0, -0.1, -0.2, -0.3, -0.4, -0.5]
    store.log_measurement(eid_b1, _asmi_measurement(
        z, [0.005, 0.006, 0.010, 0.020, 0.045, 0.090],
              [0.000, 0.001, 0.005, 0.015, 0.040, 0.085],
    ))
    store.log_measurement(eid_b2, _asmi_measurement(
        z, [0.005, 0.007, 0.012, 0.025, 0.055, 0.110],
              [0.000, 0.002, 0.007, 0.020, 0.050, 0.105],
    ))

    return store


# ─── Demo output ──────────────────────────────────────────────────────────────

SEPARATOR = "─" * 72


def section(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def main() -> None:
    store = seed_store()
    reader = DataReader(connection=store._conn)

    # 1. List all campaigns (CampaignRecord dataclasses)
    section("1 · list_campaigns() → List[CampaignRecord]")
    for c in reader.list_campaigns():
        print(f"  [{c.id}] {c.description!r}  status={c.status}")
        print(f"       board_config : {c.board_config}")

    # 2. get_campaign() single record
    section("2 · get_campaign(1) → CampaignRecord")
    pprint.pprint(reader.get_campaign(1).__dict__)

    # 3. get_experiments() — ExperimentRecord list
    section("3 · get_experiments(campaign_id=1) → List[ExperimentRecord]")
    for e in reader.get_experiments(campaign_id=1):
        contents = json.loads(e.contents) if e.contents else []
        print(f"  [{e.id}] well={e.well_id}  contents={contents}")

    section("3b · get_experiments(campaign_id=1, well_id='A1')")
    for e in reader.get_experiments(campaign_id=1, well_id="A1"):
        print(f"  [{e.id}] {e.labware_name} / {e.well_id}")

    # 4. get_measurements() — raw dicts per experiment
    section("4 · get_measurements(experiment_id=1, table='uvvis_measurements')")
    rows = reader.get_measurements(experiment_id=1, table="uvvis_measurements")
    print(f"  {len(rows)} row(s)")
    for r in rows:
        # Blobs come back as bytes; show length instead of raw bytes
        display = {k: (f"<blob {len(v)}B>" if isinstance(v, (bytes, bytearray)) else v)
                   for k, v in r.items()}
        pprint.pprint(display, indent=4)

    # 5. get_measurements_by_campaign() — raw dicts with well_id joined
    section("5 · get_measurements_by_campaign(campaign_id=1, table='uvvis_measurements')")
    rows = reader.get_measurements_by_campaign(campaign_id=1, table="uvvis_measurements")
    print(f"  {len(rows)} row(s)  (A1×2 scans + A2×1 scan; A3 blank = 0)")
    for r in rows:
        print(f"  exp={r['experiment_id']}  well={r['well_id']}  "
              f"integration_time_s={r['integration_time_s']}")

    # ASMI
    section("5b · get_measurements_by_campaign(campaign_id=2, table='asmi_measurements')")
    rows = reader.get_measurements_by_campaign(campaign_id=2, table="asmi_measurements")
    print(f"  {len(rows)} row(s)")
    for r in rows:
        print(f"  exp={r['experiment_id']}  well={r['well_id']}  "
              f"data_points={r['data_points']}  baseline_avg={r['baseline_avg']}")

    # 6. DataFrame: experiment IDs
    section("6 · get_experiment_ids_dataframe(campaign_id=1) → DataFrame")
    df_ids = reader.get_experiment_ids_dataframe(campaign_id=1)
    print(df_ids.to_string(index=False))

    # 7. DataFrame: all instruments for one experiment
    section("7 · get_experiment_measurements_dataframe(experiment_id=1) → DataFrame")
    df_all = reader.get_experiment_measurements_dataframe(experiment_id=1)
    print(df_all.to_string(index=False))
    print()
    # Parse and pretty-print one data_json to show the payload
    payload = json.loads(df_all.iloc[0]["data_json"])
    print("  data_json of first row →")
    pprint.pprint(payload, indent=4)

    # 8. DataFrame: filtered by instrument
    section("8 · get_experiment_measurements_by_instrument_dataframe(exp=1, 'uvvis')")
    df_uvvis = reader.get_experiment_measurements_by_instrument_dataframe(
        experiment_id=1, instrument="uvvis",
    )
    print(df_uvvis.to_string(index=False))

    section("8b · same for ASMI, experiment_id=4 (campaign 2, well B1)")
    df_asmi = reader.get_experiment_measurements_by_instrument_dataframe(
        experiment_id=4, instrument="asmi",
    )
    print(df_asmi.to_string(index=False))

    # 9. CSV export
    section("9 · export_dataframe_to_csv() → CSV file")
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        csv_path = f.name
    written = reader.export_dataframe_to_csv(df_ids, csv_path)
    print(f"  Wrote: {written}")
    print(Path(written).read_text())

    store.close()
    print(f"\n{SEPARATOR}")
    print("  Done.")
    print(SEPARATOR)


if __name__ == "__main__":
    main()
