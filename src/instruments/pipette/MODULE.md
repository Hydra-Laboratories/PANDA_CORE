# Module: instruments/pipette

## Purpose
Driver for Opentrons OT-2 and Flex pipettes via Arduino serial (Pawduino firmware).

## Public API (`__init__.py`)
- `Pipette` — Real serial driver
- `MockPipette` — In-memory mock (tracks `command_history`)
- `PipetteConfig`, `PipetteFamily`, `PipetteStatus`, `AspirateResult`, `MixResult` — Models
- `PIPETTE_MODELS` — Registry dict of supported pipette models
- `PipetteError`, `PipetteConnectionError`, `PipetteCommandError`, `PipetteTimeoutError`, `PipetteConfigError` — Exceptions

## Contract
`PipetteInterface` in `src/contracts.py`.

## Internal Structure
- `driver.py` — `Pipette(BaseInstrument)` with serial commands
- `mock.py` — `MockPipette(BaseInstrument)` for testing
- `models.py` — Frozen dataclasses and `PIPETTE_MODELS` registry
- `exceptions.py` — Exception hierarchy

## Dependencies
`instruments.base_instrument` (parent ABC)

## Rules for Agents
- SAFE PARALLEL ZONE — can be modified independently
- Both `Pipette` and `MockPipette` must satisfy `PipetteInterface`
- New pipette models: add to `PIPETTE_MODELS` dict in `models.py`

## Test Command
```bash
pytest tests/instruments/pipette/ -v
```
