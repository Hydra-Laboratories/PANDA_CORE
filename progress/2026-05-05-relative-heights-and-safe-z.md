# 2026-05-05 — Relative heights and gantry `safe_z`

Hardware-facing motion refactor. Replaces the inconsistent absolute/relative
treatment of measurement and approach heights with a clean split:

- **`safe_z`** (gantry yaml, top level): absolute deck-frame Z. Defaults to
  `working_volume.z_max`. Used for all inter-labware moves and the entry
  approach for the first well of a scan. Renamed from `structure_clearance_z`.
- **`measurement_height`**: now relative to `labware.height_mm` (positive =
  above surface, +Z up). Dual-source rule — at least one of:
  - `gantry.instruments.<name>.measurement_height`
  - protocol `measure` / `scan` command field

  must be set; if both are set, the values must match.
- **`safe_approach_height`**: relative to `labware.height_mm`. Required on
  every protocol `scan`. Removed from instrument yaml entirely.
- ASMI: `well_top_z` derived from `labware.height_mm` at command time;
  `safe_z` instrument field removed (gantry-level now); `indentation_limit`
  becomes a sign-agnostic magnitude.

## Why

Today `measure.py` already treats `instr.measurement_height` as a relative
offset (`coord.z - instr.measurement_height`) while `scan.py` treats the
same field as absolute. Inter-labware travel currently uses
`instr.safe_approach_height` instead of a gantry-level safe plane. This
refactor heals both inconsistencies and pushes per-labware semantics into
the labware definition (`height_mm`).

## Hardware impact

Every Z motion in `measure`, `scan`, and inter-labware moves is rewired.
Wrong sign or wrong reference = collision. Mid-air guards before any motion
runs:

1. Dual-source validator (no measurement_height anywhere, or two
   conflicting sources).
2. `labware.height_mm` presence check on every measure/scan target.
3. Bounds check: resolved absolute Z within `[z_min, z_max]`.
4. Scan-only: `safe_approach_height >= measurement_height` and
   `height_mm + safe_approach_height <= safe_z`.

All existing protocol/gantry configs become invalid and are rewritten.

## Plan

1. Tests first per phase, then implementation.
2. Phase 1: schemas — gantry `safe_z`, instrument fields, scan/measure args.
3. Phase 2: semantic validation (dual-source rule, bounds, height_mm).
4. Phase 3: movement (measure + scan + ASMI).
5. Phase 4: rewrite configs.
6. Phase 5: docs.
7. Phase 6: offline validation, then hand off hardware test procedure
   before broad test sweeps.

## Status

Offline phases complete. Awaiting hardware validation before broader sweep
or cleanup.

## Validation log

- `python -m pytest tests/` — **1077 passed, 4 subtests passed** (full
  test suite, including new dual-source/safe_z/sign-agnostic tests, plus
  post-merge additions: gantry-injection in `measure` via
  `inject_runtime_args`, scan now routed through the same dispatch
  helper instead of inline injection, `tests/protocol_engine/test_dispatch.py`
  covers the helper directly, finite-number type-guard in
  `resolve_height_field`, `KeyError`→`ValueError` translation in
  `engage_at_labware`, pipette commands wrap `engage_at_labware`'s
  `ValueError` into `ProtocolExecutionError`, `well_depth_mm` passthrough
  in nested wellplate builder).
- `python setup/validate_setup.py configs/gantry/cub_xl_asmi.yaml
  configs/deck/asmi_deck.yaml configs/protocol/asmi_indentation.yaml` —
  **PASS** (96 positions × 1 instrument; semantic validation OK).
- `python setup/validate_setup.py configs/gantry/cub_filmetrics.yaml
  configs/deck/filmetrics_deck.yaml configs/protocol/filmetrics_scan.yaml`
  — **PASS** (96 positions × 1 instrument).
- `python setup/validate_setup.py configs/gantry/cub_xl_sterling.yaml
  configs/deck/sterling_deck.yaml configs/protocol/sterling_park.yaml`
  — **PASS**.
- `python setup/validate_setup.py configs/gantry/cub_xl_sterling.yaml
  configs/deck/sterling_deck.yaml configs/protocol/sterling_vial_scan.yaml`
  — **PASS**.
- `python setup/validate_setup.py configs/gantry/cub_xl_asmi.yaml
  configs/deck/asmi_deck.yaml configs/protocol/asmi_move_a1.yaml`
  — **PASS**.

## Hardware test procedure (handoff)

Run on physical hardware after homing/WPos calibration is verified:

1. **Filmetrics non-contact measure (smoke test).** Uses
   `configs/protocol/filmetrics_scan.yaml`. Watch the Z trajectory in the
   GRBL status:
   - Gantry should rise to `safe_z` (= `working_volume.z_max` since the
     filmetrics gantry yaml leaves `safe_z` unset → default).
   - For the first well, descend to `height_mm + safe_approach_height
     = 70 + 10 = 80`, then to `height_mm + measurement_height = 80`
     (same plane for a non-contact instrument).
   - For subsequent wells, XY at `80` (no separate descent), then act.
   - End of scan: rise back to `80`.

2. **ASMI indentation (low-energy first run).** Uses
   `configs/protocol/asmi_indentation.yaml`. Confirm:
   - First well: rise to `safe_z=85`, XY travel, descend to `height_mm
     + safe_approach_height = 30 + 8 = 38`, then to `height_mm +
     measurement_height = 30 + (-1) = 29` (1 mm into the well).
   - Indentation routine descends `indentation_limit=5` mm below the
     action plane (deepest abs Z = 24).
   - Force-limit guard fires before the 5 mm magnitude is exhausted on
     real wells.

3. **Inter-labware safety check.** Move from `plate.A1` to a different
   labware (or back to `park_position`) and confirm the gantry routes
   through `safe_z` rather than the previous `safe_approach_height`
   value.

If anything looks off, abort with feed hold (`!`) before any collision.

## Next steps

- After Charl confirms hardware passes (or asks to continue): run broader
  test sweep, run lints, delete this progress file (notes already in
  PR/docs).
- If hardware reveals issues, extend the validators or movement code as
  needed and re-test.

## Open risks

- Need to verify `labware.height_mm` is set on every wellplate referenced
  by an existing protocol — fail-fast if missing.
- ASMI indentation routine assumes a sign convention today; need to walk
  the math when making the limit sign-agnostic.

