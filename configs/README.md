# Candidate Deck-Origin Configs

These configs are estimates for the issue #87 deck-origin coordinate refactor.
They are intentionally separate from `configs/` so legacy setups are not
silently replaced before hardware validation completes.

Use them as Phase 2/3 fixtures for movement-plan tests, waypoint validation,
and staged hardware bring-up. Do not run them on hardware until jog direction,
homing, WPos calibration, and structure-clearance checks have passed.

## Coordinate Frame

- Origin `(0, 0, 0)` is the front-left-bottom reachable work volume.
- Protocol `home` preserves the calibrated persistent G54 WPos instead of
  rewriting work coordinates after homing.
- `+X` moves to the operator's right.
- `+Y` moves away from the operator, toward the back of the gantry.
- `+Z` moves up, away from the deck.
- `-Z` moves down, toward the deck.
- GRBL still physically homes near top-back-right.

## ASMI Estimate Basis

The current ASMI config uses a top/back/right WPos-derived frame:

- A1: `(-51.25, -238.25, 73.0)`
- A2: `(-60.25, -238.25, 73.0)`
- working volume: approximately `400 x 300 x 100 mm`

For this deck-origin candidate:

- `x_new = 400 + x_old`
- `y_new = 300 + y_old`
- `z_new = 100 - z_old`

So the estimated ASMI plate calibration is:

- A1: `(348.75, 61.75, 27.0)`
- A2: `(339.75, 61.75, 27.0)`

This matches the photos qualitatively: the plate sits near the front-right,
columns advance left from A1, and rows advance toward the back.

## Estimated Z Plan

- plate/well-top deck-origin Z: `27.0 mm`
- ASMI indentation start: `measurement_height: 26.0` absolute deck-frame Z
  (`1.0 mm` below the estimated well top)
- ASMI indentation lower limit: `indentation_limit: 24.0` absolute deck-frame Z
  (`3.0 mm` below the estimated well top)
- interwell travel plane: `35.0 mm` absolute deck-frame Z
  (`8.0 mm` above the estimated well top)
- first-entry/park/home-edge structure clearance: about `85.0 mm`

The `85.0 mm` clearance is a conservative estimate from the side view and is
meant to keep the ASMI body above the Y rail during home/park/home-edge motion.
Measure this before trusting any physical run.

Protocol height fields in these candidate configs are absolute deck-frame Z
planes. They are not labware-relative offsets, and runtime motion should not add
them to `labware_z`.

## Files

- `gantry/cub_xl_asmi_deck_origin.yaml`
- `gantry/cub_xl_asmi_deck_origin_2026-04-24.yaml` — dated ASMI measured
  working volume from deck-origin calibration:
  `X[0.0, 399.0]`, `Y[0.0, 280.0]`, `Z[0.0, 87.0]`,
  `cnc.total_z_height: 87.0`.
- `deck/asmi_deck_origin.yaml`
- `board/asmi_board_deck_origin.yaml`
- `protocol/asmi_move_a1_deck_origin.yaml`
- `protocol/asmi_indentation_deck_origin.yaml`

## PANDA Estimate Basis

The PANDA candidate layout is estimated from `panda-deck.jpg` and
`panda-board.jpg` using the same `400 x 300 x 100 mm` Cub XL work volume.

The deck estimate treats the visible deck as:

- well plate holder at the front-left side of the loaded fixture area
- two vertical 2-row x 15-column tip racks in the middle
- black used-tip disposal to the right of the tip racks
- 9-position vial holder on the far-right side

The instrument-board estimate treats the visible moving tools as:

- left red tool: potentiostat probe
- center mount: camera placeholder
- right white tool: vial capper/decapper placeholder

Only `potentiostat` exists as a real board/instrument driver today. The camera
and vial capper/decapper entries in `board/panda_board_deck_origin.yaml` are
intentional placeholders and will not pass the board loader registry check until
real instrument types are added.

Estimated high-clearance Z for first-entry, parking, and home-edge motion is
`85.0 mm`, matching the multi-instrument collision concern from the photos.
That value is not encoded per instrument in the PANDA board YAML because it is
a board/machine-structure clearance constraint, not a measurement standoff.

PANDA files:

- `gantry/cub_xl_panda_deck_origin.yaml`
- `deck/panda_deck_origin.yaml`
- `board/panda_board_deck_origin.yaml`

## Filmetrics Estimate Basis

The Filmetrics candidate layout is translated from the legacy
`configs/deck/filmetrics_deck.yaml` and `configs/gantry/cub_filmetrics.yaml`
using an approximate `280 x 175 x 90 mm` deck-origin volume:

- `x_new = 280 + x_old`
- `y_new = 175 + y_old`
- `z_new = 90 - z_old`

So the legacy plate calibration:

- A1: `(-10.0, -35.0, 20.0)`
- A2: `(-10.0, -44.0, 20.0)`

becomes:

- A1: `(270.0, 140.0, 70.0)`
- A2: `(270.0, 131.0, 70.0)`

The Filmetrics board file uses placeholder/default TCP values. The translated
`measurement_height: 80.0` preserves the old mock board's 10 mm optical standoff
from the top of the 90 mm frame, but it must be recalibrated on the real
Filmetrics setup.

Filmetrics files:

- `gantry/cub_filmetrics_deck_origin.yaml`
- `deck/filmetrics_deck_origin.yaml`
- `board/filmetrics_board_deck_origin.yaml`
- `protocol/filmetrics_scan_deck_origin.yaml`

## Current Validation Status

The ASMI YAML files load under the deck-origin schemas, the estimated plate
wells fit inside the candidate `400 x 300 x 100 mm` working volume, and full
`setup/validate_setup.py` validation passes after the issue #87 Phase 2/3
motion cutover.

The PANDA deck and gantry candidate YAMLs load under the current schemas. The
PANDA board YAML parses against the loose board schema, but the board loader is
expected to reject the camera and vial capper/decapper placeholders until those
drivers are implemented and registered.

The Filmetrics deck, gantry, board, and scan protocol candidates load and pass
offline setup validation with the placeholder board values.
