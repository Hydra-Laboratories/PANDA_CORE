# PANDA Core

PANDA Core is a lab automation software package for running self-driving experiments via a modified, off-the-shelf CNC gantry. 

## Configuration

Four YAML files fully specify a running experiment:

### 1. Gantry (`configs/gantry/*.yaml`)

Defines the CNC hardware: serial port, homing strategy, working volume bounds, and GRBL board settings.

```yaml
serial_port: /dev/cu.usbserial-140
cnc:
  homing_strategy: xy_hard_limits

working_volume:
  x_min: 0.0
  x_max: 300.0
  y_min: 0.0
  y_max: 200.0
  z_min: 0.0
  z_max: 80.0

grbl_settings:
  dir_invert_mask: 2
  status_report: 0
  hard_limits: true
  homing_enable: true
  homing_dir_mask: 3
  homing_pull_off: 2.0
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
  plate_1:
    type: well_plate
    name: opentrons_96_well_20ml
    model_name: opentrons_96_well_20ml
    rows: 8
    columns: 12
    length_mm: 127.71
    width_mm: 85.43
    height_mm: 14.10
    calibration:
      a1: { x: -10.0, y: -10.0, z: -15.0 }
      a2: { x: -10.0, y: -19.0, z: -15.0 }
    x_offset_mm: 9.0
    y_offset_mm: -9.0
    capacity_ul: 200.0
    working_volume_ul: 150.0

  vial_1:
    type: vial
    name: standard_vial
    model_name: standard_1_5ml_vial
    height_mm: 66.75
    diameter_mm: 28.0
    location: { x: -30.0, y: -40.0, z: -20.0 }
    capacity_ul: 1500.0
    working_volume_ul: 1200.0
```

### 3. Board (`configs/board/*.yaml`)

Defines instruments mounted on the gantry head — their type, vendor, hardware-specific config, and XYZ offsets from the head reference point.

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

### 4. Protocol (`configs/protocol/*.yaml`)

Defines the experiment as a sequence of commands. Positions reference labware by key and well ID (e.g. `plate_1.A1`).

```yaml
protocol:
  - move:
      instrument: uvvis
      position: plate_1.A1

  - pick_up_tip:
      position: tiprack_1.A1

  - aspirate:
      position: plate_1.A1
      volume_ul: 100.0
      speed: 50.0

  - dispense:
      position: plate_1.B1
      volume_ul: 100.0

  - mix:
      position: plate_1.B1
      volume_ul: 50.0
      repetitions: 3
      speed: 50.0

  - blowout:
      position: plate_1.B1

  - drop_tip:
      position: waste_1

  - scan:
      plate: plate_1
      instrument: uvvis
      method: measure
```

Available protocol commands:

| Command | Description |
|---------|-------------|
| `move` | Move an instrument to a deck position |
| `pick_up_tip` | Pipette: pick up a tip |
| `aspirate` | Pipette: draw liquid |
| `dispense` | Pipette: deliver liquid |
| `transfer` | Combined move + aspirate + move + dispense |
| `serial_transfer` | Sequential transfers across positions |
| `mix` | Pipette: aspirate/dispense repeatedly |
| `blowout` | Pipette: blow out remaining liquid |
| `drop_tip` | Pipette: drop the tip |
| `scan` | Iterate all wells on a plate, calling an instrument method per well |
| `measure` | Single measurement with an instrument |
| `home` | Home the gantry |
| `pause` | Pause execution for N seconds |
| `breakpoint` | Debug pause with user prompt |

## Supported Instruments

All instruments have real drivers and mock variants for offline testing.

| Instrument | Type Key | Vendor | Description |
|------------|----------|--------|-------------|
| Thorlabs CCS UV-Vis Spectrometer | `uvvis_ccs` | thorlabs | CCS100/CCS175/CCS200 compact spectrometer (3648-pixel CCD) via TLCCS DLL |
| Opentrons Pipette | `pipette` | opentrons | OT-2/Flex pipette via Arduino serial (Pawduino firmware) |
| ASMI Force Sensor | `asmi` | vernier | Force measurement via GoDirect USB SDK |
| Filmetrics Film Thickness | `filmetrics` | kla | Thin-film thickness measurement via C# console app (FilmetricsTool.exe) |
| Excelitas UV Curing | `uv_curing` | excelitas | OmniCure S1500 PRO UV light control via RS-232 serial |

## Installation

```bash
git clone <repo-url>
cd PANDA_CORE
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Hello World

### 1. Interactive jog test (hardware required)

Connect the CNC gantry via USB, then:

```bash
python setup/hello_world.py
```

This homes the gantry and drops into an interactive jog mode (arrow keys for XY, Z/X keys for Z).

### 2. Validate a setup (no hardware required)

```bash
python setup/validate_setup.py \
    configs/gantry/genmitsu_3018_PROver_v2.yaml \
    configs/deck/deck.sample.yaml \
    configs/board/mofcat_board.yaml \
    configs/protocol/protocol.sample.yaml
```

Loads all four configs, checks that every labware position and instrument-adjusted position is within the gantry working volume, and prints PASS/FAIL.

### 3. Run a protocol (hardware required)

```bash
python setup/run_protocol.py \
    configs/gantry/genmitsu_3018_PROver_v2.yaml \
    configs/deck/mofcat_deck.yaml \
    configs/board/mofcat_board.yaml \
    configs/protocol/protocol.sample.yaml
```

Validates offline first, then connects to the gantry and executes the protocol.

### Programmatic API

```python
from src.protocol_engine.setup import setup_protocol

protocol, context = setup_protocol(
    gantry_path="configs/gantry/genmitsu_3018_PROver_v2.yaml",
    deck_path="configs/deck/deck.sample.yaml",
    board_path="configs/board/mofcat_board.yaml",
    protocol_path="configs/protocol/protocol.sample.yaml",
)
protocol.run(context)
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/
```
