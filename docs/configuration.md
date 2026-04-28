# Configuration

CubOS uses three YAML inputs to define a runnable experiment. Together they describe the machine, the deck layout, and the step sequence.

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
- optional structure-clearance Z
- optional GRBL settings expectations
- mounted instruments, offsets, and driver-specific settings

Representative example:

```yaml
serial_port: /dev/cu.usbserial-140
cnc:
  homing_strategy: standard
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
    measurement_height: 3.0
```

Use this file when:

- switching to a different gantry
- changing travel limits
- updating homing behavior
- validating expected controller settings
- changing mounted instruments, offsets, reach depths, or instrument-specific connection settings

CubOS is cut over to the deck-origin frame. Protocol `home` runs GRBL homing
and preserves the persistent G54 work-coordinate frame established by
`setup/calibrate_deck_origin.py`; it does not zero WPos after homing. Protocol
setup rejects gantry configs whose X/Y minima are not `0.0` or whose Z minimum
is negative.

## Deck Config

Deck YAML defines labware positions. Well plates use calibration anchors, while single-location labware such as vials store a direct position.
All deck Z values use the CubOS deck-origin frame: `+Z` is up, and a labware `height` field is a direct absolute deck-frame Z value.

Representative well plate example:

```yaml
labware:
  plate_1:
    type: well_plate
    name: corning_96_well_360ul
    model_name: corning_3590_96well
    rows: 8
    columns: 12
    calibration:
      a1:
        x: 100.0
        y: 60.0
        z: 20.0
      a2:
        x: 109.0
        y: 60.0
        z: 20.0
    x_offset_mm: 9.0
    y_offset_mm: -9.0
    capacity_ul: 360.0
    working_volume_ul: 200.0
```

Use this file when:

- labware is moved or re-calibrated
- the physical deck arrangement changes
- a different plate or vial layout is installed

## Instrument Config

Mounted instruments are defined inside the gantry YAML under `instruments`.
Offsets are relative to the gantry/router reference point.
`measurement_height` and `safe_approach_height` are absolute deck-frame Z planes, not labware-relative offsets.

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
    measurement_height: 3.0
```

## Protocol Config

Protocol YAML defines the experiment step sequence. It should be the file you change most often during routine experiment work.

Representative example:

```yaml
protocol:
  - move:
      instrument: uvvis
      position: plate_1.A1
  - measure:
      instrument: uvvis
      position: plate_1.A1
```

Use this file when:

- changing the experimental sequence
- adding measurement or liquid-handling steps
- adjusting step parameters without changing the machine layout

## Recommended Editing Rule

If the physical machine setup has not changed, edit the protocol file and leave the gantry and deck files alone.
