# Calibrate Deck Origin

This tutorial establishes the CubOS deck-origin work frame for one active
instrument/TCP. Use it after the gantry controller already homes and jogs in
the expected direction. If `$3`, `$23`, `$10`, homing direction, or raw
WPos/MPos behavior are still unknown, do the admin bring-up first:
[Gantry Bring-Up](admin/gantry-bring-up.md).

## Coordinate Target

CubOS protocol, deck, board, and instrument code use one deck frame:

- origin `(0, 0, 0)` is the front-left-bottom reachable work volume
- `+X` moves right from the operator perspective
- `+Y` moves away from the operator, toward the back of the deck
- `+Z` moves up, away from the deck
- `-Z` moves down, toward the deck

Protocol `home` runs GRBL homing and preserves the calibrated G54 WPos frame.
It does not apply `G92` or rewrite work coordinates after homing.

## Before You Start

Use one mounted reference TCP for this calibration. For the current ASMI setup,
the standard gantry file is:

```bash
configs/gantry/cub_xl_asmi.yaml
```

Before touching hardware:

- remove fixtures, samples, and loose cables from the motion path
- keep a hand on the E-stop or controller reset
- confirm the mounted TCP can be jogged safely near the front-left lower reach
- run offline setup validation for the protocol you intend to use

```bash
PYTHONPATH=src python setup/validate_setup.py \
  configs/gantry/cub_xl_asmi.yaml \
  configs/deck/asmi_deck.yaml \
  configs/protocol/asmi_move_a1.yaml
```

## Run Guided Calibration

The guided command homes the gantry, clears transient `G92` offsets, prompts
for interactive jogging to the physical front-left XY origin and lowest safe
reachable Z, assigns only X/Y, assigns Z, then re-homes and reports the measured
working volume.

```bash
PYTHONPATH=src python setup/calibrate_deck_origin.py \
  --gantry configs/gantry/cub_xl_asmi.yaml \
  --instrument asmi
```

During the jog step:

- arrow keys jog X/Y
- `X` jogs `+Z` up
- `Z` jogs `-Z` down
- number keys change jog step size
- Enter confirms the current calibration step
- `Q` aborts

The script assigns X/Y first with:

```text
G10 L20 P1 X0 Y0
```

Then it assigns Z at the same physical pose.

## Z Reference Modes

Use bottom mode only when the active TCP is truly touching deck bottom at the
front-left lower-reach pose:

```bash
PYTHONPATH=src python setup/calibrate_deck_origin.py \
  --gantry configs/gantry/cub_xl_asmi.yaml \
  --z-reference-mode bottom \
  --instrument asmi
```

Bottom mode assigns:

```text
G10 L20 P1 Z0
```

Use ruler-gap mode when the TCP cannot safely reach true deck bottom. Measure
the vertical gap from the deck to the TCP and enter that gap as an absolute
deck-frame Z:

```bash
PYTHONPATH=src python setup/calibrate_deck_origin.py \
  --gantry configs/gantry/cub_xl_asmi.yaml \
  --z-reference-mode ruler-gap \
  --tip-gap-mm 5 \
  --instrument asmi
```

For a 5 mm measured gap, ruler-gap mode assigns:

```text
G10 L20 P1 Z5
```

## Update Gantry YAML

After assigning the work origin, the script re-homes and reports the WPos at
the homed back-right-top corner. Those measured values become the physical
working-volume bounds for this setup.

Map the result into gantry YAML as follows:

```yaml
cnc:
  total_z_range: <measured_z_max>

working_volume:
  x_min: 0.0
  x_max: <measured_x_max>
  y_min: 0.0
  y_max: <measured_y_max>
  z_min: <z_reference_value>
  z_max: <measured_z_max>
```

For bottom contact, `z_min` is `0.0`. For ruler-gap mode, `z_min` is the
measured gap. Example: if the TCP stops 5 mm above deck and the homed WPos
reads `Z=105`, use `z_min: 5.0` and `z_max: 105.0`.

This one-instrument `z_min=<gap>` shortcut is not the final model for mixed
tools. Multi-instrument setups need one shared WPos deck frame plus per-tool
lower-reach limits and collision checks for inactive tools.

## Hardware Validation

Before trusting the calibrated setup:

1. Record the controller setting snapshot and rollback notes from admin bring-up.
2. Run the interactive jog test.

   ```bash
   PYTHONPATH=src python setup/hello_world.py \
     --gantry configs/gantry/cub_xl_asmi.yaml
   ```

3. Confirm `+X`, `+Y`, `+Z`, and `-Z` move in the CubOS deck frame.
4. Run the minimal ASMI A1 move only after jog directions are correct.

   ```bash
   PYTHONPATH=src python setup/run_protocol.py \
     configs/gantry/cub_xl_asmi.yaml \
     configs/deck/asmi_deck.yaml \
     configs/protocol/asmi_move_a1.yaml
   ```

5. Run conservative ASMI indentation only after the minimal move is correct.
6. Stop after any unexpected direction, alarm, timeout, coordinate mismatch, or
   clearance concern.

Offline validation and docs builds do not prove safe real motion.
