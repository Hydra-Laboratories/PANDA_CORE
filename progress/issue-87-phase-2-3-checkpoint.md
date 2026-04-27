# Issue 87 Phase 2/3 Checkpoint

Status: active checkpoint for the deck-origin motion refactor. Offline implementation is complete locally; physical hardware validation is still pending.

This file is intentionally temporary. Keep it current while issue #87 is being implemented or handed off, then delete it before final merge after durable context has been moved to the issue, PR, docs, or tests.

## Current Context

- Branch: `codex/phase-2-refactor-motion`
- GitHub issue: `Ursa-Laboratories/CubOS#87`
- Working split: former Phase 2 and Phase 3 are combined into one working cutover PR so only runnable behavior is merged.
- Candidate deck-origin configs live in `configs_new/`.
- Current production runtime still has legacy positive-down/top-reference behavior in several places; the combined cutover must change code, validation, tests, and docs together.
- The local implementation has cut over the high-level gantry boundary, board movement, scan/measure/pipette movement helpers, ASMI indentation direction, setup semantic validation, and deck `height` handling to the deck-origin +Z-up contract.

## Non-Negotiable Semantics

- Deck-origin frame:
  - Origin is front-left-bottom of the reachable work volume.
  - `+X` is operator right.
  - `+Y` is away/back from the operator.
  - `+Z` is up, away from the deck.
  - `-Z` is down, toward the deck.
- Protocol height fields are absolute deck-frame Z planes:
  - `measurement_height`
  - `entry_travel_height`
  - `interwell_travel_height`
  - any retained/default `safe_approach_height`
- Runtime must not compute action or travel Z as `labware_z + height`.
- Runtime must not compute action or travel Z as `labware_z - height`.
- Labware Z remains a calibration/validation reference for physical geometry.
- For ASMI indentation in deck-origin coordinates, downward motion means decreasing Z. A valid indentation lower limit is below the action plane, for example `indentation_limit < measurement_height`.
- Structure clearance for homing/first entry/parking is a machine-level clearance plane, not an instrument measurement height.

## Calibration Design Correction

The first deck-origin calibration workflow must be interactive. Do not assume
the configured/OOB working volume is the real physical working volume, and do
not set WPos at the homed corner as a substitute for visiting the physical
origin.

Correct Phase 2/3 calibration target:

1. Normalize the machine first:
   - `$H` homes to back-right-top.
   - `+X` jogs operator-right.
   - `+Y` jogs back/away.
   - `+Z` jogs up.
2. Attach one reference instrument/TCP for origin calibration.
   - If calibrating to the bottom/reference plane with multiple tools mounted,
     use the lowest safe instrument or attach instruments one at a time.
   - For Phase 2/3, keep this as a one-instrument workflow.
3. Home the gantry.
4. Prompt the operator through interactive jogging to the front-left XY
   origin/lower reach point for the reference TCP.
   - This point establishes X/Y and the lowest safe reachable Z for this one
     active TCP.
   - Do not assume this point is deck Z=0 unless the TCP is actually touching
     true deck bottom.
5. On confirmation, assign only X/Y:

   ```gcode
   G10 L20 P1 X0 Y0
   ```

6. Ask whether the TCP is touching true deck bottom at that pose.
   - If yes, bottom mode uses `z_min=0.0`.
   - If no, ruler-gap mode asks the operator to measure the vertical gap from
     deck to TCP and uses that gap as the one-instrument lower Z.
7. Assign only Z:

   ```gcode
   G10 L20 P1 Z<z_min_mm>
   ```

   In bottom mode this is `G10 L20 P1 Z0`; in ruler-gap mode it is
   `G10 L20 P1 Z<gap_mm>`.
8. Re-home after reference assignment and read the resulting WPos at the homed
   back-right-top corner. That measured WPos is the real working volume
   `(x_max, y_max, z_max)` for the setup.
9. Use the measured values to update or print the gantry YAML working-volume
   bounds. Do not treat nominal `400 x 300 x 100` values as physical truth.
   - For one-instrument bottom contact, use `z_min: 0.0`.
   - For one-instrument ruler-gap mode, use `z_min: <gap_mm>` and measured
     homed `z_max`. Example: if the TCP stops 5 mm above deck and has 100 mm
     upward travel, expect about `z_min: 5.0`, `z_max: 105.0`.

Multi-instrument calibration is intentionally deferred to a later Phase 3.5.
The expected direction is:

- Keep one shared WPos/deck frame. Do not reset WPos per instrument.
- Repeat reference/artifact calibration one instrument at a time, likely
  lowest-hanging to highest-hanging when bottom/contact calibration is involved.
- For each additional instrument, compute `offset_x`, `offset_y`, and `depth`
  relative to the established deck frame and update/print board YAML values.
- Use safe central or tool-specific reference targets/fiducials where direct
  bottom-plane contact would risk collisions.
- Add future checks for inactive-tool collisions and, if deck/labware placement
  is not mechanically constrained, extra targets/fiducials for rotation or tilt.
- Do not rely on a one-instrument global `working_volume.z_min` for
  mixed-depth tools. Multi-instrument configs need per-instrument lower-reach
  limits, e.g. `instrument_reach.<tool>.z_min_reachable`, plus motion planning
  that prevents inactive lower-hanging tools from colliding while another TCP
  is active.

## Candidate Config State

- `configs_new/README.md` documents the candidate deck-origin coordinate frame, ASMI estimates, PANDA estimates, and validation status.
- `configs_new/gantry/cub_xl_asmi_deck_origin.yaml` and `configs_new/gantry/cub_xl_panda_deck_origin.yaml` model an approximate `400 x 300 x 100 mm` Cub XL reachable work volume.
- `configs_new/gantry/cub_xl_asmi_deck_origin_2026-04-24.yaml` is a dated
  ASMI measured gantry config from the deck-origin calibration flow:
  - working volume: `X[0.0, 399.0]`, `Y[0.0, 280.0]`, `Z[0.0, 87.0]`
  - `cnc.total_z_height: 87.0`
  - Z reference mode: bottom contact with WPos `(0.0, 0.0, 0.0)`
  - unchanged settings copied from `cub_xl_asmi_deck_origin.yaml` remain
    provisional until controller settings and physical validation are checked.
- `configs_new/deck/asmi_deck_origin.yaml` places the ASMI 96-well plate from the old ASMI calibration estimate:
  - Current A1: `(358.0, 52.0, 30.0)`
  - Current A2: `(358.0, 61.0, 30.0)`
  - A2 is one adjacent column step along +Y from A1; B1 advances to lower X.
- `configs_new/board/asmi_board_deck_origin.yaml` uses absolute ASMI action/approach planes:
  - `measurement_height: 26.0`
  - `safe_approach_height: 35.0`
- `configs_new/protocol/asmi_move_a1_deck_origin.yaml` is a minimal hardware
  bring-up protocol:
  - `home`
  - deck-target `move` for `asmi` to `plate.A1`
  - The move uses `Board.move_to_labware()`, so it stops at the ASMI
    board-configured `safe_approach_height`; it does not descend to
    `measurement_height` or perform indentation.
- `configs_new/protocol/asmi_indentation_deck_origin.yaml` uses absolute scan/action planes:
  - `entry_travel_height: 85.0`
  - `interwell_travel_height: 35.0`
  - current local workspace `measurement_height: 32.0`
  - current local workspace `indentation_limit: 30.0`
  - those ASMI protocol height edits are currently unstaged user/hardware-tuning
    changes; do not revert them.
- `configs_new/deck/panda_deck_origin.yaml` is a visual estimate from the PANDA images:
  - well plate and tip racks use A1 to A2 along Y, with X unchanged between A1 and A2.
  - vial holder includes placeholder vials.
- `configs_new/board/panda_board_deck_origin.yaml` includes placeholders for camera and vial capper/decapper if real drivers are not present.
- `configs_new/deck/filmetrics_deck_origin.yaml` translates the legacy Filmetrics
  deck calibration from `configs/deck/filmetrics_deck.yaml` using the old
  `280 x 175 x 90 mm` frame:
  - A1: `(270.0, 140.0, 70.0)`
  - A2: `(270.0, 131.0, 70.0)`
- `configs_new/board/filmetrics_board_deck_origin.yaml` uses placeholder/default
  TCP values and translates the old 10 mm optical standoff to
  `measurement_height: 80.0` and `safe_approach_height: 80.0`.

## Known Code Surfaces To Cut Over

- `src/gantry/coordinate_translator.py`: cut over to identity Z normalization; no hidden sign flip.
- `src/gantry/gantry.py`: sends/reads deck-frame Z directly and jogs Z without negating.
- `src/board/board.py`: gantry TCP transform now uses `gantry_z = target_z + instrument.depth`; `move_to_labware()` uses absolute `safe_approach_height`.
- `src/protocol_engine/commands/_movement.py`: engaging actions use absolute `measurement_height` directly.
- `src/protocol_engine/commands/scan.py`: scan action/travel/final-retract Z values are absolute deck-frame planes.
- `src/instruments/asmi/driver.py`: downward indentation decreases Z and validates `indentation_limit < measurement_height`.
- `src/validation/protocol_semantics.py`: validates deck-origin travel/action ordering, ASMI indentation direction, runtime waypoints, and V1 `structure_clearance_z`.
- `src/validation/bounds.py`: gantry position validation now matches the +Z-up Board transform.
- `src/deck/loader.py`: `height` is a direct deck-frame Z value, not `total_z_height - height`.
- `src/instruments/base_instrument.py` and board schema docs: updated to absolute `measurement_height` / `safe_approach_height` semantics.
- `src/gantry/origin.py` / `setup/calibrate_deck_origin.py`: revised to the
  one-instrument interactive XY/lower-reach calibration workflow. The script
  homes, clears transient `G92`, prompts the operator to jog one reference TCP
  to the front-left XY origin and lowest safe reachable Z, sets only
  `G10 L20 P1 X0 Y0`, then assigns Z at that same pose. Bottom mode sets
  `G10 L20 P1 Z0`; ruler-gap mode prompts for the ruler-measured deck-to-TCP
  gap and sets `G10 L20 P1 Z<gap_mm>`. It re-homes and reports measured
  physical maxima plus a one-instrument `z_min` recommendation.
- `src/protocol_engine/commands/home.py`: deck-origin contexts now preserve the
  calibrated persistent WPos frame. They do not zero coordinates and do not
  assign homed WPos from configured maxima.
- `src/gantry/gantry_driver/driver.py`: standard `$H` homing now tolerates
  transient empty/invalid status reads and retries until the homing timeout
  instead of failing on the first missed `?` response. This was added after a
  physical run hit `Failed to get status from the mill` immediately after
  starting calibration homing.
- `setup/calibrate_deck_origin.py`: interactive jogging now detects limit
  alarms during jog/position-read, sends jog cancel, unlocks with `$X`, and
  pulls off in the opposite direction by `--limit-pull-off-mm` (default 2 mm).
  Recovery readback is best-effort so a transient post-unlock WPos parse
  failure does not abort the calibration loop.
- `src/gantry/gantry_driver/driver.py`: low-level `$J` jog responses now treat
  `alarm` and `[MSG:Check Limits]` as failed motion, not only `error`.

## Validation Already Run For Config Candidates

Stale relative-height phrasing/value scan:

```bash
rg -n "labware_z \+|relative action|relative clearance|measurement_height: -|indentation_limit: -|well_top_z .*\+|height above the well top" configs_new
```

Result: no matches.

Schema/load and deck-bounds smoke check:

```bash
PYTHONPATH=src python - <<'PY'
from pathlib import Path
import yaml
from gantry.loader import load_gantry_from_yaml
from deck.loader import load_deck_from_yaml
from board.yaml_schema import BoardYamlSchema
from protocol_engine.loader import load_protocol_from_yaml
from validation.bounds import validate_deck_positions

base = Path('configs_new')
for name in ['asmi', 'panda']:
    gantry = load_gantry_from_yaml(base / f'gantry/cub_xl_{name}_deck_origin.yaml')
    deck = load_deck_from_yaml(base / f'deck/{name}_deck_origin.yaml', total_z_height=gantry.total_z_height)
    with (base / f'board/{name}_board_deck_origin.yaml').open() as handle:
        board_schema = BoardYamlSchema.model_validate(yaml.safe_load(handle))
    violations = validate_deck_positions(gantry, deck)
    print(f'{name}: gantry/deck/board schema load OK; deck bounds violations={len(violations)}; instruments={list(board_schema.instruments)}')

protocol = load_protocol_from_yaml(base / 'protocol/asmi_indentation_deck_origin.yaml')
scan_step = next(step for step in protocol.steps if step.command_name == 'scan')
print('asmi protocol load OK')
print('asmi scan heights:', {k: scan_step.args[k] for k in ['entry_travel_height', 'interwell_travel_height', 'measurement_height', 'indentation_limit']})
PY
```

Result:

```text
asmi: gantry/deck/board schema load OK; deck bounds violations=0; instruments=['asmi']
panda: gantry/deck/board schema load OK; deck bounds violations=0; instruments=['potentiostat', 'camera', 'vial_capper_decapper']
asmi protocol load OK
asmi scan heights: {'entry_travel_height': 85.0, 'interwell_travel_height': 35.0, 'measurement_height': 26.0, 'indentation_limit': 24.0}
```

Pre-cutover historical note: this ASMI setup validation used to fail under the legacy positive-down implementation:

```bash
PYTHONPATH=src python setup/validate_setup.py configs_new/gantry/cub_xl_asmi_deck_origin.yaml configs_new/deck/asmi_deck_origin.yaml configs_new/board/asmi_board_deck_origin.yaml configs_new/protocol/asmi_indentation_deck_origin.yaml
```

Those old expected failures were:

- The validator treated higher absolute Z as "below" action Z due legacy positive-down assumptions.
- The ASMI validator expected `indentation_limit > measurement_height`; deck-origin requires the downward limit to be lower, so `indentation_limit < measurement_height`.

Post-cutover focused validation:

```bash
PYTHONPATH=src pytest tests/protocol_engine/ tests/board/ tests/gantry/ tests/validation/ tests/instruments/test_asmi.py -q
```

Result: `456 passed`.

Candidate config and structure-clearance tests:

```bash
PYTHONPATH=src pytest tests/protocol_engine/test_deck_origin_candidate_configs.py tests/validation/test_structure_clearance.py -q
```

Result after Filmetrics additions: `5 passed`.

Filmetrics candidate setup validation:

```bash
PYTHONPATH=src python setup/validate_setup.py configs_new/gantry/cub_filmetrics_deck_origin.yaml configs_new/deck/filmetrics_deck_origin.yaml configs_new/board/filmetrics_board_deck_origin.yaml configs_new/protocol/filmetrics_scan_deck_origin.yaml
```

Result: `PASS — all positions within gantry bounds`.

Deck-origin calibration focused tests:

```bash
PYTHONPATH=src pytest tests/setup/test_calibrate_deck_origin.py tests/protocol_engine/test_home_command.py tests/gantry/test_gantry.py -q
```

Result after interactive origin calibration revision: `43 passed`.

Homing retry and calibration-script focused tests:

```bash
PYTHONPATH=src pytest tests/setup/test_calibrate_deck_origin.py tests/gantry/driver/test_gantry_driver.py tests/gantry/test_gantry.py -q
```

Result after transient homing-status retry fix: `59 passed`.

Limit-alarm recovery and jog-driver focused tests:

```bash
PYTHONPATH=src pytest tests/setup/test_calibrate_deck_origin.py tests/gantry/driver/test_gantry_driver.py tests/gantry/test_gantry_translation.py -q
```

Result after hard-limit recovery addition: `34 passed`.

Check-limits/readback recovery focused tests:

```bash
PYTHONPATH=src pytest tests/setup/test_calibrate_deck_origin.py tests/gantry/driver/test_gantry_driver.py -q
```

Result after the earlier known-height reference surface support: `28 passed`.

Deck-origin calibration dry run:

```bash
PYTHONPATH=src python setup/calibrate_deck_origin.py --gantry configs_new/gantry/cub_xl_asmi_deck_origin.yaml --dry-run
```

Result: printed the expected physical calibration flow:
`$H`, `G92.1`, interactive jog to front-left XY origin/lower reach point,
`G10 L20 P1 X0 Y0`, confirm bottom contact or enter ruler-measured TCP gap,
`G10 L20 P1 Z<z_min_mm>`, `$H`, `?`.

Deck-origin calibration dry run with a 5 mm ruler-measured TCP gap:

```bash
PYTHONPATH=src python setup/calibrate_deck_origin.py --gantry configs_new/gantry/cub_xl_asmi_deck_origin.yaml --dry-run --z-reference-mode ruler-gap --tip-gap-mm 5 --instrument filmetrics
```

Result: printed `G10 L20 P1 X0 Y0` for the XY assignment and
`G10 L20 P1 Z5` for the lower-reach Z assignment.

Focused calibration/home tests after ruler-gap flow:

```bash
PYTHONPATH=src pytest tests/setup/test_calibrate_deck_origin.py tests/protocol_engine/test_home_command.py -q
```

Result: `16 passed`.

Focused calibration/config/home tests after making ASMI candidate scan waypoint
assertions follow the loaded protocol heights:

```bash
PYTHONPATH=src pytest tests/protocol_engine/test_deck_origin_candidate_configs.py tests/setup/test_calibrate_deck_origin.py tests/protocol_engine/test_home_command.py -q
```

Result: `19 passed`.

Focused calibration/gantry-wrapper tests:

```bash
PYTHONPATH=src pytest tests/setup/test_calibrate_deck_origin.py tests/gantry/test_gantry.py -q
```

Result after XY-then-Z plus guided reach-prompt revision:
`50 passed` for `tests/setup/test_calibrate_deck_origin.py tests/gantry/test_gantry.py`.

Focused calibration/home/driver tests:

```bash
PYTHONPATH=src pytest tests/setup/test_calibrate_deck_origin.py tests/protocol_engine/test_home_command.py tests/gantry/driver/test_gantry_driver.py tests/gantry/test_gantry.py -q
```

Result after guided bottom-vs-artifact Z grounding:
`74 passed`.

Protocol engine plus calibration-script tests:

```bash
PYTHONPATH=src pytest tests/protocol_engine/ tests/setup/test_calibrate_deck_origin.py -q
```

Result after interactive origin calibration revision: `189 passed`.

Candidate config and structure-clearance tests:

```bash
PYTHONPATH=src pytest tests/protocol_engine/test_deck_origin_candidate_configs.py tests/validation/test_structure_clearance.py -q
```

Result after interactive origin calibration revision: `5 passed`.

Full offline test suite:

```bash
PYTHONPATH=src pytest -q
```

Result after one-instrument ruler-gap calibration revision:
`967 passed`.

ASMI candidate setup validation:

```bash
PYTHONPATH=src python setup/validate_setup.py configs_new/gantry/cub_xl_asmi_deck_origin.yaml configs_new/deck/asmi_deck_origin.yaml configs_new/board/asmi_board_deck_origin.yaml configs_new/protocol/asmi_indentation_deck_origin.yaml
```

Result: `PASS — all positions within gantry bounds`.

Dated ASMI measured gantry setup validation with current local ASMI protocol
heights (`measurement_height: 32.0`, `indentation_limit: 30.0`):

```bash
PYTHONPATH=src python setup/validate_setup.py configs_new/gantry/cub_xl_asmi_deck_origin_2026-04-24.yaml configs_new/deck/asmi_deck_origin.yaml configs_new/board/asmi_board_deck_origin.yaml configs_new/protocol/asmi_indentation_deck_origin.yaml
```

Result: `PASS — all positions within gantry bounds`.

Dated ASMI measured gantry setup validation:

```bash
PYTHONPATH=src python -m setup.validate_setup configs_new/gantry/cub_xl_asmi_deck_origin_2026-04-24.yaml configs_new/deck/asmi_deck_origin.yaml configs_new/board/asmi_board_deck_origin.yaml configs_new/protocol/asmi_indentation_deck_origin.yaml
```

Result: `PASS — all positions within gantry bounds`.

ASMI A1 move bring-up validation:

```bash
PYTHONPATH=src python setup/validate_setup.py configs_new/gantry/cub_xl_asmi_deck_origin_2026-04-24.yaml configs_new/deck/asmi_deck_origin.yaml configs_new/board/asmi_board_deck_origin.yaml configs_new/protocol/asmi_move_a1_deck_origin.yaml
```

Result: `PASS — all positions within gantry bounds`.

Hardware status update from issue #93:

- ASMI move/scan/single-well indentation hardware validation has been partially
  completed by the user.
- Issue #93 now has completed Phase 2/3 implementation/offline checklist items
  checked through the ASMI-tested state.
- Remaining open hardware/design work:
  - Filmetrics hardware validation.
  - Rail guards / rail-risk behavior test strategy and implementation.
  - Multi-instrument homing/calibration, which is the highest-priority open
    design item.

## Required Implementation Shape

- Add or update movement-plan tests first so the motion sequence is explicit before touching physical motion code.
- Cut over runtime, validation, configs, and tests in the same PR.
- Preserve a compatibility story for old configs, or make the config migration explicit and loud.
- Keep structure-clearance behavior separate from measurement/action heights.
- Do not run physical hardware from cloud or CI.

## Hardware Impact

Potentially affected hardware:

- Genmitsu PROVerXL 4030 V2 / Cub XL gantry.
- GRBL controller homing, work coordinates, and commanded Z motion.
- ASMI force sensor and indentation tooling.
- Multi-instrument boards where tall tools can collide with Y rails or labware during homing/entry travel.
- PANDA board placeholders if later connected to real potentiostat, camera, pipette/tip racks, vial holder, or capper/decapper hardware.

Required hardware validation before trusting real runs:

- With tools removed or raised, verify homing corner and jog directions in the deck-origin frame.
- Run the revised interactive deck-origin calibration flow after `$3`/`$23`
  are normalized: home, jog one reference TCP to the front-left XY origin/lower
  reach point and set `G10 L20 P1 X0 Y0`, then either confirm bottom contact
  and set `G10 L20 P1 Z0` or measure the deck-to-TCP ruler gap and set
  `G10 L20 P1 Z<gap_mm>`. Re-home and record measured `(x_max, y_max, z_max)`.
- If the TCP cannot touch true deck/bottom Z=0, use ruler-gap mode and put the
  measured gap into the one-instrument `working_volume.z_min` before commanding
  low-Z motions.
- Verify commanded `+Z` moves up and `-Z` moves down at the user/API level after the cutover.
- Dry-run ASMI protocol above the deck with no sample contact and confirm entry travel, interwell travel, measurement, and indentation Z planes.
- Confirm high-clearance homing/first-entry/park moves clear Y rails and tall mounted tools on the multi-instrument board.
- Confirm an ASMI indentation run on a sacrificial plate/sample with conservative limits before using real samples.

Legacy calibration/setup scripts to remove or replace before final cleanup:

- `setup/home_gantry_config.py`: still exposes the old `G92 X0 Y0 Z0` homed-corner
  flow and should not be used for deck-origin calibration.
- `setup/hello_world.py`: jog prompts/control text predate the +Z-up deck-origin
  bring-up path.
- `calibration/home_gantry.py`: legacy homing wrapper; it does not assign
  top-back-right home to deck-origin maxima.

Current testing status: offline/config validation plus user-reported ASMI
move/scan/single-well indentation hardware validation. Filmetrics hardware,
rail/upright/home-edge guard behavior, failure-mode checks, and
multi-instrument homing/calibration remain pending.

## Next Steps

- Review the local combined Phase 2/3 cutover against issue #87.
- Decide whether to keep `configs_new/` as fixtures only or promote selected files after hardware validation.
- Keep issue/PR hardware impact current with exact offline validation and the
  remaining Filmetrics, rail-guard, and multi-instrument homing work.
- Delete this checkpoint once the task is complete and durable context has moved into the issue, PR, docs, and tests.
- Before merge: run the staged hardware checklist from issue #87 and either keep this checkpoint active for handoff or move the remaining durable hardware-validation notes into the PR/issue and delete this temporary file.
