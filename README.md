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
| `cub.yaml` | Cub |
| `cub_xl.yaml` | Cub-XL |

### 2. Deck (`configs/deck/*.yaml`)

Defines physical labware on the deck. Well plates use two-point calibration
(`calibration.a1` + `calibration.a2`); vials use a single fixed location
(`location.z` is the bottom-center Z of the vial).

Holder fixtures (`tip_disposal`, `well_plate_holder`, `vial_holder`) model
collision envelopes and carry references to the labware they hold. Each vial
or well plate is defined **once at the top level** with an explicit z; the
holder references it by name. The holder enforces that each referenced
vial/plate's z matches `holder.location.z + labware_seat_height_from_bottom_mm`
and raises a clear error on drift.

Exact-position `tip_rack` entries are also supported for pipette pickup
targets. At runtime, all labware expose shared base-level `geometry` metadata
(currently a bounding box).

```yaml
labware:
  asmi_plate:
    type: well_plate
    name: asmi_plate
    model_name: asmi_96_well
    rows: 8
    columns: 12
    calibration:
      a1: { x: 100.0, y: 100.0, z: 15.0 }
      a2: { x: 109.0, y: 100.0, z: 15.0 }
    x_offset_mm: 9.0
    y_offset_mm: 9.0

  # Each vial's location.z must equal
  # holder.location.z + holder.labware_seat_height_from_bottom_mm.
  # The holder validator enforces this; mismatches raise at load time.
  vial_1:
    type: vial
    name: vial_1
    model_name: 20ml_vial
    height_mm: 57.0
    diameter_mm: 28.0
    location: { x: 17.1, y: 0.9, z: 182.0 }
    capacity_ul: 20000.0
    working_volume_ul: 18000.0

  vial_holder:
    type: vial_holder
    name: reagent_vials
    location: { x: 17.1, y: 132.9, z: 164.0 }
    vials: [vial_1]
```

Python API:

- `VialHolder.vials` is `Dict[str, Vial]`, keyed by vial name.
- `WellPlateHolder.well_plate` is `Optional[WellPlate]`.
- `VialHolder.get_vial_top_z(name)` and `WellPlateHolder.get_plate_top_z()`
  return the absolute deck Z of the top of the held labware.
- `Vial.get_bottom_center()` / `Vial.get_top_center()` return the seated
  surface and rim coordinates.
- Each contained labware carries a non-serialized `.holder` back-reference.

Included examples:

- `configs/deck/panda_deck.yaml` — YAML deck config derived from `panda.json`, with two 2x15 tip racks, a well plate holder, and a 9-vial holder referencing nine top-level vial entries.

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

Optional per-instrument extras pull in vendor SDKs only when you need them:

```bash
# Admiral Instruments SquidStat potentiostat (PySide6 + SquidstatPyLibrary)
pip install -e ".[potentiostat]"
```

Interactive jog test:

```bash
python setup/hello_world.py
```

Validate a setup:

```bash
python setup/validate_setup.py \
    configs/gantry/cub.yaml \
    configs/deck/mofcat_deck.yaml \
    configs/board/mofcat_board.yaml \
    configs/protocol/protocol.sample.yaml
```

Run a protocol:

```bash
python setup/run_protocol.py \
    configs/gantry/cub.yaml \
    configs/deck/mofcat_deck.yaml \
    configs/board/mofcat_board.yaml \
    configs/protocol/protocol.sample.yaml
```

Programmatic setup:

```python
from protocol_engine.setup import setup_protocol

protocol, context = setup_protocol(
    gantry_path="configs/gantry/cub.yaml",
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
