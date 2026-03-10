# 2026-03-09 — Protocol Engine: Dead Volume, Pause, Dry-Run, Auto-Pause, Error Recovery

## Work Done

### Phase 3: Dead Volume Support
- Added `dead_volume_ul` field to `Vial` and `WellPlate` models (default 0.0)
- Validated `dead_volume_ul >= 0` and `dead_volume_ul < capacity_ul` in both models
- Added `dead_volume_ul` to `VialYamlEntry` and `WellPlateYamlEntry` YAML schemas
- Added `_dead_volumes` dict to `VolumeTracker` alongside `_volumes` and `_capacities`
- `validate_aspirate()` now checks `current - volume_ul >= dead_volume` instead of `>= 0`
- Updated `UnderflowVolumeError` to include dead volume info in error messages
- Added `get_dead_volume()` query method to `VolumeTracker`
- 15 new tests in `test_dead_volume.py`

### Phase 4: Pause Command
- New `src/protocol_engine/commands/pause.py` with `@protocol_command("pause")`
- Supports three reasons: "user" (input wait), "refill" (volume refill prompt), "tip_swap" (rack swap wait)
- Refill reason prompts for volume, parses input, updates VolumeTracker
- Empty input on refill does full refill to capacity
- Added `refill()` method to `VolumeTracker` (adds volume capped at capacity)
- Added `pause_handler` and `last_completed_step` fields to `ProtocolContext`
- Registered pause in `commands/__init__.py`
- 9 new tests in `test_pause_command.py`

### Phase 5: Dry-Run Simulation
- New `src/protocol_engine/dry_run.py` with `dry_run()` function
- `DepletionEvent` dataclass captures step index, command, labware, event type, shortfall
- `DryRunResult` dataclass with success flag, depletions list, final volumes dict
- Deep-copies VolumeTracker to avoid modifying original context
- Simulates aspirate, transfer, mix, serial_transfer commands
- Catches UnderflowVolumeError/OverflowVolumeError, resets volumes to continue finding ALL depletions
- 11 new tests in `test_dry_run.py`

### Phase 6: Auto-Pause Injection
- `inject_pauses()` function in `dry_run.py`
- Sorts depletions by step_index descending, inserts pause steps before each depletion
- Re-indexes all steps after insertion
- Returns new Protocol instance
- 5 new tests in `test_auto_pause.py`

### Phase 7: Protocol Error Recovery
- Modified `Protocol.run()` with try/except around each step
- Tracks `context.last_completed_step` after each successful step
- On `ProtocolExecutionError`: calls `context.pause_handler(context, step, exception)` if callable
- If handler returns without raising, retries the step
- If no handler or handler raises, re-raises the error
- 7 new tests in `test_protocol_recovery.py`

## Tests
- 734 tests pass (687 original + 47 new)
- All existing tests continue to pass with no regressions
