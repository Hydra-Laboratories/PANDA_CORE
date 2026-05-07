# Gantry

The gantry is the CNC motion platform that moves instruments over the deck.
CubOS communicates with GRBL-based controllers over serial.

## Coordinate Convention

The high-level gantry boundary uses the CubOS deck frame:

- origin `(0, 0, 0)` is the front-left-bottom reachable work volume
- `+X` moves right from the operator perspective
- `+Y` moves away from the operator, toward the back of the deck
- `+Z` moves up, away from the deck
- `-Z` moves down, toward the deck

The low-level controller may physically home at the opposite back-right-top
corner. That machine-frame detail stays at the controller/GRBL boundary. CubOS
does not apply a hidden Z sign flip in the high-level `Gantry` wrapper.

Protocol `home` runs GRBL `$H` and preserves the calibrated G54 WPos frame. It
does not apply `G92` or redefine work coordinates after homing.

## Config

Gantry YAML defines:

- serial port
- CNC homing strategy
- total Z reference height
- Y-axis motion mode
- working volume
- optional `safe_z` (absolute deck-frame travel ceiling)
- optional GRBL settings expectations
- mounted instruments, offsets, reach depths, optional `measurement_height`,
  and driver settings

Representative example:

```yaml
serial_port: /dev/ttyUSB0
cnc:
  homing_strategy: standard
  total_z_height: 87.0
  y_axis_motion: head
  # Absolute deck-frame Z used for inter-labware travel and the entry
  # approach to the first well of a scan. Defaults to working_volume.z_max.
  safe_z: 85.0

working_volume:
  x_min: 0.0
  x_max: 399.0
  y_min: 0.0
  y_max: 280.0
  z_min: 0.0
  z_max: 87.0

grbl_settings:
  dir_invert_mask: 1
  status_report: 0
  homing_enable: true
  homing_dir_mask: 0

instruments:
  asmi:
    type: asmi
    vendor: vernier
    offset_x: 0.0
    offset_y: 0.0
    depth: 0.0
    # Labware-relative offset (mm above labware.height_mm; negative = below).
    # Optional here — the protocol scan/measure command may supply it instead.
    # At least one source must set it; if both set, values must match.
    measurement_height: -1.0
```

Use this file when:

- switching to a different gantry
- changing travel limits
- updating homing behavior
- recording expected controller settings
- changing mounted instruments, offsets, reach depths, or driver-specific connection settings

## CNC Fields

`homing_strategy` must be `standard`, which runs GRBL `$H`.

`total_z_height` is required and must be greater than zero. It describes the
configured vertical envelope. Deck labware can use a `height` field instead of
explicit Z coordinates; under the deck-origin convention that `height` is used
directly as the deck-frame Z value.

`y_axis_motion` is optional and defaults to `head`. Use `head` when the gantry
head moves along Y, and `bed` when the machine bed moves along Y.

`safe_z` is optional and defaults to `working_volume.z_max`. It is the
absolute deck-frame Z used for inter-labware travel and the entry approach
for the first well of a scan. Validation requires every resolved approach
and action Z to satisfy `z <= safe_z` so the gantry can always retract
above the deck.

## Working Volume

Working volume bounds are inclusive and use the CubOS deck frame.

Protocol setup requires:

- `x_min: 0.0`
- `y_min: 0.0`
- non-negative `z_min`

Use [Calibrate Deck Origin](calibration.md) to measure the physical working
volume. The calibration script jogs to the front-left lower-reach origin, sets
X/Y with `G10 L20 P1 X0 Y0`, assigns Z by bottom contact or ruler gap, then
re-homes and reports the measured homed WPos as `(x_max, y_max, z_max)`.

For one-instrument bottom contact, use `z_min: 0.0`. For ruler-gap calibration,
use the measured gap as `z_min`. Example: if the TCP stops 5 mm above deck and
the homed WPos reads `Z=105`, use `z_min: 5.0`, `z_max: 105.0`.

Multi-instrument setups need per-instrument lower-reach limits and inactive-tool
collision checks instead of one global lower reach for every tool.

## Instrument Fields

Mounted instruments live under the gantry YAML `instruments` key.

- `offset_x` and `offset_y` describe XY offsets from the gantry/router
  reference point.
- `depth` is positive tool depth below the gantry reference point; in the +Z-up
  deck frame, gantry Z is computed as target/tool Z plus `depth`.
- `measurement_height` and `safe_approach_height` are *labware-relative*
  offsets (mm above `labware.height_mm`; negative = below).
  `measurement_height` is owned by the instrument config and is required
  here for any instrument that engages with labware; protocol commands
  do not accept it. `safe_approach_height` may be set here, on the
  `scan` command, or both; at least one source must define it and
  conflicting values across sources are rejected.

Inter-labware and first-well-entry travel use the gantry-level `safe_z`,
not any instrument field.

## Protocol Height Fields

Protocol heights are *labware-relative* offsets above `labware.height_mm`
(positive = above the surface; negative = below):

- `measurement_height` is the action plane offset for `measure` and
  `scan`. It is owned by the instrument config — set it in the gantry
  YAML's `instruments:` block, not on the protocol command.
- `safe_approach_height` is the between-wells XY-travel offset for
  `scan`. May be set on the instrument config, the `scan` command, or
  both; at least one source must define it and conflicting values
  across sources are rejected. Must be at or above `measurement_height`.
- `park_position` is an explicit rest pose (absolute coords, not relative).
- ASMI `indentation_limit` is a sign-agnostic *magnitude* — the descent
  distance below the action plane.

Legacy names `entry_travel_z`, `entry_travel_height`,
`interwell_travel_height`, and ASMI `z_limit` are rejected before motion.

## Controller Bring-Up

Axis and homing normalization is controller administration, not routine
operator calibration. Use [Gantry Bring-Up](admin/gantry-bring-up.md) when a
machine is new or controller direction/WPos behavior is unknown.

That admin procedure covers:

- controller setting snapshots and rollback notes
- `$3` jog direction invert mask
- `$10` WPos status reporting
- `$23` homing direction invert mask
- WPos/MPos/WCO checks

## Supported Gantries

| Config | System | Current status |
|--------|--------|----------------|
| `configs/gantry/cub_xl_asmi.yaml` | CubOS-XL + ASMI | Measured deck-origin ASMI config from 2026-04-24; still requires staged hardware checks before broad reuse |
| `configs/gantry/cub_xl_sterling.yaml` | Sterling ASMI | Sterling ASMI setup; validate on hardware before real protocols |
| `configs/gantry/cub_filmetrics.yaml` | Cub + Filmetrics | Converted deck-origin starting point; recalibrate and hardware-validate before real Filmetrics runs |
| `configs/gantry/cub_xl_panda.yaml` | CubOS-XL + PANDA-style board | Estimated layout/config surface; placeholders require follow-up before real multi-instrument use |
