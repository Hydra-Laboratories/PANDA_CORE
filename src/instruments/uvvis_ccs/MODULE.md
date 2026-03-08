# Module: instruments/uvvis_ccs

## Purpose
Driver for Thorlabs CCS100/CCS175/CCS200 compact spectrometers (3648-pixel linear CCD). Communicates via TLCCS DLL through ctypes.

## Public API (`__init__.py`)
- `UVVisCCS` — Real DLL-based driver
- `MockUVVisCCS` — In-memory mock (tracks `command_history`)
- `UVVisSpectrum` — Frozen dataclass (wavelengths, intensities, integration_time_s, is_valid, num_pixels)
- `UVVisCCSError`, `UVVisCCSConnectionError`, `UVVisCCSMeasurementError`, `UVVisCCSTimeoutError` — Exceptions

## Contract
`UVVisCCSInterface` in `src/contracts.py`.

## Internal Structure
- `driver.py` — `UVVisCCS(BaseInstrument)` with ctypes DLL calls
- `mock.py` — `MockUVVisCCS(BaseInstrument)` for testing
- `models.py` — `UVVisSpectrum` frozen dataclass, `NUM_PIXELS = 3648`
- `exceptions.py` — Exception hierarchy

## Dependencies
`instruments.base_instrument` (parent ABC)

## Rules for Agents
- SAFE PARALLEL ZONE — can be modified independently
- Both `UVVisCCS` and `MockUVVisCCS` must satisfy `UVVisCCSInterface`
- `UVVisSpectrum` is used by `data/data_store.py` for type dispatch and BLOB serialization

## Test Command
```bash
pytest tests/test_uvvis_ccs.py -v
```
