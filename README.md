# CubOS

CubOS is a lab automation package for running self-driving experiments on a
modified CNC gantry.

## Configuration

Four YAML files define a runnable experiment:

### 1. Gantry (`configs/gantry/*.yaml`)

Defines the controller serial port, homing strategy, working volume, optional
structure-clearance plane, optional GRBL expectations, and
`cnc.total_z_height`.

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
  structure_clearance_z: 85.0

working_volume:
  x_min: 0.0
  x_max: 399.0
  y_min: 0.0
  y_max: 280.0
  z_min: 0.0
  z_max: 87.0
```

Included examples:

| Config | System |
|--------|--------|
| `configs/gantry/cub_xl_asmi.yaml` | Cub-XL + ASMI |
| `configs/gantry/cub_filmetrics.yaml` | Cub + Filmetrics |

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

### 3. Board (`configs/board/*.yaml`)

Defines instruments mounted on the gantry head, including offsets and
hardware-specific parameters.

Board-level Z semantics:

- `measurement_height` is the absolute deck-frame Z where the instrument
  performs its action when no protocol-level override is supplied.
- `safe_approach_height` is the absolute deck-frame Z used for XY travel to a
  labware target. It must be at or above `measurement_height`.
- These board-level fields are used by generic deck-target motion such as
  `move` to a deck target, `measure`, and pipette commands.

```yaml
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

### 4. Protocol (`configs/protocol/*.yaml`)

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
- `scan.entry_travel_height` is the absolute deck-frame Z used only for the
  first move into the first well.
- `scan.interwell_travel_height` is the absolute deck-frame Z used for
  well-to-well travel and final scan retract.
- Legacy scan names `entry_travel_z`, scan-level `safe_approach_height`, and
  ASMI `z_limit` are rejected before motion.

ASMI-specific note:

- Board YAML `measurement_height` is the generic absolute deck-frame action Z
  used by shared movement helpers.
- Scan-level `measurement_height` is the absolute deck-frame Z where
  `ASMI.indentation()` begins.
- `indentation_limit` is the lower stopping Z; downward indentation requires
  `indentation_limit < measurement_height`.

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

Calibrate the deck-origin work frame before trusting real motion:

```bash
PYTHONPATH=src python setup/calibrate_deck_origin.py \
  --gantry configs/gantry/cub_xl_asmi.yaml \
  --instrument asmi
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
  configs/board/asmi_board.yaml \
  configs/protocol/asmi_move_a1.yaml
```

Run a protocol:

```bash
PYTHONPATH=src python setup/run_protocol.py \
  configs/gantry/cub_xl_asmi.yaml \
  configs/deck/asmi_deck.yaml \
  configs/board/asmi_board.yaml \
  configs/protocol/asmi_move_a1.yaml
```

`setup/run_protocol.py` runs offline validation first, then:

- connects to the gantry
- clears the expected GRBL alarm state if present and restores controller state
- connects all board instruments
- executes the protocol
- disconnects instruments and gantry in `finally`

Programmatic setup:

```python
from protocol_engine.setup import setup_protocol

protocol, context = setup_protocol(
    gantry_path="configs/gantry/cub_xl_asmi.yaml",
    deck_path="configs/deck/asmi_deck.yaml",
    board_path="configs/board/asmi_board.yaml",
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
