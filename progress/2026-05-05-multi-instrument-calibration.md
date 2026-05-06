# Multi-instrument calibration checkpoint

- Date: 2026-05-05
- Branch: unknown
- Scope: Add a simple guided setup CLI for multi-instrument board calibration.

## Requested semantics

- Prerequisite: GRBL `$3` axis directions and `$23` homing corner must be configured so CubOS positive deck-frame motion is FLB -> positive X/Y/Z, and homing is BRT.
- Origin phase sets **only G54 WPos X/Y** at the front-left XY artifact/reference pose. It must not set Z at this phase.
- Working bounds phase re-homes after XY origin and uses homed WPos as machine-derived bounds for X/Y/Z maxima. Manual x_max refinement is intentionally out of scope.
- Z phase happens after instruments are attached: the lowest instrument defines WPos Z=0.
- Instrument calibration uses a known artifact/block point; each instrument is jogged to that point/height and its `offset_x`, `offset_y`, and `depth` are computed from current gantry WPos.

## Safety assumptions

- This touches CNC gantry motion, G54 WPos, possibly GRBL soft-limit settings, and mounted instruments.
- Offline tests must validate command sequencing and YAML math before hardware use.
- Required hardware validation remains user-operated with slow jog steps and E-stop access.

## Planned files

- New: `setup/calibrate_multi_instrument_board.py`
- New tests: likely `tests/setup/test_calibrate_multi_instrument_board.py`
- Docs/context updates: `AGENTS.md`, `README.md` if feature lands.

## Progress

- Workspace/repo docs read per AGENTS/CLAUDE.
- Existing calibration, gantry origin, board offset math, validation paths inspected.
- Added `setup/calibrate_multi_instrument_board.py` guided CLI.
- Added offline tests in `tests/setup/test_calibrate_multi_instrument_board.py` covering:
  - inverse offset/depth math from `Board.move()`
  - minimal operator-facing prompt path with only `--gantry` required
  - XY-only origin assignment before Z assignment
  - re-home-derived working volume/YAML updates
  - per-instrument offset/depth preservation and updates in YAML
- Updated `AGENTS.md` and `README.md` with multi-instrument calibration usage and safety notes.
- Simplified CLI after user feedback: only `--gantry` is required; reference instrument, lowest instrument, and artifact XYZ are prompted. Pre-fill flags remain available but hidden from normal `--help` for scripted runs/tests.
- Removed automatic move-to-center after hardware run hit a switch/status failure. The calibration now starts each guided jog from a known homed BRT pose and explicitly tells the operator that no automatic center move will be made.
- Added first-time calibration seed configs under `configs/gantry/seeds/` so the CLI can get instrument inventory before real offsets/depths are known.
- Updated Sterling gantry config and Sterling seed to remove ASMI and expose `potentiostat` + `pipette` (`vendor: opentrons`) with placeholder calibration values.
- Added larger interactive jog step hotkeys: `6` = 50 mm and `7` = 100 mm. This affects one-instrument and multi-instrument calibration because multi-instrument calibration reuses the shared jog helper.
- Simplified multi-instrument Step 2/3 flow after hardware feedback: the lowest instrument's first touch now both defines Z and records its X/Y/Z block coordinate. The script no longer immediately re-homes and asks for that same lowest instrument point again; it calibrates only remaining instruments, then re-homes once at the end to measure final working-volume maxima.

## Validation

- `python -m pytest tests/setup/test_calibrate_multi_instrument_board.py -q` → 2 passed before CLI simplification
- `python -m pytest tests/setup/test_calibrate_multi_instrument_board.py tests/setup/test_calibrate_deck_origin.py tests/setup/test_setup_imports.py -q` → 21 passed before CLI simplification
- `python -m pytest tests/setup/test_calibrate_multi_instrument_board.py tests/setup/test_calibrate_deck_origin.py tests/setup/test_setup_imports.py -q` → 22 passed after CLI simplification
- `python -m pytest tests/setup/test_calibrate_multi_instrument_board.py tests/setup/test_calibrate_deck_origin.py tests/setup/test_setup_imports.py -q` → 22 passed after removing automatic center moves
- `python setup/calibrate_multi_instrument_board.py --help` → shows only `--gantry`, `--dry-run`, `--write-gantry-yaml`, and `--output-gantry`
- `PYTHONPATH=src python - <<'PY' ... load_gantry_from_yaml(configs/gantry/seeds/*.yaml) ... PY` → all seed YAML files load and expose expected instrument names
- `PYTHONPATH=src python - <<'PY' ... load_gantry_from_yaml('configs/gantry/cub_xl_sterling.yaml') ... PY` → Sterling instruments are `pipette`, `potentiostat`
- `PYTHONPATH=src python - <<'PY' ... load_board_from_gantry_config(..., mock_mode=True) ... PY` → instantiates `Pipette` and `Potentiostat`
- `PYTHONPATH=src python -m pytest tests/setup/test_calibrate_deck_origin.py tests/setup/test_calibrate_multi_instrument_board.py tests/setup/test_keyboard_input.py -q` → 26 passed

## Hardware validation pending

- Run `--dry-run` on the intended gantry config.
- Verify GRBL `$3` and `$23` produce BRT homing and CubOS-positive jog directions.
- Run the guided calibration with slow jog steps, calibration artifact/block in place, and E-stop access.
