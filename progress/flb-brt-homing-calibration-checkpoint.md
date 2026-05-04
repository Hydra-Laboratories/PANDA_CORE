# FLB/BRT Homing Calibration Checkpoint

- **Branch:** `new-homing`
- **Task scope:** Replace `setup/calibrate_deck_origin.py` with explicit FLB/BRT homing-profile calibration, add gantry YAML schema support for calibration profiles and instrument reach limits, and enforce per-instrument X reach during offline bounds validation.
- **Issue/PR:** none supplied in this turn.

## Semantic Contracts

- CubOS runtime remains front-left-bottom deck frame: `+X` right, `+Y` back/away, `+Z` up.
- Runtime `home` remains normal BRT GRBL `$H`; FLB homing is calibration/admin only.
- The calibration script must not infer `$3` or `$23`; both `runtime_brt` and `origin_flb` must be explicitly configured under `cnc.calibration_homing`.
- When `cnc.calibration_homing` is present, `runtime_brt.dir_invert_mask` and `runtime_brt.homing_dir_mask` must match the normal `grbl_settings`.
- The script must restore the runtime BRT profile before disconnecting whenever it has connected to hardware, but it must not run BRT `$H` as part of calibration.
- Bounds validation must continue to enforce global `working_volume`; optional instrument `reach_limits.gantry_x_min/max` add stricter per-instrument gantry-X checks.

## Hardware Impact

- Potentially affected hardware: GRBL controller settings `$3`, `$20`, `$21`, `$22`, `$23`, `$130`, `$131`, `$132`; CNC gantry FLB homing, estimated-bound moves, and jogging; selected instrument TCP calibration.
- Offline validation only so far in this checkpoint.
- Required physical validation remains: no-instrument FLB origin and estimated-bound inspection first with `python setup/calibrate_deck_origin.py --gantry <gantry.yaml>`, repeatability over at least three cycles, one-instrument TCP calibration at low jog step/feed with E-stop ready, then `setup/validate_setup.py` and a minimal real move protocol.

## Files Likely To Change

- `src/gantry/yaml_schema.py`, `src/gantry/gantry_config.py`, `src/gantry/loader.py`, `src/gantry/origin.py`, `src/gantry/__init__.py`
- `src/instruments/yaml_schema.py`, `src/instruments/base_instrument.py`, `src/board/loader.py`
- `src/validation/bounds.py`
- `setup/calibrate_deck_origin.py`
- `configs/gantry/cub_xl_asmi.yaml`
- focused tests under `tests/gantry`, `tests/setup`, and `tests/validation`
- docs/README/AGENTS calibration references

## Validation Log

- `PYTHONPATH=src pytest -q tests/gantry/test_yaml_schema.py tests/validation/test_bounds_validation.py tests/setup/test_calibrate_deck_origin.py` -> 68 passed before machine-bounds-only mode; `tests/setup/test_calibrate_deck_origin.py` later -> 6 passed.
- `PYTHONPATH=src pytest -q tests/gantry tests/validation tests/setup/test_calibrate_deck_origin.py tests/setup/test_protocol_setup.py tests/setup/test_integration.py` -> 277 passed, 4 subtests passed.
- `PYTHONPATH=src pytest -q tests/protocol_engine/test_deck_origin_configs.py` -> 5 passed.
- `PYTHONPATH=src python setup/validate_setup.py configs/gantry/cub_xl_asmi.yaml configs/deck/asmi_deck.yaml configs/protocol/asmi_move_a1.yaml` -> PASS.
- `PYTHONPATH=src python setup/calibrate_deck_origin.py --gantry configs/gantry/cub_xl_asmi.yaml --dry-run` -> printed explicit FLB/BRT profile-switching flow.
- `PYTHONPATH=src pytest -q tests/gantry/test_origin.py tests/setup/test_calibrate_deck_origin.py` -> 32 passed after aligning the origin helper plan.
- `PYTHONPATH=src pytest -q` -> 1023 passed, 4 subtests passed (latest run after origin-helper alignment).
- Added Sterling explicit profiles from hardware note: runtime BRT `$3=1`, `$23=0`; FLB `$3=1`, `$23=7`.
- `PYTHONPATH=src python setup/calibrate_deck_origin.py --gantry configs/gantry/cub_xl_sterling.yaml --dry-run --skip-instrument-calibration` -> printed explicit Sterling FLB/BRT flow.
- `PYTHONPATH=src python setup/validate_setup.py configs/gantry/cub_xl_sterling.yaml configs/deck/sterling_deck.yaml configs/protocol/sterling_park.yaml` -> PASS.
- `PYTHONPATH=src python setup/validate_setup.py configs/gantry/cub_xl_sterling.yaml configs/deck/sterling_deck.yaml configs/protocol/sterling_vial_scan.yaml` -> PASS.
- `PYTHONPATH=src pytest -q tests/protocol_engine/test_deck_origin_configs.py tests/gantry/test_yaml_schema.py tests/setup/test_calibrate_deck_origin.py` -> 47 passed.
- `PYTHONPATH=src pytest -q` -> 1023 passed, 4 subtests passed after Sterling profile addition.
- Removed required `--reference-x-mm/--reference-y-mm` from the standard TCP calibration flow. The script now defaults to the measured deck center and asks the operator to jog the selected TCP to the physical center mark; explicit reference X/Y remain optional overrides.
- `PYTHONPATH=src pytest -q tests/setup/test_calibrate_deck_origin.py tests/protocol_engine/test_deck_origin_configs.py` -> 11 passed.
- `PYTHONPATH=src python setup/calibrate_deck_origin.py --gantry configs/gantry/cub_xl_sterling.yaml --dry-run` -> prints center-mark TCP calibration step without requiring reference coordinates.
- `PYTHONPATH=src pytest -q` -> 1023 passed, 4 subtests passed after center-reference calibration update.
- User hardware run showed the BRT-WPos-as-bounds assumption is invalid: Sterling could physically move farther left/down than the script's inferred `0..BRT WPos` clamps. The next attempted direction was FLB zero plus active positive-axis probing, but later hardware behavior invalidated the non-blocking jog probing path.
- Refactor direction: `setup/calibrate_deck_origin.py` should expose a stateful calibration session with calibration defaults as class/dataclass fields. CLI should only need `--gantry` and optional `--instrument`; no operator-facing tuning flags.
- Implemented stateful `DeckOriginCalibrationSession` with CLI limited to `--gantry` and optional `--instrument`.
- Superseded interim state: replaced BRT-derived bounds with active positive-axis probing. That path has since been removed after hardware overshoot.
- Current failure handling: if the session fails before estimated spans are committed, it attempts to restore the runtime BRT profile plus original `$20`, `$21`, and `$130-$132` before disconnecting.
- `PYTHONPATH=src pytest -q tests/setup/test_calibrate_deck_origin.py tests/gantry/test_yaml_schema.py tests/validation/test_bounds_validation.py tests/gantry/test_origin.py tests/protocol_engine/test_deck_origin_configs.py` -> 100 passed.
- `python setup/calibrate_deck_origin.py --help` -> only `--gantry` and `--instrument` are exposed.
- `PYTHONPATH=src python setup/validate_setup.py configs/gantry/cub_xl_sterling.yaml configs/deck/sterling_deck.yaml configs/protocol/sterling_park.yaml` -> PASS.
- `PYTHONPATH=src python setup/validate_setup.py configs/gantry/cub_xl_sterling.yaml configs/deck/sterling_deck.yaml configs/protocol/sterling_vial_scan.yaml` -> PASS.
- `PYTHONPATH=src pytest -q` -> 1023 passed, 4 subtests passed after probing refactor.
- Hardware attempt hit the +Z top limit faster than expected and the first recovery path failed when WPos readback returned no location immediately after pull-off. Fixed recovery to use slower probing/pull-off defaults, catch direct `LocationNotFound` from WPos parsing, retry raw status/WPos recovery after pull-off, and return recovered coordinates to the interactive jog loop instead of issuing an immediate second read.
- `PYTHONPATH=src pytest -q tests/setup/test_calibrate_deck_origin.py` -> 7 passed, including a regression where WPos readback fails once during limit recovery.
- `PYTHONPATH=src pytest -q` -> 1024 passed, 4 subtests passed after limit-recovery hardening.
- Hardware follow-up showed non-blocking probe jogs could overshoot the guardrail badly (`Z=211` after a nominal 0.25 mm step). Removed the automatic switch-probing/C-R-Q path. Bounds are now estimated from gantry YAML `working_volume.<axis>_max - 2 mm`; the script moves to that estimated BRT inspection pose with normal blocking moves, verifies WPos did not overshoot, programs `$130/$131/$132` from the estimate, and uses BRT homing only for verification.
- `python setup/calibrate_deck_origin.py --help` -> only `--gantry` and optional `--instrument`; help now says "estimate usable machine bounds".
- `PYTHONPATH=src pytest -q tests/setup/test_calibrate_deck_origin.py` -> 7 passed after estimate-only bounds change.
- `PYTHONPATH=src pytest -q` -> 1024 passed, 4 subtests passed after estimate-only bounds change.
- Removed automatic final BRT `$H`. The script and origin-plan helper now treat FLB G54 zero as the coordinate source of truth, program estimated spans, and only restore the runtime BRT `$3`/`$23` profile before disconnecting.
- `PYTHONPATH=src pytest -q tests/gantry/test_origin.py tests/setup/test_calibrate_deck_origin.py` -> 33 passed after removing final BRT homing.
- `python setup/calibrate_deck_origin.py --help` -> still only `--gantry` and optional `--instrument`.
- `git diff --check` -> passed.
- `PYTHONPATH=src pytest -q` -> 1024 passed, 4 subtests passed after removing final BRT homing.
- Simplified `setup/calibrate_deck_origin.py` to deck-origin only: hardcoded gantry path, no argparse, no instrument/TCP calibration, no BRT restore, FLB home + G54 zero + estimated-bound move + optional write to a new YAML file. Added `setup/instrument_calibration.py` placeholder with TODOs for the removed TCP offset/depth/reach workflow.
- `python -m py_compile setup/calibrate_deck_origin.py setup/instrument_calibration.py` -> passed. Tests were not updated for this quick hardware-iteration cleanup.
- Updated `configs/gantry/cub_xl_asmi.yaml` to use the same working bounds as `configs/gantry/cub_xl_sterling.yaml`: X[0,395], Y[0,295], Z[0,110], with `cnc.total_z_height: 139.0` so schema validation still passes.
- `PYTHONPATH=src python setup/validate_setup.py configs/gantry/cub_xl_asmi.yaml configs/deck/asmi_deck.yaml configs/protocol/asmi_move_a1.yaml` -> PASS.
- `PYTHONPATH=src python setup/validate_setup.py configs/gantry/cub_xl_asmi.yaml configs/deck/asmi_deck.yaml configs/protocol/asmi_indentation.yaml` -> PASS.

## Open Risks

- Real FLB switch topology is not verified by offline tests.
- Existing real gantry YAMLs other than `configs/gantry/cub_xl_asmi.yaml` and `configs/gantry/cub_xl_sterling.yaml` still need explicit machine-specific `calibration_homing` values before the new calibration script can run.
- Estimated BRT inspection still needs real validation. Watch whether the configured YAML maxima minus 2 mm are actually clear of physical switches; if not, hit E-stop/reset and lower the YAML maxima before retrying.
