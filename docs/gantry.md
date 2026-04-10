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

`total_z_height` is required and must be greater than zero. Deck labware can use a `height` field instead of explicit Z coordinates; in that case CubOS computes user-space Z as `total_z_height - height`.

`y_axis_motion` is optional and defaults to `head`. Use `head` when the gantry head moves along Y, and `bed` when the machine bed moves along Y.

Working volume bounds are inclusive. Current configs include both positive-space gantries and the older ASMI negative-space gantry, so match the coordinate convention used by your selected gantry config.

## Supported Gantries

| Config | System | Working Volume |
|--------|--------|----------------|
| `cubos_xl.yaml` | CubOS-XL / Genmitsu 3018 PRO | 400 x 300 x 80 mm |
| `cubos.yaml` | CubOS / Genmitsu 3018 PROVer V2 | 300 x 200 x 80 mm |
| `genmitsu_3018_PROver_v2.yaml` | PANDA / Genmitsu 3018 PROVer V2 | 300 x 200 x 80 mm |
| `genmitsu_3018_PRO_Desktop.yaml` | CUB / Genmitsu 3018 PRO Desktop | 281 x 181 x 80 mm |
| `asmi_gantry.yaml` | ASMI / Genmitsu 3018 PRO | negative-space 400 x 300 x 80 mm |
