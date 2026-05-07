# Configuration

CubOS uses three YAML inputs to define a runnable experiment. Together they
describe the machine, the deck layout, and the step sequence.

## Directory Layout

```text
configs/
  gantry/     # Machine envelope, serial port, homing strategy, instruments
  deck/       # Labware placement and calibration
  protocol/   # Ordered protocol steps
```

## Gantry Config

Gantry YAML defines:

- serial port
- CNC homing strategy
- total Z reference height
- Y-axis motion mode
- working volume
- optional absolute `safe_z` plane (inter-labware travel)
- optional GRBL settings expectations
- mounted instruments, offsets, reach depths, action heights, and driver-specific settings

Representative example:

```yaml
serial_port: /dev/cu.usbserial-140
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

instruments:
  asmi:
    type: asmi
    vendor: vernier
    offset_x: 0.0
    offset_y: 0.0
    depth: 0.0
    # Labware-relative offset (mm above labware.height_mm; negative = below).
    measurement_height: -1.0
```

Use this file when:

- switching to a different gantry
- changing travel limits
- updating homing behavior
- recording expected controller settings
- changing mounted instruments, offsets, reach depths, or instrument-specific connection settings

CubOS is cut over to the deck-origin frame. Protocol `home` runs GRBL homing
and preserves the persistent G54 work-coordinate frame established by
`setup/calibrate_deck_origin.py`; it does not zero WPos after homing. Protocol
setup rejects gantry configs whose X/Y minima are not `0.0` or whose Z minimum
is negative.

Run [Calibrate Deck Origin](calibration.md) before trusting measured working
volume values on real hardware. Use [Gantry Bring-Up](admin/gantry-bring-up.md)
first if controller direction, homing, or WPos reporting is unknown.

## Deck Config

Deck YAML defines labware positions. Well plates use calibration anchors, while
single-location labware such as vials store a direct position.

All deck Z values use the CubOS deck-origin frame: `+Z` is up, and a labware
`height` field is a direct absolute deck-frame Z value.

Representative well plate example:

```yaml
labware:
  plate:
    load_name: sbs_96_wellplate
    name: asmi_96_well
    model_name: asmi_96_well
    calibration:
      a1:
        x: 347.0
        y: 42.0
        z: 30.0
      a2:
        x: 338.0
        y: 42.0
        z: 30.0
    x_offset_mm: -9.0
    y_offset_mm: 9.0
```

Use this file when:

- labware is moved or re-calibrated
- the physical deck arrangement changes
- a different plate or vial layout is installed

## Instrument Config

Mounted instruments are defined inside the gantry YAML under `instruments`.
Offsets are relative to the gantry/router reference point.

`measurement_height` and `safe_approach_height` are *labware-relative*
offsets (mm above the labware's `height_mm` surface; negative = below).
Each may be set on the instrument, on the protocol command, or both —
at least one source must define each, and conflicting values across
sources are rejected. `safe_approach_height` is consumed only by
`scan`. Inter-labware and first-well-entry travel use the gantry-level
`safe_z`, not any instrument field.

Representative example:

```yaml
instruments:
  uvvis:
    type: uvvis_ccs
    vendor: thorlabs
    serial_number: "M00801544"
    dll_path: "TLCCS_64.dll"
    default_integration_time_s: 0.24
    offset_x: 0.0
    offset_y: 0.0
    depth: 0.0
    measurement_height: 3.0   # 3 mm above the plate surface
```

## Protocol Config

Protocol YAML defines the experiment step sequence. It should be the file you
change most often during routine experiment work.

Representative example:

```yaml
protocol:
  - move:
      instrument: uvvis
      position: plate.A1
  - measure:
      instrument: uvvis
      position: plate.A1
```

Use this file when:

- changing the experimental sequence
- adding measurement or liquid-handling steps
- adjusting step parameters without changing the machine layout

Protocol scan heights are labware-relative (mm above `labware.height_mm`):

- `measurement_height` — action plane.
- `safe_approach_height` — between-wells XY-travel plane (must be at or
  above `measurement_height`).

Each may be set on the instrument config, the protocol command, or
both. At least one source must define each; conflicting values across
sources are rejected.

Inter-labware travel uses the gantry's absolute `safe_z`. Legacy names
`entry_travel_z`, `entry_travel_height`, `interwell_travel_height`, and
ASMI `z_limit` are rejected before motion.

## Recommended Editing Rule

If the physical machine setup has not changed, edit the protocol file and leave
the gantry and deck files alone.
