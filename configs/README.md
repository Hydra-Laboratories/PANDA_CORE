# Deck-Origin Configs

The `configs/` tree is the current CubOS configuration surface. These files use
the deck-origin coordinate convention:

- origin `(0, 0, 0)` is the front-left-bottom reachable work volume
- `+X` moves to the operator's right
- `+Y` moves away from the operator, toward the back of the gantry
- `+Z` moves up, away from the deck
- `-Z` moves down, toward the deck
- protocol `home` preserves the calibrated persistent G54 WPos frame

Protocol, deck, board, and instrument code should speak only in this CubOS deck
frame. GRBL homing direction, raw MPos, WCO, and controller setting details are
admin/setup concerns documented in `docs/admin/gantry-bring-up.md`.

## Directory Layout

```text
configs/
  gantry/     # serial port, homing, working volume, clearance planes
  deck/       # labware positions and calibration anchors
  board/      # mounted instruments, offsets, action/travel Z planes
  protocol/   # ordered protocol steps
```

## ASMI

Primary files:

- `gantry/cub_xl_asmi.yaml`
- `deck/asmi_deck.yaml`
- `board/asmi_board.yaml`
- `protocol/asmi_move_a1.yaml`
- `protocol/asmi_indentation.yaml`

`gantry/cub_xl_asmi.yaml` is the measured ASMI gantry config from the
2026-04-24 deck-origin calibration flow:

- working volume: `X[0.0, 399.0]`, `Y[0.0, 280.0]`, `Z[0.0, 87.0]`
- `cnc.total_z_height: 87.0`
- `structure_clearance_z: 85.0`

The ASMI board uses absolute deck-frame Z planes:

- `measurement_height: 26.0`
- `safe_approach_height: 35.0`

The ASMI indentation protocol uses:

- `entry_travel_height: 85.0`
- `interwell_travel_height: 35.0`
- `measurement_height: 32.0`
- `indentation_limit: 30.0`

Downward indentation decreases Z, so `indentation_limit` must be less than
`measurement_height`.

Hardware status:

- Offline setup validation passes for `asmi_move_a1.yaml` and
  `asmi_indentation.yaml`.
- Treat real motion as untrusted until the staged hardware checks in
  `docs/calibration.md` pass on the target setup.

## Filmetrics

Primary files:

- `gantry/cub_filmetrics.yaml`
- `deck/filmetrics_deck.yaml`
- `board/filmetrics_board.yaml`
- `protocol/filmetrics_scan.yaml`

The Filmetrics configs are converted deck-origin starting points. The board
file intentionally marks optical head offset, depth, and measurement plane as
values to recalibrate on the physical setup.

Required before hardware use:

- run controller bring-up and rollback capture
- calibrate deck origin for the mounted Filmetrics TCP
- verify `measurement_height` and `safe_approach_height` on the real optical
  head
- run offline validation and a staged high-clearance hardware move before scan

## PANDA And Sterling

Primary PANDA-style files:

- `gantry/cub_xl_panda.yaml`
- `deck/panda_deck.yaml`
- `board/panda_board.yaml`

Primary Sterling-style files:

- `gantry/cub_xl_sterling.yaml`
- `deck/sterling_deck.yaml`
- `board/sterling_board.yaml`

These configs preserve the current deck-origin schema surface but still need
setup-specific validation before real multi-instrument motion. The PANDA board
contains placeholders for instruments that may not have complete real drivers
registered yet. Do not treat those entries as ready hardware routes until the
driver registry and physical calibration are confirmed.

## Height Semantics

All protocol and board motion heights are absolute deck-frame Z planes:

- board `measurement_height`: default action Z for an instrument
- board `safe_approach_height`: default XY-travel Z for deck-target moves
- scan `measurement_height`: scan action/start Z
- scan `entry_travel_height`: first scan transit Z
- scan `interwell_travel_height`: between-well travel and final retract Z
- ASMI `indentation_limit`: lower/deeper stopping Z

Runtime motion must not add these values to labware Z. Legacy scan names
`entry_travel_z`, scan-level `safe_approach_height`, and ASMI `z_limit` are
rejected before motion.

## Validation Examples

Minimal ASMI move:

```bash
PYTHONPATH=src python setup/validate_setup.py \
  configs/gantry/cub_xl_asmi.yaml \
  configs/deck/asmi_deck.yaml \
  configs/board/asmi_board.yaml \
  configs/protocol/asmi_move_a1.yaml
```

ASMI indentation:

```bash
PYTHONPATH=src python setup/validate_setup.py \
  configs/gantry/cub_xl_asmi.yaml \
  configs/deck/asmi_deck.yaml \
  configs/board/asmi_board.yaml \
  configs/protocol/asmi_indentation.yaml
```

Offline validation does not prove safe real motion. Use the hardware sequence
in `docs/calibration.md` before trusting a setup with mounted tools, labware, or
samples.
