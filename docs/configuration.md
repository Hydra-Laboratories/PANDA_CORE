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
- optional structure-clearance Z
- optional GRBL settings expectations

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
```

Use this file when:

- switching to a different gantry
- changing travel limits
- updating homing behavior
- validating expected controller settings

CubOS is cut over to the deck-origin frame. Protocol `home` runs GRBL homing
and preserves the persistent G54 work-coordinate frame established by
`setup/calibrate_deck_origin.py`; it does not zero WPos after homing. Protocol
setup rejects gantry configs whose X/Y minima are not `0.0` or whose Z minimum
is negative.

Run [Calibrate Deck Origin](calibration.md) before trusting measured working
volume values on real hardware. Use [Gantry Bring-Up](admin/gantry-bring-up.md)
first if controller direction, homing, or WPos reporting is unknown.

## Deck Config

Deck YAML defines labware positions. Well plates use calibration anchors, while single-location labware such as vials store a direct position.
All deck Z values use the CubOS deck-origin frame: `+Z` is up, and a labware `height` field is a direct absolute deck-frame Z value.

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

## Board Config

Board YAML defines mounted instruments and their offsets relative to the gantry/router.
`measurement_height` and `safe_approach_height` are absolute deck-frame Z planes, not labware-relative offsets.
`safe_approach_height` must be greater than or equal to `measurement_height` in the +Z-up deck frame.

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

Protocol scan heights use the current names `measurement_height`,
`entry_travel_height`, and `interwell_travel_height`. Legacy scan names
`entry_travel_z`, scan-level `safe_approach_height`, and ASMI `z_limit` are
rejected before motion.

## Recommended Editing Rule

If the physical machine setup has not changed, edit the protocol file and leave the gantry, deck, and board files alone.
