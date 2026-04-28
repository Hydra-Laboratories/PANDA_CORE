# CubOS Configs

These configs use the deck-origin CubOS frame:

- Origin `(0, 0, 0)` is the front-left-bottom reachable work volume.
- Protocol `home` preserves the calibrated persistent G54 WPos instead of
  rewriting work coordinates after homing.
- `+X` moves to the operator's right.
- `+Y` moves away from the operator, toward the back of the gantry.
- `+Z` moves up, away from the deck.
- `-Z` moves down, toward the deck.

## Directory Layout

```text
configs/
  gantry/     # Machine envelope, GRBL expectations, mounted instruments
  deck/       # Labware placement and calibration
  protocol/   # Ordered protocol steps
```

There are no separate board YAMLs. Mounted instruments and their offsets live
inside the corresponding `configs/gantry/*.yaml` machine file.

## Runnable ASMI Example

```bash
python setup/validate_setup.py \
  configs/gantry/cub_xl_asmi.yaml \
  configs/deck/asmi_deck.yaml \
  configs/protocol/asmi_move_a1.yaml
```

For the full indentation protocol:

```bash
python setup/validate_setup.py \
  configs/gantry/cub_xl_asmi.yaml \
  configs/deck/asmi_deck.yaml \
  configs/protocol/asmi_indentation.yaml
```

## Current Files

- `gantry/cub_xl_asmi.yaml` - measured ASMI Cub-XL setup.
- `gantry/cub_xl_sterling.yaml` - Sterling ASMI setup.
- `gantry/cub_filmetrics.yaml` - Filmetrics setup with placeholder optical
  TCP values that still require hardware calibration.
- `gantry/cub_xl_panda.yaml` - PANDA estimate with placeholder camera/capper
  instrument entries; those placeholders parse as config data but will not
  instantiate until real instrument drivers are registered.
- `deck/asmi_deck.yaml`, `deck/sterling_deck.yaml`,
  `deck/filmetrics_deck.yaml`, `deck/panda_deck.yaml`.
- `protocol/asmi_move_a1.yaml`, `protocol/asmi_indentation.yaml`,
  `protocol/sterling_park.yaml`, `protocol/filmetrics_scan.yaml`.

## Validation Status

Offline setup validation is useful for schema, bounds, and protocol semantics,
but it does not prove safe real motion. Before running any hardware protocol,
verify GRBL `$3`, `$10`, `$20`, `$22`, `$23`, `$130`, `$131`, and `$132`, home
to the expected back-right-top corner, jog each positive axis, and run
`setup/calibrate_deck_origin.py` for the active machine/TCP.
