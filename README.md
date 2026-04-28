# CubOS

CubOS is a lab automation package for running self-driving experiments on a
modified CNC gantry.

## Configuration

Three YAML files define a runnable experiment:

### 1. Gantry (`configs/gantry/*.yaml`)

Defines the controller serial port, homing strategy, working volume, optional
GRBL expectations, `cnc.total_z_height`, and the instruments mounted on that
gantry.

Coordinate convention:

- User-facing coordinates are always treated as positive `X`, `Y`, and `Z`.
- Callers should think in the lab/workcell coordinate system, not raw CNC
  machine coordinates.
- The underlying gantry boundary code currently translates user-facing `Z`
  values to negative machine `Z` before sending them to the controller, similar
  to CNC mode. Callers should not manually negate `Z`; that translation stays
  internal.
- TODO: in a later PR, redefine `Z` from the base deck reference instead of
  the gantry head/top reference.

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
  uvvis:
    type: uvvis_ccs
    vendor: thorlabs
    offset_x: 0.0
    offset_y: 0.0
    depth: 0.0
    measurement_height: 3.0
```

Included examples:

| Config | System |
|--------|--------|
| `cub.sample.yaml` | Cub / Sterling UV-Vis sample |
| `cub_xl.sample.yaml` | Cub-XL mock UV-Vis sample |
| `cub_xl_asmi.yaml` | Cub-XL ASMI indenter |
| `cub_filmetrics.yaml` | Cub Filmetrics/UV-Vis mock |

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

### 3. Protocol (`configs/protocol/*.yaml`)

Defines the experiment as a sequence of commands. Positions can reference
labware by key and well ID, for example `plate_1.A1`.

```yaml
positions:
  safe_z: [0.0, 0.0, 20.0]

protocol:
  - home:
  - move:
      instrument: uvvis
      position: plate_1.A1
```

Available protocol commands include `home`, `move`, `scan`, `measure`,
`pause`, and the pipette command set.

## Mounted Instruments

Mounted instruments now live inside the selected gantry YAML. This keeps the
machine, controller, and head-mounted tool configuration together.

Instrument Z semantics:

- `measurement_height` is the instrument's relative action offset from the
  labware reference Z.
- `safe_approach_height` is the instrument's relative XY-travel offset from
  the labware reference Z.
- These gantry instrument fields are used by generic deck-target motion such as
  `move` to a deck target, `measure`, and pipette commands.

```yaml
instruments:
  pipette:
    type: pipette
    vendor: opentrons
    offset_x: 5.0
    offset_y: 0.0
    depth: 0.0
```

Protocol motion notes:

- `positions:` entries such as `safe_z` are protocol named positions, not deck
  labware.
- `move` accepts optional `travel_z` for named/literal XYZ targets. That forces
  a retract-first transit: move Z to `travel_z`, travel in XY at that Z, then
  finish at the target position.
- `scan.entry_travel_z` is an absolute Z used only for the first move into the
  first well.
- `scan.safe_approach_height` is also an absolute Z, but only for well-to-well
  travel inside the scan.
- This is intentionally different from gantry instrument `safe_approach_height`,
  which remains a relative offset from labware for generic motion helpers.

ASMI-specific note:

- ASMI has two different `measurement_height` concepts.
- Gantry YAML instrument `measurement_height` is the generic relative
  instrument offset.
- `scan.method_kwargs.measurement_height` for `ASMI.indentation()` is an
  absolute Z where the indentation begins.

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

Manual-origin homing:

```bash
python setup/home_manual.py
```

This uses the same user-facing positive `X/Y/Z` convention. The script and
high-level gantry wrapper handle any controller-specific `Z` translation
internally.

Validate a setup:

```bash
python setup/validate_setup.py \
    configs/gantry/cub.sample.yaml \
    configs/deck/mofcat_deck.yaml \
    configs/protocol/scan.yaml
```

Run a protocol:

```bash
python setup/run_protocol.py \
    configs/gantry/cub.sample.yaml \
    configs/deck/mofcat_deck.yaml \
    configs/protocol/scan.yaml
```

`setup/run_protocol.py` runs offline validation first, then:

- connects to the gantry
- clears the expected GRBL alarm state if present and restores controller state
- connects all mounted instruments
- executes the protocol
- disconnects instruments and gantry in `finally`

Programmatic setup:

```python
from protocol_engine.setup import setup_protocol

protocol, context = setup_protocol(
    "configs/gantry/cub.sample.yaml",
    "configs/deck/mofcat_deck.yaml",
    "configs/protocol/scan.yaml",
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
