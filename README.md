# CubOS

CubOS is a lab automation package for running self-driving experiments on a
modified CNC gantry.

## Configuration

Three YAML files define a runnable experiment:

### 1. Gantry (`configs/gantry/*.yaml`)

Defines the controller serial port, homing strategy, working volume, optional
GRBL expectations, `cnc.total_z_height`, and the instruments mounted on that
machine.

Coordinate convention:

- User-facing coordinates are always treated as positive `X`, `Y`, and `Z`.
- Callers should think in the CubOS deck frame: front-left-bottom origin,
  `+X` right, `+Y` back, and `+Z` up.
- Protocol homing preserves the calibrated G54 work-coordinate frame and does
  not rewrite WPos after homing.

```yaml
serial_port: /dev/ttyUSB0
cnc:
  homing_strategy: standard
  total_z_height: 90.0

working_volume:
  x_min: 0.0
  x_max: 300.0
  y_min: 0.0
  y_max: 200.0
  z_min: 0.0
  z_max: 80.0

instruments:
  asmi:
    type: asmi
    vendor: vernier
    offset_x: 0.0
    offset_y: 0.0
    depth: 0.0
    measurement_height: 26.0
    safe_approach_height: 35.0
```

Included examples:

| Config | System |
|--------|--------|
| `configs/gantry/cub_filmetrics.yaml` | Cub + Filmetrics |
| `configs/gantry/cub_xl_asmi.yaml` | Cub-XL + ASMI |
| `configs/gantry/cub_xl_sterling.yaml` | Sterling ASMI |

### 2. Deck (`configs/deck/*.yaml`)

Defines physical labware on the deck. Well plates use two-point calibration
(`calibration.a1` + `calibration.a2`); vials use a single fixed location.
Holder fixtures are also supported for collision-aware deck modeling and future
nesting workflows: `tip_holder`, `tip_disposal`, `well_plate_holder`, and
`vial_holder`. Exact-position `tip_rack` entries are also supported for pipette
pickup targets. Holders can define nested contained labware so holder seat
height contributes directly to experiment Z generation. At runtime, all labware
now expose shared base-level `geometry` metadata; for current deck models this
is represented as a bounding box.

```yaml
labware:
  plate:
    type: well_plate
    name: asmi_96_well
    model_name: asmi_96_well
    rows: 8
    columns: 12
    calibration:
      a1: { x: 100.0, y: 100.0, z: 15.0 }
      a2: { x: 109.0, y: 100.0, z: 15.0 }
    x_offset_mm: 9.0
    y_offset_mm: 9.0

  vial_holder:
    type: vial_holder
    name: reagent_vials
    location: { x: 180.0, y: 60.0 }
    height: 20.0
    vials:
      vial_1:
        location: { x: 180.0, y: 60.0 }
        model_name: 20ml_vial
        height_mm: 57.0
        diameter_mm: 28.0
        capacity_ul: 20000.0
        working_volume_ul: 18000.0
```

Included examples:

- `configs/deck/panda_deck.yaml` — YAML deck config derived from `panda.json`, with two 2x15 tip racks, a nested well plate holder, and a nested vial holder. Contained vial / plate Z positions are generated from holder seat heights.

Instrument Z semantics:

- `measurement_height` is the instrument's absolute deck-frame action Z.
- `safe_approach_height` is the instrument's absolute deck-frame XY-travel Z.
- These fields are used by generic deck-target motion such as `move` to a deck
  target, `measure`, `scan`, and pipette commands.

### 3. Protocol (`configs/protocol/*.yaml`)

Defines the experiment as a sequence of commands. Positions can reference
labware by key and well ID, for example `plate_1.A1`.

```yaml
positions:
  safe_z: [0.0, 0.0, 20.0]

protocol:
  - home:
  - move:
      instrument: pipette
      position: plate_1.A1
```

Available protocol commands include `home`, `move`, `scan`, `measure`,
`pause`, and the pipette command set.

Protocol motion notes:

- `positions:` entries such as `safe_z` are protocol named positions, not deck
  labware.
- `move` accepts optional `travel_z` for named/literal XYZ targets. That forces
  a retract-first transit: move Z to `travel_z`, travel in XY at that Z, then
  finish at the target position.
- `scan.entry_travel_height` is an absolute Z used only for the first move into the
  first well.
- `scan.interwell_travel_height` is also an absolute Z, but only for well-to-well
  travel inside the scan.
- Deck-target `move` commands use the instrument's gantry-configured
  `safe_approach_height`.

ASMI-specific note:

- ASMI has two different `measurement_height` concepts.
- Gantry YAML `measurement_height` is the generic absolute instrument action Z.
- Protocol scan `measurement_height` for `ASMI.indentation()` is the absolute Z
  where the indentation begins.

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

Interactive jog test:

```bash
python setup/hello_world.py --gantry configs/gantry/cub_xl_asmi.yaml
```

Deck-origin calibration:

```bash
python setup/calibrate_deck_origin.py --gantry configs/gantry/cub_xl_asmi.yaml --instrument asmi
```

This establishes the persistent G54 work-coordinate frame used by protocol
`home`. Protocol homing does not rewrite WPos.

Validate a setup:

```bash
python setup/validate_setup.py \
    configs/gantry/cub_xl_asmi.yaml \
    configs/deck/asmi_deck.yaml \
    configs/protocol/asmi_move_a1.yaml
```

Run a protocol:

```bash
python setup/run_protocol.py \
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
pytest tests/
```
