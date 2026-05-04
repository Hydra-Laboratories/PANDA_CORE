# Calibrate Deck Origin

This tutorial establishes the CubOS deck-origin work frame using explicit
front-left-bottom (FLB) and back-right-top (BRT) GRBL homing profiles from the
gantry YAML. Runtime protocol `home` still uses the normal BRT `$H`; FLB homing
is calibration/admin only.

The calibration script will not infer `$3` or `$23`. If the YAML does not define
both `cnc.calibration_homing.runtime_brt` and
`cnc.calibration_homing.origin_flb`, the script refuses to move.

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
- confirm FLB homing switches are physically present and wired for GRBL homing
- confirm the mounted TCP can be jogged safely at low step/feed after bounds are measured
- run offline setup validation for the protocol you intend to use

```bash
PYTHONPATH=src python setup/validate_setup.py \
  configs/gantry/cub_xl_asmi.yaml \
  configs/deck/asmi_deck.yaml \
  configs/protocol/asmi_move_a1.yaml
```

## Run Guided Calibration

The guided command snapshots rollback GRBL settings, unlocks an initial alarm
if the controller starts in `Alarm`, applies the explicit FLB profile, homes,
and sets G54 WPos `(0, 0, 0)`. It then disables stale soft limits, moves to an
estimated BRT inspection pose from the configured working-volume maxima minus
2 mm, and programs `$130/$131/$132` from that conservative estimate.

The script does not run BRT homing during calibration. It restores the runtime
BRT profile before disconnecting, but BRT WPos and switch impacts are not used
to discover or verify machine dimensions.

For the first physical run, do not attach an instrument. Validate homing and
bounds only:

```bash
PYTHONPATH=src python setup/calibrate_deck_origin.py \
  --gantry configs/gantry/cub_xl_asmi.yaml
```

After FLB homing and the estimated bounds are verified, calibrate one instrument's
TCP offset, depth, lower Z reach, and safe X reach:

```bash
PYTHONPATH=src python setup/calibrate_deck_origin.py \
  --gantry configs/gantry/cub_xl_asmi.yaml \
  --instrument asmi
```

The script moves near the measured deck center and asks the operator to jog the
selected TCP onto the physical center mark before it computes `offset_x` and
`offset_y`.

During the jog step:

- arrow keys jog X/Y
- `X` jogs `+Z` up
- `Z` jogs `-Z` down
- number keys change jog step size
- Enter confirms the current calibration step
- `Q` aborts

The script sets the FLB home pose to G54 WPos zero with:

```text
G10 L20 P1 X0 Y0 Z0
```

It then leaves the calibrated G54 frame in place and restores the runtime BRT
`$3`/`$23` profile before disconnecting. It does not run BRT `$H`.

## Z Reference Modes

The script asks about Z grounding interactively after you jog the TCP to its
lower safe reference. Use bottom mode only when the selected TCP is truly
touching deck bottom at its lower safe reach. Use ruler-gap mode when the TCP
cannot safely reach true deck bottom. Measure the vertical gap from the deck to
the TCP and enter that gap as an absolute deck-frame Z.

```bash
PYTHONPATH=src python setup/calibrate_deck_origin.py \
  --gantry configs/gantry/cub_xl_asmi.yaml \
  --instrument asmi
```

For a 5 mm measured gap, ruler-gap mode records `tcp_z_min: 5.0` under the
selected instrument's `reach_limits`.

## Update Gantry YAML

After assigning FLB WPos zero, the script moves to the conservative estimated
BRT inspection pose. Those estimated values become the working-volume bounds
for this setup. The runtime BRT profile is restored before disconnecting, but
BRT homing is not part of the calibration flow.

Map the result into gantry YAML as follows:

```yaml
cnc:
  total_z_height: <measured_z_max>

working_volume:
  x_min: 0.0
  x_max: <measured_x_max>
  y_min: 0.0
  y_max: <measured_y_max>
  z_min: 0.0
  z_max: <measured_z_max>
```

The selected instrument receives calibrated fields:

```yaml
instruments:
  asmi:
    offset_x: <center_x - gantry_x_at_center_mark>
    offset_y: <center_y - gantry_y_at_center_mark>
    depth: <gantry_z_at_lower_reach - tcp_z_min>
    reach_limits:
      gantry_x_min: <safe_left_gantry_x>
      gantry_x_max: <safe_right_gantry_x>
      tcp_z_min: <0 for deck touch, otherwise measured gap>
```

This keeps one shared FLB deck frame and models lower reach per instrument
instead of encoding a one-tool lower reach as global `working_volume.z_min`.

## Hardware Validation

Before trusting the calibrated setup:

1. First run FLB origin plus estimated BRT inspection with no instrument attached and no samples.
2. Verify FLB `$H`, estimated X/Y/Z bounds, and WPos repeatability across at least three cycles.
3. Run the one-instrument TCP calibration at low jog step/feed with E-stop ready.
4. Run the interactive jog test.

   ```bash
   PYTHONPATH=src python setup/hello_world.py \
     --gantry configs/gantry/cub_xl_asmi.yaml
   ```

5. Confirm `+X`, `+Y`, `+Z`, and `-Z` move in the CubOS deck frame.
6. Run the minimal ASMI A1 move only after jog directions are correct.

   ```bash
   PYTHONPATH=src python setup/run_protocol.py \
     configs/gantry/cub_xl_asmi.yaml \
     configs/deck/asmi_deck.yaml \
     configs/protocol/asmi_move_a1.yaml
   ```

7. Run conservative ASMI indentation only after the minimal move is correct.
8. Stop after any unexpected direction, alarm, timeout, coordinate mismatch, or
   clearance concern.

Offline validation and docs builds do not prove safe real motion.
