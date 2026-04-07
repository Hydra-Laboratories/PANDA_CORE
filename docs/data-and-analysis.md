# Data and Analysis

PANDA Core includes a local SQLite-backed persistence layer for campaigns, experiments, measurements, and tracked labware contents.

## Main Components

- `data.data_store`: database creation and persistence API
- `data.data_reader`: read/query helpers
- `data.analysis.uvvis`: UV-Vis analysis helpers

## Stored Concepts

The data layer models:

- campaigns
- experiments
- UV-Vis measurements
- Filmetrics measurements
- camera measurements
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
