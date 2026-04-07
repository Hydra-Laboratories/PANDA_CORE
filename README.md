# PANDA Core

PANDA Core is a lab automation software package for running self-driving experiments via a modified, off-the-shelf CNC gantry. 

## Configuration

Four YAML files fully specify a running experiment:

### 1. Gantry (`configs/gantry/*.yaml`)

Defines the CNC hardware: serial port, homing strategy, working volume bounds, and GRBL board settings.

```yaml
serial_port: /dev/ttyUSB0
cnc:
  homing_strategy: standard

working_volume:
  x_min: -400.0
  x_max: 0.01
  y_min: -300.0
  y_max: 0.01
  z_min: -80.0
  z_max: 0.0

grbl_settings:
  homing_enable: true
  steps_per_mm_x: 800.0
  steps_per_mm_y: 800.0
  steps_per_mm_z: 800.0
  max_travel_x: 300.0
  max_travel_y: 200.0
  max_travel_z: 80.0
```

Two gantry configs are included:

| Config | System | Working Volume |
|--------|--------|----------------|
| `genmitsu_3018_PROver_v2.yaml` | PANDA (XL) | 300 x 200 x 80 mm |
| `genmitsu_3018_PRO_Desktop.yaml` | CUB (Small) | 300 x 200 x 80 mm |

### 2. Deck (`configs/deck/*.yaml`)

Defines physical labware on the deck and their positions. Well plates use two-point calibration (A1 + A2, must be axis-aligned). Vials use a single fixed location.

```yaml
labware:
  plate:
    type: well_plate
    name: asmi_96_well
    model_name: asmi_96_well
    rows: 8
    columns: 12
    calibration:
      a1: { x: -49.7, y: -236.8, z: -50.0 }
      a2: { x: -58.7, y: -236.8, z: -50.0 }
    x_offset_mm: -9.0
    y_offset_mm: 9.0
```

### 3. Board (`configs/board/*.yaml`)

Defines instruments mounted on the gantry head — their type, vendor, hardware-specific config, and XYZ offsets from the head reference point.

```yaml
instruments:
  asmi:
    type: asmi
    offset_x: 0.0
    offset_y: 0.0
    depth: 0.0
    measurement_height: 0.0
    force_threshold: -50
    sensor_channels: [1]
```

### 4. Protocol (`configs/protocol/*.yaml`)

Defines the experiment as a sequence of commands. Positions reference labware by key and well ID (e.g. `plate_1.A1`).

```yaml
positions:
  safe_z: [0.0, 0.0, -50.0]

protocol:
  # Home the gantry and zero coordinates
  - home:

  # Scan all wells: move to each well, run indentation
  - scan:
      plate: plate
      instrument: asmi
      method: indentation
      method_kwargs:
        z_limit: -83.0
        step_size: 0.01
        force_limit: 10.0
        measurement_height: -73.0
        baseline_samples: 10

  # Return to safe Z after scan
  - move:
      instrument: asmi
      position: safe_z

  # Home the gantry
  - home:
```

Available protocol commands:

| Command | Description |
|---------|-------------|
| `move` | Move an instrument to a deck position |
| `scan` | Iterate all wells on a plate, calling an instrument method per well |
| `measure` | Single measurement with an instrument |
| `pick_up_tip` | Pipette: pick up a tip |
| `aspirate` | Pipette: draw liquid |
| `dispense` | Pipette: deliver liquid |
| `transfer` | Pipette: combined move + aspirate + move + dispense |
| `serial_transfer` | Pipette: sequential transfers across positions |
| `mix` | Pipette: aspirate/dispense repeatedly |
| `blowout` | Pipette: blow out remaining liquid |
| `drop_tip` | Pipette: drop the tip |
| `home` | Home the gantry |
| `pause` | Pause execution for N seconds |
| `breakpoint` | Debug pause with user prompt |

## Supported Instruments

All instruments have real drivers and mock variants for offline testing.

| Instrument | Type Key | Vendor | Description |
|------------|----------|--------|-------------|
| Thorlabs CCS UV-Vis Spectrometer | `uvvis_ccs` | thorlabs | UV-Vis spectroscopy |
| Opentrons Pipette | `pipette` | opentrons | Liquid handling |
| ASMI Force Sensor | `asmi` | vernier | Force measurement |
| Filmetrics | `filmetrics` | kla | Thin-film thickness measurement |
| Excelitas OmniCure | `uv_curing` | excelitas | UV curing |

## Installation

```bash
git clone https://github.com/Hydra-Laboratories/PANDA_CORE.git
cd PANDA_CORE
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Hello World

### 1. Interactive jog test

Connect the CNC gantry via USB, then:

```bash
python setup/hello_world.py
```

This homes the gantry and drops into an interactive jog mode (arrow keys for XY, Z/X keys for Z).

### 2. Validate a setup

```bash
python setup/validate_setup.py \
    configs/gantry/asmi_gantry.yaml \
    configs/deck/asmi_deck.yaml \
    configs/board/asmi_board.yaml \
    configs/protocol/asmi_indentation.yaml
```

Loads all four configs, checks that every labware position and instrument-adjusted position is within the gantry working volume, and prints PASS/FAIL.

### 3. Run a protocol

```bash
python setup/run_protocol.py \
    configs/gantry/asmi_gantry.yaml \
    configs/deck/asmi_deck.yaml \
    configs/board/asmi_board.yaml \
    configs/protocol/asmi_indentation.yaml
```

Validates offline first, then connects to the gantry and executes the protocol.

### Programmatic API

```python
from src.protocol_engine.setup import setup_protocol

protocol, context = setup_protocol(
    gantry_path="configs/gantry/asmi_gantry.yaml",
    deck_path="configs/deck/asmi_deck.yaml",
    board_path="configs/board/asmi_board.yaml",
    protocol_path="configs/protocol/asmi_indentation.yaml",
)
protocol.run(context)
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/
```
