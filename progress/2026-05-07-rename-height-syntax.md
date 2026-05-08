# 2026-05-07 — Consistent height/z naming syntax

Project-wide rename to enforce a single naming convention:

- **`[name]_height`** — labware-relative offset in mm. `+` is above the
  reference, `-` is below. Direction is in the sign.
- **`[name]_z`** — absolute deck-frame Z (WPos).
- **Dimensional fields drop the `_mm` suffix** — units are implicit
  (mm) per the convention; `length`, `width`, `height`, `well_depth`,
  `diameter`, etc.

Branch: `rename-height` off `staging`. 1092 tests green.

## Renames

| Before | After | Notes |
|--------|-------|-------|
| `safe_approach_height` | `interwell_scan_height` | Same semantic. |
| `indentation_limit` | `indentation_limit_height` | **Semantic shift**: was a sign-agnostic *magnitude*; now a signed offset above the well surface (`-5.0` = 5 mm into the well). Must be ≤ `measurement_height`. |
| `total_z_height` | `total_z_range` | Range of motion, not an offset. |
| `height_mm` | `height` | Physical dimension. |
| `length_mm` / `width_mm` | `length` / `width` | |
| `well_depth_mm` | `well_depth` | |
| `diameter_mm` | `diameter` | |
| `labware_support_height_mm` | `labware_support_height` | |
| `labware_seat_height_from_bottom_mm` | `labware_seat_height_from_bottom` | |
| `x_offset_mm` / `y_offset_mm` | `x_offset` / `y_offset` | Pitch, not a relative offset-with-direction. |
| `z_pickup` / `z_drop` (tip rack) | `pickup_z` / `drop_z` | `_z` suffix for absolute Z. |
| `_z_target` (ASMI internal) | `_target_z` | Local var rename. |

## Internal API consequences

`indentation_limit_height` is signed. ASMI's `indentation()` no longer
accepts a magnitude — its method API now takes absolute Z values:

```python
def indentation(
    self, gantry, *,
    measurement_z: float,   # absolute deck-frame action plane Z
    target_z: float,        # absolute deck-frame deepest descent Z
    step_size: float | None = None,
    force_limit: float | None = None,
    baseline_samples: int | None = None,
    measure_with_return: bool = False,
):
```

The protocol command (`scan`) does the relative→absolute resolution:

- `action_z = well.z + measurement_height`
- `target_z = well.z + indentation_limit_height`

`inject_runtime_args` was updated to inject `measurement_z` (absolute,
renamed from `measurement_height`) and a new optional `target_z`. The
old name `measurement_height` was misleading because the engine always
forwarded an absolute Z under that label — now the kwarg name matches
the value.

The constructor field `default_indentation_limit` was dropped — ASMI
no longer has a meaningful default; the engine always supplies
`target_z`.

## Removed: legacy `height` z-hint in deck YAML

Pre-rename, deck YAML had two distinct `height_mm` (dimensional) and
`height` (z-hint) fields. Renaming `height_mm` → `height` collided with
the legacy z-hint, so the z-hint shorthand was removed. Calibration
anchors (`calibration.a1.z` for plates/holders/tip racks,
`location.z` for vials) are now the single source of truth for the
labware-surface deck-frame Z.

## Legacy-rejection updates

`scan_args._LEGACY_KWARG_HINTS` rejects (with rename hints):

- `safe_approach_height` → `interwell_scan_height`
- `indentation_limit` → `indentation_limit_height`
- the same fields nested inside `method_kwargs`

## Validation additions

`_validate_scan_command` now asserts
`indentation_limit_height ≤ measurement_height` so the descent is
non-degenerate. Per-field finite checks already in place from the
prior PR continue to surface the offending field name.

## Files touched (high level)

- Source: `src/protocol_engine/{commands,scan_args.py}`,
  `src/instruments/asmi/driver.py`, `src/deck/{yaml_schema,loader}.py`
  and labware modules, `src/gantry/*`, `src/validation/protocol_semantics.py`.
- Configs: `configs/protocol/asmi_indentation.yaml`,
  `configs/gantry/*.yaml`, `configs/deck/panda_deck.yaml`.
- Tests: 30+ files updated to use the new field names and the
  ASMI-method absolute-Z API.
- Docs: `README.md`, `AGENTS.md`, `docs/{board,configuration,gantry,protocol}.md`,
  `configs/README.md`, labware `README.md` and YAML definitions.
