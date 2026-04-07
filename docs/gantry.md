# Gantry

The gantry is the CNC motion platform that moves instruments over the deck. CubOS communicates with GRBL-based controllers over serial.

## Config

Gantry YAML defines:

- serial port
- homing strategy
- working volume
- optional GRBL settings expectations

Representative example:

```yaml
serial_port: /dev/ttyUSB0
cnc:
  homing_strategy: standard

working_volume:
  x_min: -400.0
  x_max: 0.01
  y_min: -300.0
  y_max: 0.01
  z_min: -80.0
  z_max: 0.0

grbl_settings:
  homing_enable: true
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

## Supported Gantries

| Config | System | Working Volume |
|--------|--------|----------------|
| `genmitsu_3018_PROver_v2.yaml` | Cub-XL | 300 x 200 x 80 mm |
| `genmitsu_3018_PRO_Desktop.yaml` | Cub | 300 x 200 x 80 mm |
