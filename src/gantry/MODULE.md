# Module: gantry

## Purpose
CNC gantry hardware control via GRBL serial, config loading, and working volume bounds. Includes OfflineGantry for hardware-free testing and validation.

## Public API (`__init__.py`)
- `Gantry` — Hardware gantry (serial connection to Mill)
- `OfflineGantry` — Stub gantry for testing/validation
- `GantryConfig` — Frozen config dataclass (working volume, homing, serial port)
- `WorkingVolume` — Frozen dataclass with x/y/z min/max bounds
- `HomingStrategy` — Enum for homing strategies
- `GantryLoaderError` — Loader exception
- `load_gantry_from_yaml()` / `load_gantry_from_yaml_safe()` — YAML loading

## Contract
`GantryInterface` in `src/contracts.py` — satisfied by both `Gantry` and `OfflineGantry`.

## Internal Structure
- `gantry.py` — `Gantry` class wrapping the Mill driver
- `offline.py` — `OfflineGantry` no-op stub
- `gantry_config.py` — `GantryConfig`, `WorkingVolume`, `HomingStrategy`
- `loader.py` — YAML config loading functions
- `yaml_schema.py` — Pydantic schema for gantry YAML
- `errors.py` — `GantryLoaderError`
- `gantry_driver/` — Low-level GRBL `Mill` driver (serial)

## Dependencies
None (leaf module).

## Dependents
`board`, `validation`, `protocol_engine`

## Rules for Agents
- Both `Gantry` and `OfflineGantry` must satisfy `GantryInterface`
- Never add methods to `Gantry` without adding them to `OfflineGantry` too
- `gantry_driver/` is the serial layer — changes here can break hardware
- Run `pytest tests/test_contracts.py -k gantry` after interface changes

## Test Command
```bash
pytest tests/gantry/ -v
```
