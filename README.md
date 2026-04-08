# CubOS

CubOS is a lab automation package for running self-driving experiments on a
modified CNC gantry.

## Configuration

Four YAML files define a runnable experiment:

### 1. Gantry (`configs/gantry/*.yaml`)

Defines the controller serial port, homing strategy, working volume, optional
GRBL expectations, and `cnc.total_z_height`.

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
```

Included examples:

| Config | System |
|--------|--------|
| `cubos.yaml` | Cub |
| `cubos_xl.yaml` | Cub-XL |

### 2. Deck (`configs/deck/*.yaml`)

Defines physical labware on the deck. Well plates use two-point calibration
(`calibration.a1` + `calibration.a2`); vials use a single fixed location.

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
```

### 3. Board (`configs/board/*.yaml`)

Defines instruments mounted on the gantry head, including offsets and
hardware-specific parameters.

```yaml
instruments:
  pipette:
    type: pipette
    vendor: opentrons
    offset_x: 5.0
    offset_y: 0.0
    depth: 0.0
```

### 4. Protocol (`configs/protocol/*.yaml`)

Defines the experiment as a sequence of commands. Positions can reference
labware by key and well ID, for example `plate_1.A1`.

```yaml
protocol:
  - home:
  - move:
      instrument: pipette
      position: plate_1.A1
```

Available protocol commands include `home`, `move`, `scan`, `measure`,
`pause`, and the pipette command set.

## Setup and Execution

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Interactive jog test:

```bash
python setup/hello_world.py
```

Validate a setup:

```bash
python setup/validate_setup.py \
    configs/gantry/cubos.yaml \
    configs/deck/mofcat_deck.yaml \
    configs/board/mofcat_board.yaml \
    configs/protocol/protocol.sample.yaml
```

Run a protocol:

```bash
python setup/run_protocol.py \
    configs/gantry/cubos.yaml \
    configs/deck/mofcat_deck.yaml \
    configs/board/mofcat_board.yaml \
    configs/protocol/protocol.sample.yaml
```

Programmatic setup:

```python
from protocol_engine.setup import setup_protocol

protocol, context = setup_protocol(
    gantry_path="configs/gantry/cubos.yaml",
    deck_path="configs/deck/mofcat_deck.yaml",
    board_path="configs/board/mofcat_board.yaml",
    protocol_path="configs/protocol/protocol.sample.yaml",
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
