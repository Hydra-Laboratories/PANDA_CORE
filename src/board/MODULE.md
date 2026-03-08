# Module: board

## Purpose
Board = gantry + instruments. Wraps gantry movement with instrument offset math so the gantry head positions the instrument tip at the correct location.

## Public API (`__init__.py`)
- `Board` — Main class (move, object_position)
- `BoardLoaderError` — Loader exception
- `BoardYamlSchema`, `InstrumentYamlEntry` — Pydantic schemas
- `INSTRUMENT_REGISTRY` — Maps instrument type names to classes
- `load_board_from_yaml()` / `load_board_from_yaml_safe()` — YAML loading

## Contract
None (Board is consumed by protocol_engine, not abstracted behind an interface).

## Internal Structure
- `board.py` — `Board` class with `move()` and `object_position()`
- `loader.py` — Board YAML loading with instrument instantiation
- `yaml_schema.py` — Pydantic schema for board YAML
- `errors.py` — `BoardLoaderError`

## Dependencies
`gantry` (Gantry instance), `instruments` (BaseInstrument instances)

## Dependents
`protocol_engine`, `validation`

## Rules for Agents
- COORDINATION REQUIRED for `board.py` — offset math affects all instrument positioning
- `INSTRUMENT_REGISTRY` in `loader.py` must be updated when adding new instruments
- `Board.move()` formula: `gantry_pos = deck_pos - instrument_offset`

## Test Command
```bash
pytest tests/board/ -v
```
