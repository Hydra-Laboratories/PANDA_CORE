# 2026-05-05 — Add `well_depth` to WellPlate

## Scope

`WellPlate` already carries an `height` (outer plate height, rim → underside
of plate including skirt/feet). It did **not** carry the *inside* depth (rim →
floor where the sample sits), even though analysis pipelines need that to
compute sample thickness from a contact point. ASMI's analysis path was
working around this with a manual `well_bottom_z` knob in `analysis.yaml` —
defaulting to `-85.0` (positive-down legacy convention) and silently wrong
under the new deck-origin +Z-up frame.

This commit teaches WellPlate the inside depth so any consumer can derive
`well_bottom_z = a1.z - well_depth` from the plate object directly.

## What changed

- `src/deck/yaml_schema.py` — add `well_depth: Optional[float]` (gt=0) to
  both `WellPlateYamlEntry` and `NestedWellPlateYamlEntry`. Backward-compatible:
  default `None`; existing deck YAMLs that don't declare it keep loading.
- `src/deck/labware/well_plate.py` — add `well_depth: Optional[float]`
  field + positive-value field validator.
- `src/deck/loader.py` — `_build_well_plate` already auto-wires matching
  fields via `_entry_kwargs_for_model`; only `_build_nested_well_plate`
  needed an explicit pass-through.
- `src/deck/labware/definitions/sbs_96_wellplate/SBS96WellPlate.yaml` —
  declare `well_depth: 10.67` (standard flat-bottom shallow SBS96, e.g.
  Corning 3585). Documents the rim-vs-inside distinction in comments.
- `src/deck/labware/definitions/sbs_96_wellplate/README.md` — add the inside
  depth to the dimensions table and call out the (outer, inside) pair as
  intentionally separate.

## Tests

`tests/test_deck_loader.py`:

- `test_well_plate_carries_well_depth_to_plate_object` — explicit
  `well_depth: 10.67` flows from yaml → entry → plate object.
- `test_well_plate_well_depth_is_optional_default_none` — pre-existing
  deck YAMLs without the field still load; plate's `well_depth` is None.
- `test_well_plate_well_depth_must_be_positive` — negative values fail
  schema validation.
- `test_load_name_sbs_96_wellplate_carries_default_well_depth` —
  `load_name: sbs_96_wellplate` users get the registry default (10.67) without
  per-deck overrides.

Full suite: 1033 passed, 4 subtests passed.

## Hardware impact

None directly. The new field is metadata; no motion or instrument code reads
it yet. ASMI's analysis pipeline will be wired up in a follow-up commit on
the ASMI_new side once this lands.

## Why a separate field instead of overloading `height`

`height` already describes the outer plate height (calibration rim →
underside of plate, including skirt). The inside well depth is a different
quantity (rim → inside floor where the sample sits), and the two diverge by
a few millimeters depending on the well-bottom geometry and skirt thickness.
Mixing them would silently break either the existing footprint/clearance
math or the new sample-thickness math. Two separate fields keep both
explicit.

## Open follow-ups

- ASMI_new: drop `measurement.well_bottom_z` from `analysis.yaml` and update
  `src/analysis.py` + `scripts/analyze_from_db.py` to compute it as
  `plate.a1.z - plate.well_depth`. (Tracked separately, after this PR
  lands.)
- Add `well_depth` to other well-plate definitions if/when added (deep-well
  2 mL ≈ 38 mm; V-bottom ≈ vertex-depth dependent).
