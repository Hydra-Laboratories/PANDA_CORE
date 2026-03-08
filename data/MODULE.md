# Module: data

## Purpose
SQLite persistence for self-driving lab campaigns. Tracks campaigns, experiments, measurements (UV-Vis spectra, Filmetrics thickness, camera images), and labware volume/content per well.

## Public API (`__init__.py`)
- `DataStore` — Main class owning a SQLite connection

Key methods:
- `create_campaign(description, ...)` — Start a new campaign
- `create_experiment(campaign_id, labware_name, well_id, ...)` — Log an experiment
- `log_measurement(experiment_id, result)` — Dispatch by type (UVVisSpectrum, MeasurementResult, str)
- `register_labware(campaign_id, labware_key, labware)` — Register Vial/WellPlate for tracking
- `record_dispense(campaign_id, labware_key, well_id, source_name, volume_ul)` — Track dispenses
- `get_contents(campaign_id, labware_key, well_id)` — Query well contents
- `close()` — Close DB connection

## Contract
`DataStoreInterface` in `src/contracts.py`.

## Internal Structure
- `data_store.py` — `DataStore` class with all SQL logic
- `databases/panda_data.db` — Empty template DB

## Dependencies
`instruments.filmetrics.models.MeasurementResult` (type dispatch)
`instruments.uvvis_ccs.models.UVVisSpectrum` (type dispatch + BLOB packing)

## Dependents
`protocol_engine` (optional, via ProtocolContext.data_store)

## Rules for Agents
- SAFE PARALLEL ZONE — can be modified independently
- Uses `:memory:` SQLite for testing (no file I/O)
- BLOB serialization: `struct.pack("<Nd", *floats)` for spectra
- Adding new measurement types requires a new table + dispatch branch in `log_measurement()`

## Test Command
```bash
pytest tests/data/ -v
```
