# Module: deck

## Purpose
Deck container for labware, labware models (WellPlate, Vial, Coordinate3D), and YAML loading with two-point calibration for well plates.

## Public API (`__init__.py`)
- `Deck` — Runtime container with dict-like access and `resolve()` for target strings
- `Coordinate3D` — (x, y, z) model
- `Labware` — Base labware model
- `WellPlate` — Multi-well plate model (Pydantic, strict)
- `Vial` — Single vial model (Pydantic, strict)
- `generate_wells_from_offsets()` — Well position derivation
- `DeckLoaderError` — Loader exception
- `DeckYamlSchema`, `WellPlateYamlEntry`, `VialYamlEntry` — Pydantic schemas
- `load_deck_from_yaml()` / `load_deck_from_yaml_safe()` — YAML loading

## Contract
`DeckInterface` in `src/contracts.py` — satisfied by `Deck`.

## Internal Structure
- `deck.py` — `Deck` container class
- `labware/labware.py` — `Coordinate3D`, `Labware` base
- `labware/well_plate.py` — `WellPlate` Pydantic model
- `labware/vial.py` — `Vial` Pydantic model
- `loader.py` — YAML loading + well derivation from calibration points
- `yaml_schema.py` — Pydantic schemas for deck YAML
- `errors.py` — `DeckLoaderError`

## Dependencies
None (leaf module).

## Dependents
`board`, `validation`, `protocol_engine`, `data`

## Rules for Agents
- All labware models use `extra='forbid'` — adding new fields requires schema updates
- Two-point calibration must be axis-aligned (A1 and A2 share x or y)
- Changes to WellPlate/Vial affect validation and data modules

## Test Command
```bash
pytest tests/test_deck.py tests/test_deck_loader.py tests/test_labware.py -v
```
