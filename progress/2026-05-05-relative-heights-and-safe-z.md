# 2026-05-05 — Labware-relative heights on commands, and gantry `safe_z`

Hardware-facing motion refactor. Replaces the inconsistent absolute/relative
treatment of measurement and approach heights with a clean split:

- **`safe_z`** (gantry yaml, top level): absolute deck-frame Z. Defaults to
  `working_volume.z_max`. Used for all inter-labware moves and the entry
  approach for the first well of a scan. Renamed from
  `structure_clearance_z`.
- **`measurement_height`**: labware-relative (positive = above the
  calibrated well/labware surface Z, +Z up). First-class arg to the
  protocol command: required on `measure` and `scan`. Removed from
  instrument YAML and `BaseInstrument.__init__`.
- **`safe_approach_height`**: labware-relative. First-class arg to `scan`,
  required. Must be at or above `measurement_height`. Removed from
  instrument YAML.
- **`WellPlate.height_mm`** restored to its documented meaning: the
  plate's *physical outer dimension* (rim → underside). The deck-frame Z
  of the plate surface lives on each well's calibrated `Coordinate3D.z`.
  Motion code derives `ref_z` from the resolved well coordinate, not
  from `height_mm`.
- ASMI: `well_top_z` is the resolved absolute action Z (`well.z +
  measurement_height`), injected at the dispatch boundary. The legacy
  constructor field `z_target` (an absolute deck-frame Z default) is
  renamed to `default_indentation_limit` (a sign-agnostic magnitude) so
  the new semantic isn't a silent reinterpretation of an existing field.
  `indentation_limit` is a sign-agnostic magnitude (descent below the
  action plane).
- Pipette: aspirate/dispense/etc. engage at the labware reference Z (well
  bottom, tip top) — `measurement_height = 0` implicitly; per-command
  Z offsets aren't surfaced yet.

## Why

Earlier iterations let `measurement_height` live on either the instrument
config or the command (with a dual-source matcher), and `scan` accepted
only `safe_approach_height`. The dual-source rule was a constant source
of confusion (which side was authoritative when both differed?), and the
asymmetry between scan and measure made protocol authoring error-prone.
Pinning both heights as required command args removes both problems:
each field has exactly one source, instruments only carry physical
mounting state, and protocols are self-describing — you can read the
scan/measure step and know the exact Z planes without cross-referencing
the gantry YAML.

## Hardware impact

Every Z motion in `measure`, `scan`, and inter-labware moves is rewired.
Wrong sign or wrong reference = collision. Mid-air guards before any
motion runs:

1. Required-fields validator: `measure` rejects missing
   `measurement_height`; `scan` rejects missing `measurement_height` or
   `safe_approach_height`.
2. Calibrated well/labware surface Z presence check (via the resolved
   coordinate) on every measure/scan target.
3. Bounds check: resolved absolute Z within `[z_min, z_max]`.
4. Scan-only: `safe_approach_height >= measurement_height` and
   `height_mm + safe_approach_height <= safe_z`.
5. Legacy field rejector: `interwell_travel_height`,
   `entry_travel_height`, ASMI `z_limit` are explicit semantic
   violations. `measurement_height`/`safe_approach_height` are also
   rejected inside `method_kwargs` and on the instrument YAML — both
   places where they used to be silently swallowed or overwritten.

## Validation

- 1073 unit/integration tests pass.
- Hardware validation pending — see active-checkpoint.

## Files touched (high level)

- `src/instruments/{base_instrument,asmi,filmetrics,pipette,potentiostat,uv_curing,uvvis_ccs}/`
  drivers — strip `measurement_height`/`safe_approach_height` kwargs.
- `src/instruments/yaml_schema.py` — drop both fields from
  `InstrumentYamlEntry`.
- `src/protocol_engine/commands/{_movement,measure,scan,pipette}.py` —
  command boundary now owns the heights.
- `src/protocol_engine/scan_args.py` — drop both height fields; only
  legacy-key rejection and `indentation_limit` reconciliation remain.
- `src/validation/protocol_semantics.py` — read heights from command
  args; require both on `scan`, `measurement_height` on `measure`.
- `configs/gantry/{cub_xl_asmi,cub_xl_sterling,cub_filmetrics}.yaml` —
  drop `measurement_height` from instrument blocks.
- `configs/protocol/{asmi_indentation,filmetrics_scan}.yaml` — both
  heights on the scan step.
- Docs (`README.md`, `docs/{board,configuration,gantry,protocol}.md`,
  `AGENTS.md`, `configs/README.md`).

## Next steps

- Hardware validation on Cub-XL ASMI before trust on physical motion.
- If pipette workflows want a Z offset (e.g. aspirate 2 mm above well
  bottom), promote `measurement_height` to a first-class pipette
  command arg in a follow-up.
