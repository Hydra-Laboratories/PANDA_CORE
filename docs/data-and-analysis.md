# Data and Analysis

PANDA Core includes a local SQLite-backed persistence layer for campaigns, experiments, measurements, and tracked labware contents.

## Main Components

- `data.data_store`: database creation and persistence API
- `data.data_reader`: read/query helpers
- `data.analysis.uvvis`: UV-Vis analysis helpers
- `data.analysis.asmi`: ASMI analysis helpers

## Stored Concepts

The data layer models:

- campaigns
- experiments
- UV-Vis measurements
- Filmetrics measurements
- camera measurements
- ASMI measurements
- labware volume/content tracking

## Runtime Integration

When `ProtocolContext.data_store` and `ProtocolContext.campaign_id` are set, relevant protocol commands can persist:

- measurements
- transfer/dispense state
- campaign and experiment lineage

This design allows protocol execution to remain the same when persistence is absent while enabling stateful experiment tracking when it is present.

## Recommended Usage

- Use an on-disk database for long-lived campaigns
- Use `:memory:` in tests where persistence should be isolated
- Treat schema changes as migration-worthy changes, not casual edits

## Example: fake ASMI SQL roundtrip

To verify the ASMI read helpers without hardware, run:

```bash
PYTHONPATH=src:. python setup/asmi_sql_roundtrip_example.py
```

That script:

1. generates synthetic indentation data with `ASMI(offline=True)`
2. stores it in a temporary SQLite database
3. loads it back with:
   - `load_asmi_by_experiment()`
   - `load_asmi_by_campaign()`
   - `load_asmi_by_well()`

The offline driver currently generates simple flat fake force data, so this example verifies the SQL read/unpack plumbing rather than realistic indentation physics.

## TODO(manual)

- Add backup and retention expectations for the lab database
- Document where production databases live and who is allowed to modify them
- Add examples for post-run analysis workflows and export formats
- Record any data integrity or audit requirements that matter for experiments
