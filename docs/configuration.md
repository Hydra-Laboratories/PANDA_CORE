# Configuration

CubOS uses four YAML inputs to define a runnable experiment. Together they describe the machine, the layout, the mounted tools, and the step sequence.

## Directory Layout

```text
configs/
  gantry/     # Machine envelope, serial port, homing strategy
  deck/       # Labware placement and calibration
  board/      # Mounted instruments and offsets
  protocol/   # Ordered protocol steps
```

## Gantry Config

Gantry YAML defines:

- serial port
- CNC homing strategy
- total Z reference height
- Y-axis motion mode
- working volume
- optional GRBL settings expectations

Representative example:

```yaml
serial_port: /dev/cu.usbserial-140
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
```

Use this file when:

- switching to a different gantry
- changing travel limits
- updating homing behavior
- validating expected controller settings

## Deck Config

Deck YAML defines labware positions. Well plates use calibration anchors, while single-location labware such as vials store a direct position.

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
        x: -17.88
        y: -42.23
        z: -20.0
      a2:
        x: -17.88
        y: -51.23
        z: -20.0
    x_offset_mm: -9.0
    y_offset_mm: -9.0
    capacity_ul: 360.0
    working_volume_ul: 200.0
```

Use this file when:

- labware is moved or re-calibrated
- the physical deck arrangement changes
- a different plate or vial layout is installed

## Board Config

Board YAML defines mounted instruments and their offsets relative to the gantry/router.

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

Use this file when:

- a different instrument is mounted
- offsets or reach depths change
- instrument-specific connection settings change

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

If the physical machine setup has not changed, edit the protocol file and leave the gantry, deck, and board files alone.
