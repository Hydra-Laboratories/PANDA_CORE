# CubOS Agent Guide

CubOS controls real lab hardware: a GRBL CNC gantry plus mounted instruments. Prefer repo source over model memory, but keep retrieval focused.

## Fast Start

1. Read this file and `CLAUDE.md`.
2. Use `docs/agent-index.md` as the routing map for the subsystem you are touching.
3. Read only the source/docs needed for the task unless changing shared interfaces, coordinate semantics, hardware motion, YAML schemas, or protocol setup.

## Hardware Safety

Any code/config change can affect real motion, instruments, samples, or connected controllers.

Always tell the user:

- Hardware touched or potentially affected.
- Offline validation performed.
- Required physical validation still pending.

For hardware-facing changes, use this handoff order by default:

1. Run focused offline/unit validation for the edited behavior.
2. Stop and give the user the exact hardware test procedure before cleanup or broad test sweeps.
3. After the user confirms the hardware result or asks to continue, clean up temporary files/checkpoints and run broader relevant tests.

Prefer dry-runs and validation scripts before commands that can move gantries, start protocols, or actuate instruments.

## Coordinate Convention

At the repo/user level, use the CubOS deck frame:

- Origin: front-left-bottom (FLB)
- `+X`: operator-right
- `+Y`: back/away
- `+Z`: up
- `-Z`: down

Do not pre-flip signs in high-level code. GRBL `$3` axis direction and `$23` homing direction must make controller WPos match this CubOS deck frame. `$H` should home to the normalized back-right-top (BRT) corner.

Current high-level gantry code no longer applies a hidden Z sign flip. Working-volume bounds are deck-frame values.

### Heights: absolute vs. labware-relative

Two kinds of Z fields coexist:

- **Absolute deck-frame Z** (`gantry.cnc.safe_z`, gantry working-volume
  bounds, `move` command's `travel_z`, named positions, literal `[x, y, z]`
  targets). `safe_z` is the travel ceiling: every resolved approach/action
  Z must be ≤ `safe_z`. Defaults to `working_volume.z_max` when omitted.
- **Labware-relative offsets** (`measurement_height`,
  `interwell_scan_height` on `scan`/`measure`). Positive = above the
  labware's calibrated surface Z; negative = below. Resolved at command
  time as `well.z + relative_offset`, where `well.z` is the calibrated
  deck-frame surface Z. The labware's `height` is the *physical outer
  dimension*, not a Z reference.

These offsets live on the protocol command, never on instruments. `scan`
requires both `measurement_height` and `interwell_scan_height`; `measure`
requires `measurement_height`. Pipette commands engage at the labware
reference Z (`measurement_height = 0` implicitly). ASMI
`indentation_limit_height` is a signed labware-relative offset (mm above
the well surface; negative = below); must be at or below
`measurement_height`.

## Where to Look

Use `docs/agent-index.md` for exact files/tests. Common entrypoints:

- Gantry/motion/origin: `src/gantry/`, `setup/calibrate_deck_origin.py`, `setup/calibrate_multi_instrument_board.py`
- Board/instrument offsets: `src/board/`
- Deck/labware YAML: `src/deck/`, `configs/deck/`
- Protocol YAML/setup/commands: `src/protocol_engine/`, `configs/protocol/`, `setup/validate_setup.py`
- Bounds/safety validation: `src/validation/`
- Instruments: `src/instruments/<instrument>/`
- Persistence: `data/data_store.py`, `src/protocol_engine/measurements.py`

## Calibration Scripts

- `setup/calibrate_deck_origin.py`: single-instrument deck-origin calibration.
- `setup/calibrate_multi_instrument_board.py`: guided multi-instrument board calibration.
  - CLI: `python setup/calibrate_multi_instrument_board.py --gantry <gantry.yaml>`
  - Prompts for reference instrument, lowest instrument, and artifact/block XYZ.
  - Starts guided jogging from the homed BRT pose; it does not make an automatic center move.
  - Sets XY with `G10 L20 P1 X0 Y0` only, then later sets Z with `G10 L20 P1 Z0` using the lowest instrument.
  - Per-instrument calibration uses inverse `Board.move()` math:
    - `offset_x = artifact_x - gantry_x`
    - `offset_y = artifact_y - gantry_y`
    - `depth = gantry_z - artifact_z`

## Progress / Checkpoints

Create a temporary checkpoint under `progress/` for large refactors, hardware-facing motion changes, long tasks, or tasks likely to be handed off. Keep it current with scope, changed files, validation, hardware impact, open risks, and next steps.

For small localized edits, do not create progress files unless useful.

When the task is complete, either delete the temporary checkpoint after promoting durable notes into docs/PRs, or explicitly state why it remains.

## Documentation Updates

Update relevant docs when changing:

- Coordinate, motion, calibration, safety, or validation semantics.
- Public CLI arguments or workflows.
- YAML schemas/config invariants.
- Protocol command behavior or setup flow.
- Cross-repo interfaces.

Do not expand this file into a full module map; put detailed retrieval pointers in `docs/agent-index.md`.
