# Module: instruments/filmetrics

## Purpose
Driver for the Filmetrics film thickness measurement system. Communicates with a C# console app (FilmetricsTool.exe) via stdin/stdout.

## Public API (`__init__.py`)
- `Filmetrics` — Real driver (subprocess-based)
- `MockFilmetrics` — In-memory mock (tracks `command_history`)
- `MeasurementResult` — Frozen dataclass (thickness_nm, goodness_of_fit, is_valid)
- `FilmetricsError`, `FilmetricsConnectionError`, `FilmetricsCommandError`, `FilmetricsParseError` — Exceptions

## Contract
`FilmetricsInterface` in `src/contracts.py`.

## Internal Structure
- `driver.py` — `Filmetrics(BaseInstrument)` with subprocess commands
- `mock.py` — `MockFilmetrics(BaseInstrument)` for testing
- `models.py` — `MeasurementResult` frozen dataclass
- `exceptions.py` — Exception hierarchy
- `reference/` — C# source for protocol reference

## Dependencies
`instruments.base_instrument` (parent ABC)

## Rules for Agents
- SAFE PARALLEL ZONE — can be modified independently
- Both `Filmetrics` and `MockFilmetrics` must satisfy `FilmetricsInterface`
- `MeasurementResult` is used by `data/data_store.py` for type dispatch

## Test Command
```bash
pytest tests/instruments/filmetrics/ -v
```
