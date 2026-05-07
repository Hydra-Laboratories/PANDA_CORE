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

## Where to Look

Use `docs/agent-index.md` for exact files/tests. Common entrypoints:

- Gantry/motion/origin: `src/gantry/`, `setup/calibrate_gantry.py`
- Board/instrument offsets: `src/board/`
- Deck/labware YAML: `src/deck/`, `configs/deck/`
- Protocol YAML/setup/commands: `src/protocol_engine/`, `configs/protocol/`, `setup/validate_setup.py`
- Bounds/safety validation: `src/validation/`
- Instruments: `src/instruments/<instrument>/`
- Persistence: `data/data_store.py`, `src/protocol_engine/measurements.py`

## Calibration Scripts

- `setup/calibrate_gantry.py`: user-facing calibration script that requires a seed YAML and output gantry path, then chooses single- or multi-instrument calibration from instrument count.
- `setup/calibrate_gantry.py`: only supported gantry calibration entrypoint. It contains both the single-instrument and multi-instrument flows and selects the correct path from instrument count in the seed YAML.
  - Multi-instrument flow prompts the operator to explicitly choose the reference and lowest instruments by number; blank input is not accepted.
  - Starts guided jogging from the homed BRT pose; it does not make an automatic center move.
  - Sets XY with `G10 L20 P1 X0 Y0` only, then later sets Z to the calibration block height with `G10 L20 P1 Z<block_height>` using the lowest instrument.
  - Per-instrument calibration uses inverse `Board.move()` math against the same physical block point:
    - `offset_x = reference_gantry_x - gantry_x`
    - `offset_y = reference_gantry_y - gantry_y`
    - `depth = gantry_z - lowest_gantry_z`

## Debugging Mode

If the user explicitly says they are debugging, or if their intent is clearly active debugging, prioritize fast diagnosis over the normal TDD loop. Do not add or run unit tests during the live debugging cycle unless the user asks for them or the bug is already fixed and ready to lock down. Temporary instrumentation is acceptable, but tag it clearly and remove it before finalizing.

## Progress / Checkpoints

Create a temporary checkpoint under `progress/` for large refactors, hardware-facing motion changes, long tasks, or tasks likely to be handed off. Keep it current with scope, changed files, validation, hardware impact, open risks, and next steps.

For small localized edits, do not create progress files unless useful.

When the task is complete, either delete the temporary checkpoint after promoting durable notes into docs/PRs, or explicitly state why it remains.

## Documentation Updates

- **`calibrate_gantry.py`**: Preferred user-facing calibration entrypoint. Loads a seed gantry YAML, requires a separate output path, preflights hardware risk and instrument count, then dispatches one-instrument configs to the internal deck-origin flow or multi-instrument configs to the internal board-calibration flow.
    - **Guided usage**: `python setup/calibrate_gantry.py --seed configs/gantry/seeds/<seed>.yaml --output-gantry configs/gantry/<calibrated>.yaml`
    - **Single instrument**: jog the tool to the calibration block at the front-left origin point; X/Y/Z are assigned at the same physical pose, with Z set to the block height.
    - **Multi instrument**: pick the left-most/reference instrument and lowest instrument by number, use a calibration block, then record each instrument's `offset_x`, `offset_y`, and `depth` from the shared block point.
    - **Safety**: this changes G54 WPos and may program GRBL soft limits; validate offline first and calibrate slowly with clear E-stop access.
- **`hello_world.py`**: Interactive deck-origin jog test. Loads an explicit gantry YAML, homes without rewriting WPos, then lets you jog in the CubOS deck frame.
    - **Usage**: `python3 setup/hello_world.py --gantry configs/gantry/cub_xl_asmi.yaml`
    - **Controls**: Arrow keys (X/Y ±1mm), Z key (Z down 1mm), X key (Z up 1mm), Q (quit)
    - **Dependencies**: `src/gantry` (Gantry class), `setup/keyboard_input.py`
- **`validate_setup.py`**: Validate a protocol setup by loading the gantry, deck, and protocol configs and checking that all deck and gantry positions are within the gantry's working volume.
    - **Usage**: `python setup/validate_setup.py <gantry.yaml> <deck.yaml> <protocol.yaml>`
    - **Output**: Step-by-step loading status, labware/instrument summaries, bounds validation results, and a final PASS/FAIL verdict.
    - **Dependencies**: `src/gantry`, `src/deck`, `src/board`, `src/protocol_engine`, `src/validation`
- **`run_protocol.py`**: Load, validate, connect to hardware, and run a protocol end-to-end. Runs offline validation first, then connects to the gantry and executes the protocol.
    - **Usage**: `python setup/run_protocol.py <gantry.yaml> <deck.yaml> <protocol.yaml>`
    - **Startup behavior**:
        - Connects to the gantry, clears the expected GRBL alarm state if present, and restores controller state.
        - Connects all configured instruments before the first protocol step.
        - Disconnects instruments and gantry in `finally`, even on protocol failure.
    - **Dependencies**: `src/gantry`, `src/deck`, `src/board`, `src/protocol_engine`, `src/validation`
- **`keyboard_input.py`**: Helper module that reads single keypresses (including arrow keys) without requiring Enter. Uses `tty`/`termios` (Unix only).

- Coordinate, motion, calibration, safety, or validation semantics.
- Public CLI arguments or workflows.
- YAML schemas/config invariants.
- Protocol command behavior or setup flow.
- Cross-repo interfaces.

Do not expand this file into a full module map; put detailed retrieval pointers in `docs/agent-index.md`.
