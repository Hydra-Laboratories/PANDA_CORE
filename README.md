# CubOS

CubOS is a lab automation package for running self-driving experiments on a
modified CNC gantry.

## Configuration

Three YAML files define a runnable experiment:

### 1. Gantry (`configs/gantry/*.yaml`)

Defines the controller serial port, homing strategy, working volume, optional
absolute `safe_z` plane (used for inter-labware travel), fixed machine
structures, optional GRBL expectations, `cnc.total_z_height`, and the
instruments mounted on that machine.

Coordinate convention:

- User-facing coordinates are in the CubOS deck frame.
- Origin is the front-left-bottom reachable work volume.
- `+X` moves right, `+Y` moves back/away, and `+Z` moves up.
- Protocol `home` preserves the calibrated G54 work-coordinate frame and does
  not apply `G92` or rewrite WPos after homing.

```yaml
serial_port: /dev/ttyUSB0
cnc:
  homing_strategy: standard
  total_z_height: 87.0
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

machine_structures:
  right_x_max_rail:
    type: box
    x_min: 480.0
    x_max: 540.0
    y_min: 0.0
    y_max: 300.0
    z_min: 0.0
    z_max: 100.0

instruments:
  asmi:
    type: asmi
    vendor: vernier
    offset_x: 0.0
    offset_y: 0.0
    depth: 0.0
```

Included examples:

| Config | System |
|--------|--------|
| `configs/gantry/cub_xl_asmi.yaml` | Cub-XL + ASMI |
| `configs/gantry/cub_filmetrics.yaml` | Cub + Filmetrics |
| `configs/gantry/cub_xl_sterling.yaml` | Sterling ASMI |

### 2. Deck (`configs/deck/*.yaml`)

Defines physical labware on the deck. Well plates use two-point calibration
(`calibration.a1` + `calibration.a2`); vials use a single fixed location.
Holder fixtures are also supported for collision-aware deck modeling and future
nesting workflows: `tip_holder`, `tip_disposal`, `well_plate_holder`, and
`vial_holder`. Exact-position `tip_rack` entries are also supported for pipette
pickup targets. Holders can define nested contained labware so holder seat
height contributes directly to experiment Z generation. At runtime, all labware
expose shared base-level `geometry` metadata; for current deck models this is
represented as a bounding box.

```yaml
labware:
  plate:
    load_name: sbs_96_wellplate
    name: asmi_96_well
    model_name: asmi_96_well
    calibration:
      a1: { x: 347.0, y: 42.0, z: 30.0 }
      a2: { x: 338.0, y: 42.0, z: 30.0 }
    x_offset_mm: -9.0
    y_offset_mm: 9.0
```

Instrument blocks carry only physical mounting state (offsets, depth,
hardware-specific config). Labware-relative motion heights
(`measurement_height`, `safe_approach_height`) live on the protocol
command — see the Protocol section below. Inter-labware travel uses the
gantry-level `safe_z`, not any instrument field.

`machine_structures` are fixed gantry-level safety obstacles, not deck labware.
They can live outside `working_volume`; protocol validation rejects commanded
instrument points and known travel segments that intersect a structure box.

### 3. Protocol (`configs/protocol/*.yaml`)

Defines the experiment as a sequence of commands. Positions can reference
labware by key and well ID, for example `plate.A1`.

```yaml
positions:
  park_position: [360.0, 260.0, 85.0]

protocol:
  - home:
  - move:
      instrument: asmi
      position: plate.A1
```

Available protocol commands include `home`, `move`, `scan`, `measure`,
`pause`, and the pipette command set.

Protocol motion notes:

- `positions:` entries such as `park_position` are protocol named positions,
  not deck labware.
- `move` accepts optional `travel_z` for named/literal XYZ targets. That forces
  a retract-first transit: move Z to `travel_z`, travel in XY at that Z, then
  finish at the target position.
- Scan and measure take labware-relative heights as first-class command
  arguments: `scan` requires both `measurement_height` (action plane)
  and `safe_approach_height` (between-wells XY-travel plane, must be at
  or above the action plane); `measure` requires `measurement_height`.
  Both are mm above the well/labware calibrated surface Z (negative = below). Pipette
  commands engage at the labware reference Z (well bottom, tip top)
  with no Z offset.
- The first well of a scan and inter-labware travel use the gantry's
  absolute `cnc.safe_z` (default `working_volume.z_max`).
- Legacy names `entry_travel_z`, `entry_travel_height`,
  `interwell_travel_height`, and ASMI `z_limit` are rejected before motion.

ASMI-specific note:

- `ASMI.indentation()` begins at the resolved action plane
  (`well.z + measurement_height`) and descends by
  `indentation_limit` mm. `indentation_limit` is sign-agnostic: only its
  magnitude matters.

## Setup and Execution

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional per-instrument extras pull in vendor SDKs only when you need them:

```bash
# Admiral Instruments SquidStat potentiostat (PySide6 + SquidstatPyLibrary)
pip install -e ".[potentiostat]"
```

Calibrate the deck-origin work frame before trusting real motion. For a
single-instrument setup:

```bash
PYTHONPATH=src python setup/calibrate_deck_origin.py \
  --gantry configs/gantry/cub_xl_asmi.yaml \
  --instrument asmi
```

For a multi-instrument gantry config, use the guided board calibration. It
prompts for the left-most reference instrument, the lowest instrument, and the
known artifact/block point. It starts from the homed BRT pose and does not make
an automatic center move. It sets G54 WPos X/Y first, then sets WPos Z=0 from
the lowest instrument, then records each instrument's `offset_x`, `offset_y`,
and `depth` from the artifact point:

```bash
PYTHONPATH=src python setup/calibrate_multi_instrument_board.py \
  --gantry configs/gantry/cub_xl_multi.yaml
```

See the docs for the full operator tutorial:

```text
docs/calibration.md
```

Interactive jog test:

```bash
PYTHONPATH=src python setup/hello_world.py \
  --gantry configs/gantry/cub_xl_asmi.yaml
```

Validate a setup:

```bash
PYTHONPATH=src python setup/validate_setup.py \
  configs/gantry/cub_xl_asmi.yaml \
  configs/deck/asmi_deck.yaml \
  configs/protocol/asmi_move_a1.yaml
```

Run a protocol:

```bash
PYTHONPATH=src python setup/run_protocol.py \
  configs/gantry/cub_xl_asmi.yaml \
  configs/deck/asmi_deck.yaml \
  configs/protocol/asmi_move_a1.yaml
```

`setup/run_protocol.py` runs offline validation first, then:

- connects to the gantry
- clears the expected GRBL alarm state if present and restores controller state
- connects all configured instruments
- executes the protocol
- disconnects instruments and gantry in `finally`

Programmatic setup:

```python
from protocol_engine.setup import setup_protocol

protocol, context = setup_protocol(
    gantry_path="configs/gantry/cub_xl_asmi.yaml",
    deck_path="configs/deck/asmi_deck.yaml",
    protocol_path="configs/protocol/asmi_move_a1.yaml",
    mock_mode=True,
)
protocol.run(context)
```

## Data Persistence

Campaign state can be stored in SQLite through `data.DataStore`. Measurement
commands can log into a `ProtocolContext` when `data_store` and `campaign_id`
are provided.

## Development

```bash
PYTHONPATH=src pytest tests/
```
