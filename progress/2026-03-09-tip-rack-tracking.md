# 2026-03-09 -- TipRack Labware Type + Tip Tracking

## Work Done

### 1. TipRack labware model (`src/deck/labware/tip_rack.py`)
- New `TipRack` class extending `Labware` (same base as WellPlate/Vial)
- Fields: name, model_name, rows, columns, wells (Dict[str, Coordinate3D]), length_mm, width_mm, height_mm
- No volume fields (tips are boolean present/absent)
- Validates: non-empty name, positive dimensions, A1 must exist, well count == rows*columns
- Uses `ConfigDict(extra="forbid", protected_namespaces=())`

### 2. YAML schema for TipRack (`src/deck/yaml_schema.py`)
- Added `TipRackYamlEntry` with `type: Literal["tip_rack"]`, rows, columns, calibration, offsets, dimensions
- Added to the `LabwareYamlEntry` discriminated union

### 3. Deck loader support (`src/deck/loader.py`)
- Added `_build_tip_rack()` reusing `_derive_wells_from_calibration()` (same well grid generation as WellPlate)
- Updated `load_deck_from_yaml()` to handle `TipRackYamlEntry`
- Updated type hints for `_resolve_plate_orientation` and `_derive_wells_from_calibration` to accept TipRackYamlEntry

### 4. Deck type hints (`src/deck/deck.py`)
- Updated Union types to include TipRack throughout

### 5. Tip tracking in VolumeTracker (`src/protocol_engine/volume_tracker.py`)
- Added `_tips` dict and `_tip_rack_wells` dict for column-major ordering
- `register_tip_rack()` -- registers all well slots as True (present)
- `pick_up_tip()` -- validates tip exists, sets to False
- `tips_remaining()` -- count of available tips
- `next_available_tip()` -- returns next well_id in column-major order (A1, B1, C1, ..., A2, B2, ...)

### 6. Tip error types (`src/protocol_engine/errors.py`)
- `TipError(ProtocolExecutionError)` -- base
- `TipNotAvailableError(TipError)` -- specific slot has no tip (fields: labware_key, well_id)
- `TipRackDepletedError(TipError)` -- no tips remaining (fields: labware_key)

### 7. Auto-select tip in pick_up_tip command (`src/protocol_engine/commands/pipette.py`)
- If position contains a dot (e.g. `tiprack_1.A1`), picks specific tip
- If position has no dot (e.g. `tiprack_1`), auto-selects next available tip
- Calls `volume_tracker.pick_up_tip()` before hardware action
- Raises `TipRackDepletedError` if auto-select finds no tips

### 8. Setup integration (`src/protocol_engine/setup.py`)
- `_register_deck_labware()` handles TipRack via `tracker.register_tip_rack()`

### 9. DataStore integration (`data/data_store.py`)
- `register_labware()` handles TipRack: creates one row per tip slot with labware_type='tip_rack', total_volume_ul=0, working_volume_ul=0

### 10. Exports updated
- `src/deck/labware/__init__.py` -- exports TipRack
- `src/deck/__init__.py` -- exports TipRack and TipRackYamlEntry

## Tests
- `tests/deck/test_tip_rack.py` -- 12 tests for TipRack model
- `tests/protocol_engine/test_tip_tracking.py` -- 15 tests for tip tracking
- `tests/test_deck_loader.py` -- 2 new tests for YAML loading
- 716 total tests pass

## Files Modified
- `src/deck/labware/tip_rack.py` (new)
- `src/deck/labware/__init__.py`
- `src/deck/__init__.py`
- `src/deck/deck.py`
- `src/deck/yaml_schema.py`
- `src/deck/loader.py`
- `src/protocol_engine/errors.py`
- `src/protocol_engine/volume_tracker.py`
- `src/protocol_engine/commands/pipette.py`
- `src/protocol_engine/setup.py`
- `data/data_store.py`
- `tests/deck/__init__.py` (new)
- `tests/deck/test_tip_rack.py` (new)
- `tests/protocol_engine/test_tip_tracking.py` (new)
- `tests/test_deck_loader.py`
