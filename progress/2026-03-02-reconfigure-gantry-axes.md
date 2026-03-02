# Reconfigure Gantry Axes to Positive Coordinate Space

**Date:** 2026-03-02
**Status:** Planning

## Goal

Reconfigure the PANDA_CORE coordinate system so all user-facing axes (X, Y, Z) use **positive** working coordinates. Users should never see raw GRBL negative coordinates.

## Current State

- Home = (0, 0, 0), working area extends into negative space
- X: 0 to -300, Y: 0 to -200, Z: 0 to -80
- All configs, deck positions, instrument offsets, validation use negative coordinates
- GRBL firmware naturally works in negative space — this will NOT change

## Design Decisions

1. **Translation layer in `Gantry` class** — single boundary between user-facing (positive) and machine-facing (negative) code
2. **Negation on all three axes** — `user_coord = -machine_coord` and vice versa
3. **Mill driver stays untouched internally** — safe-Z logic, homing, GRBL commands all remain in machine space
4. **Z height model** — users specify labware height, system calculates `labware_z = total_z_height - labware_height`
5. **Instrument offsets are positive** — depth=+5 means "instrument tip is 5mm below gantry head" (5mm in positive Z direction)
6. **GRBL output always translated** — any user-visible coordinate reporting shows positive values

---

## Implementation Plan

### Phase 1: Coordinate Translation Module (Foundation)

**Goal:** Create a well-tested, single-responsibility translation layer.

**New file:** `src/gantry/coordinate_translator.py`

Functions:
- `to_user_coordinates(x, y, z) -> (x, y, z)` — negate all axes (machine → user)
- `to_machine_coordinates(x, y, z) -> (x, y, z)` — negate all axes (user → machine)
- `translate_status_string(status: str) -> str` — parse GRBL status strings (e.g., `<Idle|MPos:-150.000,-100.000,-40.000|...>`) and replace coordinate values with their positive equivalents
- Overloads/variants that accept `Coordinates` objects

**Tests first:** `tests/gantry/test_coordinate_translator.py`
- Test negation is correctly applied to all axes
- Test round-trip: `to_user(to_machine(x, y, z)) == (x, y, z)`
- Test zero coordinates stay zero
- Test status string translation with WPos format
- Test status string translation with MPos format
- Test status string with no coordinates passes through unchanged
- Test edge cases: very large values, very small values, floating point precision

### Phase 2: Gantry Config — Positive Working Volume

**Goal:** Update the config schema and files to use positive bounds.

**Changes:**
1. `src/gantry/gantry_config.py`
   - Update `WorkingVolume` docstring (remove "negative space" language)
   - Add `total_z_height: float` field to `GantryConfig`
   - `contains()` logic stays the same (min <= val <= max works with positive bounds)

2. `src/gantry/yaml_schema.py`
   - Add `total_z_height` field to `GantryYamlSchema` (under `working_volume` or top-level `cnc` section)
   - Validation: `total_z_height > 0`, `total_z_height == z_max`

3. `src/gantry/loader.py`
   - Pass `total_z_height` through to domain model

4. `configs/gantry/genmitsu_3018_PROver_v2.yaml` — update to:
   ```yaml
   working_volume:
     x_min: 0.0
     x_max: 300.0
     y_min: 0.0
     y_max: 200.0
     z_min: 0.0
     z_max: 80.0
   cnc:
     homing_strategy: xy_hard_limits
     total_z_height: 80.0
   ```

5. `configs/gantry/genmitsu_3018_PRO_Desktop.yaml` — same pattern

**Tests to update:**
- `tests/gantry/test_gantry_config.py` — all coordinate values flip to positive
- `tests/gantry/test_yaml_schema.py` — all coordinate values flip to positive
- `tests/gantry/test_loader.py` — all coordinate values flip to positive

### Phase 3: Gantry Wrapper — Translation Integration

**Goal:** Wire the translation layer into the Gantry class so all user-facing API returns positive coordinates.

**Changes to `src/gantry/gantry.py`:**

1. `move_to(x, y, z)`:
   - Accept positive user coordinates
   - Translate to machine coordinates (negate) before calling `self._mill.safe_move()`

2. `get_coordinates() -> dict`:
   - Get machine coordinates from `self._mill.current_coordinates()`
   - Translate to positive user coordinates before returning

3. `get_status() -> str`:
   - Get raw status from `self._mill.current_status()`
   - Translate any coordinate values in the string to positive

4. Add `total_z_height` property from config for labware height calculations

**New tests:** `tests/gantry/test_gantry_translation.py`
- Test `move_to(150, 100, 40)` sends `(-150, -100, -40)` to Mill
- Test `get_coordinates()` returns positive when Mill reports negative
- Test `get_status()` translates coordinate strings
- Test round-trip: move to position, read back, values match
- Test zero position (home) stays at zero
- Test boundary positions translate correctly
- Mock-based tests (heavy coverage as requested)

### Phase 4: Scan Command — Measurement Height Fix

**Goal:** Fix the measurement_height formula for positive-down Z space.

**Change in `src/protocol_engine/commands/scan.py`:**
```python
# Old (negative Z space — "above" = adding positive value toward 0):
target = (well.x, well.y, well.z + instr.measurement_height)

# New (positive Z space — "above" = subtracting from Z, moving toward 0):
target = (well.x, well.y, well.z - instr.measurement_height)
```

**Tests to update:**
- `tests/protocol_engine/test_scan_command.py` — update `test_applies_measurement_height_offset`:
  - Old: well z=-5.0, measurement_height=3.0, target z=-2.0
  - New: well z=75.0, measurement_height=3.0, target z=72.0

### Phase 5: Update All Configs and Tests to Positive Space

**Goal:** Flip every negative coordinate value in configs and tests to positive.

**Config files:**
- `configs/gantry/*.yaml` — positive working volume (done in Phase 2)
- `configs/decks/deck.sample.yaml` — positive deck positions
- `configs/boards/mofcat_board.yaml` — positive instrument offsets

**Test files to update (coordinate values only, no logic changes):**
1. `tests/gantry/test_gantry_config.py`
2. `tests/gantry/test_yaml_schema.py`
3. `tests/gantry/test_loader.py`
4. `tests/gantry/driver/test_gantry_driver.py`
5. `tests/validation/test_bounds_validation.py`
6. `tests/test_deck.py`
7. `tests/test_labware.py`
8. `tests/test_deck_loader.py`
9. `tests/protocol_engine/test_move_command.py`
10. `tests/protocol_engine/test_scan_command.py`
11. `tests/board/test_board.py`
12. `tests/board/test_board_loader.py`
13. `tests/protocol_engine/test_pipette_commands.py`
14. `tests/data/test_integration.py`

**Source files to update:**
- `src/gantry/gantry_driver/mock.py` — MockMill working_volume and safe_floor_height to positive
- `src/gantry/gantry_driver/driver.py` — only the `read_working_volume()` default fallback values (internal machine space stays negative)
- `src/validation/bounds.py` — no logic changes, just docstring updates
- `src/board/board.py` — no logic changes, offset math works the same in positive space

### Phase 6: Labware Height Helper

**Goal:** Allow users to specify labware height instead of calculating Z manually.

**Changes:**
1. Add optional `height` field to labware YAML schemas (`VialYamlEntry`, `WellPlateYamlEntry`)
2. In deck loader: when `height` is specified, compute `z = total_z_height - height`
3. This requires the deck loader to receive `total_z_height` — add it as a parameter to `load_deck_from_yaml()` or compute during protocol setup

**Tests:**
- Test vial with `height: 30` and `total_z_height: 80` → z = 50
- Test well plate with `height: 15` and `total_z_height: 80` → z = 65
- Test raw Z still works when height not specified (backward compatibility)

### Phase 7: Documentation and Cleanup

1. Update `AGENTS.md`:
   - New coordinate convention (positive space)
   - `total_z_height` concept
   - Instrument offset convention (positive values)
   - Labware height field

2. Update `README.md` if applicable

3. Update progress file with completed work

4. Delete any temporary test/planning files

---

## Key Risk: Z-Axis Semantics

In the new system, positive Z means "down" (away from home, toward the deck). This is opposite to standard CNC convention where positive Z = up. This is intentional for lab automation — users think about "how far to travel" and "labware height" — but worth documenting clearly.

## Testing Strategy

- **Translation layer gets the heaviest testing** (as requested) — every edge case, round-trip verification, status string parsing
- **Each phase runs tests before moving to the next** (TDD per CLAUDE.md)
- **Integration verification:** after all phases, run full test suite to ensure nothing breaks

## Files Changed Summary

| Category | Files |
|----------|-------|
| New files | `src/gantry/coordinate_translator.py`, `tests/gantry/test_coordinate_translator.py`, `tests/gantry/test_gantry_translation.py` |
| Config schema | `src/gantry/gantry_config.py`, `src/gantry/yaml_schema.py`, `src/gantry/loader.py` |
| Translation boundary | `src/gantry/gantry.py` |
| Command fix | `src/protocol_engine/commands/scan.py` |
| Config files | `configs/gantry/*.yaml`, `configs/decks/*.yaml`, `configs/boards/*.yaml` |
| Mock | `src/gantry/gantry_driver/mock.py` |
| Docstrings only | `src/validation/bounds.py`, `src/board/board.py` |
| Test updates (~14 files) | All test files with coordinate values |
| Documentation | `AGENTS.md`, `README.md`, `progress/` |
