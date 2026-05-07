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

- New: `setup/calibrate_gantry.py` unified calibration entrypoint
- New tests: calibration routing plus single-/multi-flow helper coverage
- Docs/context updates: `AGENTS.md`, `README.md` if feature lands.

## Progress

- Workspace/repo docs read per AGENTS/CLAUDE.
- Existing calibration, gantry origin, board offset math, validation paths inspected.
- Added guided multi-instrument flow; it now lives inside `setup/calibrate_gantry.py`.
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
- Updated stale Sterling ASMI protocols/tests after Sterling was changed to potentiostat + pipette: `sterling_park.yaml` and `sterling_vial_scan.yaml` now use `potentiostat`; tests assert potentiostat offline state.
- Cleaned up end-user multi-instrument calibration prompts: defer lowest-tool selection until after full board attach/verify; replace unexplained TCP wording with active tip/probe point plus tool center point; Step 1 tells user to place front-left origin block/artifact and jog over the X mark.
- Fixed limit-alarm Z recovery: Z-axis recovery now always pulls upward (+Z in CubOS deck frame), avoiding the stale-alarm case where pressing X/up after a lower-limit hit caused the old opposite-delta logic to pull deeper into the switch.
- Increased calibration limit pull-off distance from 2 mm to 5 mm.
- Added best-effort proactive limit detection after each jog by querying status for `Alarm` or active `Pn:X/Y/Z` limit pins.
- Added 15 mm automatic +Z retract after each instrument contact point is recorded in multi-instrument calibration.
- Changed instrument selection prompts to numbered menus; operators now enter `1`, `2`, etc. instead of typing instrument names.
- Added a brief calibration overview before preflight explaining that Step 1 establishes the shared system origin by placing the front-left origin block/artifact and jogging the first/left-most tool over the X mark; Z is set later with the full board attached.
- Removed the separate internal `setup/calibration/` modules. `setup/calibrate_gantry.py` is now the only calibration script/file and contains both flows, selecting single- vs multi-instrument calibration from the seed YAML.

## Validation

- `python -m pytest tests/setup/test_calibrate_multi_instrument_board.py -q` → 2 passed before CLI simplification
- `python -m pytest tests/setup/test_calibrate_multi_instrument_board.py tests/setup/test_calibrate_deck_origin.py tests/setup/test_setup_imports.py -q` → 21 passed before CLI simplification
- `python -m pytest tests/setup/test_calibrate_multi_instrument_board.py tests/setup/test_calibrate_deck_origin.py tests/setup/test_setup_imports.py -q` → 22 passed after CLI simplification
- `python -m pytest tests/setup/test_calibrate_multi_instrument_board.py tests/setup/test_calibrate_deck_origin.py tests/setup/test_setup_imports.py -q` → 22 passed after removing automatic center moves
- `python setup/calibrate_gantry.py --help` → shows the unified `--seed` and `--output-gantry` entrypoint
- `PYTHONPATH=src python - <<'PY' ... load_gantry_from_yaml(configs/gantry/seeds/*.yaml) ... PY` → all seed YAML files load and expose expected instrument names
- `PYTHONPATH=src python - <<'PY' ... load_gantry_from_yaml('configs/gantry/cub_xl_sterling.yaml') ... PY` → Sterling instruments are `pipette`, `potentiostat`
- `PYTHONPATH=src python - <<'PY' ... load_board_from_gantry_config(..., mock_mode=True) ... PY` → instantiates `Pipette` and `Potentiostat`
- `PYTHONPATH=src python -m pytest tests/setup/test_calibrate_deck_origin.py tests/setup/test_calibrate_multi_instrument_board.py tests/setup/test_keyboard_input.py -q` → 26 passed
- `PYTHONPATH=src python setup/validate_setup.py configs/gantry/cub_xl_sterling.yaml configs/deck/sterling_deck.yaml configs/protocol/sterling_vial_scan.yaml` → PASS
- `PYTHONPATH=src python setup/validate_setup.py configs/gantry/cub_xl_sterling.yaml configs/deck/sterling_deck.yaml configs/protocol/sterling_2_instrument_vial_scan.yaml` → PASS
- `PYTHONPATH=src python setup/validate_setup.py configs/gantry/cub_xl_sterling.yaml configs/deck/sterling_deck.yaml configs/protocol/sterling_park.yaml` → PASS
- `PYTHONPATH=src python -m pytest -q` → 1044 passed, 4 subtests passed
- `PYTHONPATH=src python -m pytest tests/setup/test_calibrate_multi_instrument_board.py tests/setup/test_calibrate_deck_origin.py tests/setup/test_keyboard_input.py -q` → 27 passed after prompt/recovery cleanup
- `PYTHONPATH=src python -m pytest -q` → 1045 passed, 4 subtests passed after prompt/recovery cleanup
- `PYTHONPATH=src python -m pytest -q` → 1045 passed, 4 subtests passed after 5 mm pull-off/status probe/15 mm retract changes
- `PYTHONPATH=src python -m pytest -q` → 1045 passed, 4 subtests passed after numbered instrument prompt change
- `python -m pytest tests/setup/test_calibrate_gantry.py tests/setup/test_calibrate_deck_origin.py tests/setup/test_calibrate_multi_instrument_board.py tests/setup/test_keyboard_input.py -q` → 37 passed after consolidating calibration flows into `setup/calibrate_gantry.py` only
- `python -m pytest tests/setup/test_setup_imports.py -q` → 2 passed after deleting `setup/calibration/`

## Hardware validation pending

- Run `--dry-run` on the intended gantry config.
- Verify GRBL `$3` and `$23` produce BRT homing and CubOS-positive jog directions.
- Run the guided calibration with slow jog steps, calibration artifact/block in place, and E-stop access.
