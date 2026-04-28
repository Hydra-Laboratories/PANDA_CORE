# Gantry

The gantry is the CNC motion platform that moves instruments over the deck. CubOS communicates with GRBL-based controllers over serial.

## Config

Gantry YAML defines:

- serial port
- CNC homing strategy
- total Z reference height
- Y-axis motion mode
- working volume
- optional GRBL settings expectations
- mounted instruments and offsets

Representative example:

```yaml
serial_port: /dev/ttyUSB0
cnc:
  homing_strategy: xy_hard_limits
  total_z_height: 90.0
  y_axis_motion: head

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

instruments:
  uvvis:
    type: uvvis_ccs
    vendor: thorlabs
    offset_x: 0.0
    offset_y: 0.0
    depth: 0.0
    measurement_height: 3.0
```

Use this file when:

- switching to a different gantry
- changing travel limits
- updating homing behavior
- validating expected controller settings
- changing mounted instruments or their offsets

## CNC Fields

`homing_strategy` must be one of:

- `xy_hard_limits`
- `standard`
- `manual_origin`

`total_z_height` is required and must be greater than zero. Deck labware can use a `height` field instead of explicit Z coordinates; in that case CubOS computes user-space Z as `total_z_height - height`.

`y_axis_motion` is optional and defaults to `head`. Use `head` when the gantry head moves along Y, and `bed` when the machine bed moves along Y.

Working volume bounds are inclusive. Current configs include both positive-space gantries and the older ASMI negative-space gantry, so match the coordinate convention used by your selected gantry config.

## Planned Deck-Origin CubOS Convention

Issue #87 tracks a refactor to make the user-facing CubOS frame deck-origin
instead of gantry-top-origin. Until that migration lands, check the selected
config and tests before assuming these semantics are active everywhere.

Target convention:

- CubOS `(0, 0, 0)` is the front-left-bottom reachable work volume after
  homing, backing off limits, and setting WPos zero.
- `+X` moves right from the operator perspective.
- `+Y` moves away from the operator, toward the back of the deck.
- `+Z` moves up, away from the deck.
- `-Z` moves down, toward the deck.
- GRBL may still physically home at top-back-right. That machine-frame detail
  should remain isolated inside the gantry/GRBL boundary.

Under that target convention, protocol movement names should describe intent:

- `measurement_height` is where an instrument performs its action. For ASMI,
  this is the indentation start height.
- `interwell_travel_height` is the scan travel height between wells and should
  default to `measurement_height` when omitted.
- `entry_travel_height` is the first scan transit height.
- `park_position` is an explicit rest pose and should replace ambiguous names
  such as `safe_z` in examples.

Phase 1 uses only the new protocol names:

- `interwell_travel_height`
- `entry_travel_height`
- ASMI `indentation_limit`

Until the deck-origin semantic change lands, scan-level heights remain absolute
Z coordinates in the current positive-down user space.

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

### Acceptance Criteria

- `$H` always goes to back-right-top
- `+X`, `+Y`, and `+Z` always move right, back, and up
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
| `cub_xl.sample.yaml` | CubOS-XL / Genmitsu 3018 PRO | 400 x 300 x 100 mm |
| `cub.sample.yaml` | CubOS / Genmitsu 3018 PROVer V2 | 300 x 200 x 80 mm |
| `cub_xl_asmi.yaml` | ASMI / Genmitsu 3018 PRO | 390 x 290 x 95 mm |
| `cub_filmetrics.yaml` | Filmetrics/UV-Vis / Genmitsu 3018 PROVer V2 | 280 x 175 x 36 mm |
