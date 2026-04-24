# Gantry

The gantry is the CNC motion platform that moves instruments over the deck. CubOS communicates with GRBL-based controllers over serial.

## Config

Gantry YAML defines:

- serial port
- CNC homing strategy
- total Z reference height
- Y-axis motion mode
- working volume
- optional `structure_clearance_z`
- optional GRBL settings expectations

Representative example:

```yaml
serial_port: /dev/ttyUSB0
cnc:
  homing_strategy: xy_hard_limits
  total_z_height: 90.0
  y_axis_motion: head
  structure_clearance_z: 75.0

working_volume:
  x_min: 0.0
  x_max: 300.0
  y_min: 0.0
  y_max: 200.0
  z_min: 0.0
  z_max: 80.0

grbl_settings:
  dir_invert_mask: 2
  status_report: 0
  hard_limits: true
  homing_enable: true
  homing_dir_mask: 3
  homing_pull_off: 2.0
  steps_per_mm_x: 800.0
  steps_per_mm_y: 800.0
  steps_per_mm_z: 800.0
  max_travel_x: 300.0
  max_travel_y: 200.0
  max_travel_z: 80.0
```

Use this file when:

- switching to a different gantry
- changing travel limits
- updating homing behavior
- validating expected controller settings

## CNC Fields

`homing_strategy` must be one of:

- `xy_hard_limits`
- `standard`
- `manual_origin`

`total_z_height` is required and must be greater than zero. It describes the configured vertical envelope. Deck labware can use a `height` field instead of explicit Z coordinates; under the deck-origin convention that `height` is used directly as the deck-frame Z value.

`y_axis_motion` is optional and defaults to `head`. Use `head` when the gantry head moves along Y, and `bed` when the machine bed moves along Y.

`structure_clearance_z` is optional. When set, validation requires first-entry scan travel and explicit named/literal move `travel_z` values to meet or exceed that absolute Z plane before entering home/park/edge-risk regions.

Working volume bounds are inclusive and use the CubOS deck frame:

- CubOS `(0, 0, 0)` is the front-left-bottom reachable work volume. Because
  normalized machines home at the opposite top-back-right corner, run the
  deck-origin calibration script to jog to a known-height front-left reference
  surface, assign that pose as `X=0`, `Y=0`, `Z=<reference_height>`, then
  measure the homed pose as `(x_max, y_max, z_max)`.
- `+X` moves right from the operator perspective.
- `+Y` moves away from the operator, toward the back of the deck.
- `+Z` moves up, away from the deck.
- `-Z` moves down, toward the deck.
- GRBL may still physically home at top-back-right. That machine-frame detail
  should remain isolated inside the gantry/GRBL boundary.

Protocol movement names describe absolute deck-frame Z planes:

- `measurement_height` is where an instrument performs its action. For ASMI,
  this is the indentation start height.
- `interwell_travel_height` is the scan travel height between wells and should
  default to `measurement_height` when omitted.
- `entry_travel_height` is the first scan transit height.
- `park_position` is an explicit rest pose.
- ASMI `indentation_limit` is the lower/deeper stopping Z, so a downward
  indentation has `indentation_limit < measurement_height`.

## GRBL Axis And Homing Normalization

Use this procedure when bringing up a new machine or normalizing multiple GRBL
controllers to the same physical convention.

Target behavior:

- home is back-right-top
- `+X` moves right
- `+Y` moves back, away from the user
- `+Z` moves up

In CubOS gantry config, these GRBL fields map to the live controller settings:

- `grbl_settings.dir_invert_mask` -> `$3`
- `grbl_settings.homing_dir_mask` -> `$23`

Inspect the current controller state first:

```text
$$
```

Record `$3` and `$23` before changing anything.

### Safety

- ensure the tool is clear of fixtures, stock, and cables
- keep a hand on the E-stop or controller reset
- use low jog speeds while validating motion

### Procedure

1. Start with a known homing direction, for example:

   ```text
   $23=0
   ```

2. Run homing:

   ```text
   $H
   ```

3. Check which corner the machine reaches. The goal is back-right-top.
4. If homing is wrong, adjust `$23` and home again. GRBL uses this bitmask:
   - `X=1`
   - `Y=2`
   - `Z=4`

   Example:

   ```text
   $23=3
   ```

   This flips the X and Y homing directions.

5. After homing is correct, jog each axis and verify:
   - `+X` moves right
   - `+Y` moves back
   - `+Z` moves up

6. If jogging is wrong, adjust `$3` using the same bitmask:

   ```text
   $3=2
   ```

   This inverts Y motion.

7. Run `$H` again after changing `$3`. `$3` and `$23` are coupled, so a motion
   change can also affect homing behavior.
8. Repeat the `$23` and `$3` adjustments until both of these are true:
   - `$H` always goes to back-right-top
   - positive jog directions are right, back, and up
9. Save the final `$3` and `$23` values in the gantry config so the expected
   controller settings are documented with the machine:

   ```yaml
   grbl_settings:
     dir_invert_mask: 2
     homing_dir_mask: 3
   ```

10. Calibrate the CubOS work origin using the deck-origin script:

   ```bash
   python setup/calibrate_deck_origin.py --gantry configs_new/gantry/cub_xl_asmi_deck_origin.yaml
   ```

   The script sends `$H`, clears transient `G92` offsets, asks for a known
   reference surface height above true deck/bottom Z=0, prompts the operator to
   jog one reference TCP to the front-left XY reference and known Z surface,
   sets that pose with `G10 L20 P1 X0 Y0 Z<reference_height>`, then re-homes
   and reads WPos at the homed back-right-top corner. That measured WPos is the
   physical working volume for the setup. Do not treat nominal or configured
   max-travel values as physical truth until this measurement is done.

   Use `--reference-z-mm 0` only when the reference TCP can touch the true
   bottom plane. If it cannot, place a known-height block or artifact at the
   front-left XY reference and pass that height:

   ```bash
   python setup/calibrate_deck_origin.py --gantry configs_new/gantry/cub_xl_asmi_deck_origin.yaml --reference-z-mm 10
   ```

   To also record the lowest safe reachable Z for that one TCP, add:

   ```bash
   python setup/calibrate_deck_origin.py --gantry configs_new/gantry/cub_xl_asmi_deck_origin.yaml --reference-z-mm 10 --measure-reachable-z-min
   ```

   This reach note is per-instrument. The deck bottom remains absolute Z=0
   even when the mounted TCP cannot physically reach it.

### Acceptance Criteria

- `$H` always goes to back-right-top
- `+X`, `+Y`, and `+Z` always move right, back, and up
- after `setup/calibrate_deck_origin.py`, homed WPos reports the measured
  physical working-volume maxima
- the same `$3` / `$23` pair is documented and reused for identical machines

### Quick Reference

- `$3` bitmask: `X=1`, `Y=2`, `Z=4`
- `$23` bitmask: `X=1`, `Y=2`, `Z=4`
- `$3` controls motion direction
- `$23` controls homing direction
- validate them together, not independently

## Supported Gantries

| Config | System | Working Volume |
|--------|--------|----------------|
| `cub_xl.yaml` | CubOS-XL / Genmitsu 3018 PRO | 400 x 300 x 80 mm |
| `cub.yaml` | CubOS / Genmitsu 3018 PROVer V2 | 300 x 200 x 80 mm |
