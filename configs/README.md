# CubOS Configs

The `configs/` tree is the current CubOS configuration surface. These files use
the deck-origin coordinate convention:

- origin `(0, 0, 0)` is the front-left-bottom reachable work volume
- protocol `home` preserves the calibrated persistent G54 WPos frame
- `+X` moves to the operator's right
- `+Y` moves away from the operator, toward the back of the gantry
- `+Z` moves up, away from the deck
- `-Z` moves down, toward the deck

Protocol, deck, gantry, and instrument code should speak only in this CubOS
deck frame. GRBL homing direction, raw MPos, WCO, and controller setting
details are admin/setup concerns documented in
`docs/admin/gantry-bring-up.md`.

## Directory Layout

```text
configs/
  gantry/     # Machine envelope, GRBL expectations, mounted instruments
  deck/       # Labware placement and calibration
  protocol/   # Ordered protocol steps
```

There are no separate board YAMLs. Mounted instruments, offsets,
`measurement_height`, and `safe_approach_height` live inside the corresponding
`configs/gantry/*.yaml` machine file.

## Runnable ASMI Example

```bash
PYTHONPATH=src python setup/validate_setup.py \
  configs/gantry/cub_xl_asmi.yaml \
  configs/deck/asmi_deck.yaml \
  configs/protocol/asmi_move_a1.yaml
```

For the full indentation protocol:

```bash
PYTHONPATH=src python setup/validate_setup.py \
  configs/gantry/cub_xl_asmi.yaml \
  configs/deck/asmi_deck.yaml \
  configs/protocol/asmi_indentation.yaml
```

## Current Files

- `gantry/cub_xl_asmi.yaml` - measured ASMI Cub-XL setup.
- `gantry/cub_xl_sterling.yaml` - Sterling ASMI setup.
- `gantry/cub_filmetrics.yaml` - Filmetrics setup with placeholder optical TCP
  values that still require hardware calibration.
- `gantry/cub_xl_panda.yaml` - PANDA estimate with placeholder camera/capper
  instrument entries; those placeholders parse as config data but will not
  instantiate until real instrument drivers are registered.
- `deck/asmi_deck.yaml`, `deck/sterling_deck.yaml`,
  `deck/filmetrics_deck.yaml`, `deck/panda_deck.yaml`.
- `protocol/asmi_move_a1.yaml`, `protocol/asmi_indentation.yaml`,
  `protocol/sterling_park.yaml`, `protocol/sterling_vial_scan.yaml`,
  `protocol/filmetrics_scan.yaml`.

## Height Semantics

All protocol and instrument motion heights are absolute deck-frame Z planes:

- instrument `measurement_height`: default action Z
- instrument `safe_approach_height`: default XY-travel Z for deck-target moves
- scan `measurement_height`: scan action/start Z
- scan `entry_travel_height`: first scan transit Z
- scan `interwell_travel_height`: between-well travel and final retract Z
- ASMI `indentation_limit`: lower/deeper stopping Z

Runtime motion must not add these values to labware Z. Legacy scan names
`entry_travel_z`, scan-level `safe_approach_height`, and ASMI `z_limit` are
rejected before motion.

## Validation Status

Offline setup validation is useful for schema, bounds, and protocol semantics,
but it does not prove safe real motion. Before running any hardware protocol,
verify GRBL `$3`, `$10`, `$20`, `$22`, `$23`, `$130`, `$131`, and `$132`, home
to the expected back-right-top corner, jog each positive axis, and run
`setup/calibrate_deck_origin.py` for the active machine/TCP.
