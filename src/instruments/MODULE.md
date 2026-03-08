# Module: instruments

## Purpose
BaseInstrument abstract class and all instrument drivers. Each sub-driver is self-contained with its own driver, mock, models, and exceptions.

## Public API (`__init__.py`)
- `BaseInstrument` — ABC for all instruments
- `InstrumentError` — Base exception

Sub-modules (each has their own `__init__.py`):
- `instruments.pipette` — Pipette, MockPipette, models, exceptions
- `instruments.filmetrics` — Filmetrics, MockFilmetrics, models, exceptions
- `instruments.uvvis_ccs` — UVVisCCS, MockUVVisCCS, models, exceptions

## Contracts
- `InstrumentInterface` — base contract (all instruments)
- `PipetteInterface` — pipette-specific methods
- `FilmetricsInterface` — filmetrics-specific methods
- `UVVisCCSInterface` — UV-Vis-specific methods

All in `src/contracts.py`.

## Internal Structure
- `base_instrument.py` — `BaseInstrument` ABC, `InstrumentError`
- `pipette/` — See `pipette/MODULE.md`
- `filmetrics/` — See `filmetrics/MODULE.md`
- `uvvis_ccs/` — See `uvvis_ccs/MODULE.md`

## Dependencies
None (leaf module).

## Dependents
`board`, `protocol_engine`, `data` (types only)

## Rules for Agents
- Each sub-driver directory is a SAFE PARALLEL ZONE
- New instruments: create `src/instruments/<name>/` with driver, mock, models, exceptions, `__init__.py`
- Never modify `base_instrument.py` without checking all existing drivers
- Every driver must have a corresponding Mock for testing

## Test Command
```bash
pytest tests/instruments/ tests/test_uvvis_ccs.py -v
```
