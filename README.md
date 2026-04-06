# PANDA Core

Python control and experiment orchestration for the PANDA CNC-based lab platform. The repository combines:

- Gantry control for GRBL-based CNC hardware
- Instrument drivers for UV-Vis, Filmetrics, and pipettes
- A YAML-driven protocol engine for experiment execution
- Validation utilities that check deck positions and instrument reachability before hardware moves

## Prerequisites

### Software

- Python 3.9 or newer
- `pip`
- A virtual environment tool such as `venv`

### Hardware and vendor dependencies

Some parts of the repo run fully offline, but real hardware workflows need the matching device dependencies:

- GRBL-compatible CNC gantry reachable over serial
- Thorlabs TLCCS driver DLL for `uvvis_ccs` instruments
- Filmetrics console executable for the Filmetrics driver
- Attached serial device for the pipette driver when using real pipette hardware

If you only want to validate configs or run tests, you do not need the physical hardware connected.

## Install

Create a virtual environment and install the project:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

For test tooling:

```bash
pip install -r requirements.txt
```

## Repository Layout

The main configuration and runtime surfaces are:

```text
configs/
  gantry/     # Gantry geometry, serial port, homing, GRBL settings
  deck/       # Labware placement and calibration points
  board/      # Instruments and offsets mounted on the gantry
  protocol/   # YAML protocol steps

setup/
  hello_world.py      # Interactive gantry jog test
  validate_setup.py   # Offline config + bounds validation
  run_protocol.py     # Validate, connect to gantry, and execute a protocol

src/
  gantry/             # Gantry models and driver
  deck/               # Deck and labware loaders
  board/              # Instrument-board loader
  protocol_engine/    # Protocol loader, registry, commands, setup
  instruments/        # Instrument drivers and mocks
  validation/         # Bounds validation
```

## How To Run The Repo

### 1. Validate a setup offline

This is the safest first step. It loads all four YAML files and checks:

- The deck positions are inside the gantry working volume
- The gantry positions derived from instrument offsets are still reachable
- The protocol loads with valid commands and arguments

```bash
python setup/validate_setup.py \
  configs/gantry/genmitsu_3018_PROver_v2.yaml \
  configs/deck/mofcat_deck.yaml \
  configs/board/mofcat_board.yaml \
  configs/protocol/scan.yaml
```

### 2. Run a protocol on hardware

Once validation passes, execute the same four-file setup against the real gantry:

```bash
python setup/run_protocol.py \
  configs/gantry/genmitsu_3018_PROver_v2.yaml \
  configs/deck/mofcat_deck.yaml \
  configs/board/mofcat_board.yaml \
  configs/protocol/scan.yaml
```

`setup/run_protocol.py` performs validation first, then connects to the gantry and runs the protocol.

### 3. Jog the gantry interactively

For first-run hardware bring-up:

```bash
python3 setup/hello_world.py
```

That script lets you choose a gantry config, home the machine, and jog it with the keyboard.

### 4. Run tests

```bash
pytest tests/ -v
```

## Experiment Setup From YAML

An experiment in this repo is assembled from four YAML files:

1. A gantry config describing the machine envelope and serial settings
2. A deck config describing where labware lives on the machine
3. A board config describing which instruments are mounted and what their offsets are
4. A protocol config describing the step-by-step experiment

### Gantry Example

`configs/gantry/genmitsu_3018_PROver_v2.yaml` defines the working volume and GRBL settings:

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
```

This file is the source of truth for the allowed motion envelope.

### Deck Example

`configs/deck/mofcat_deck.yaml` places a 96-well plate on the deck:

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

Key points:

- `plate_1` is the lookup key used later in protocol positions such as `plate_1.A1`
- `a1` and `a2` anchor the plate in machine coordinates
- The loader derives the rest of the well coordinates from the plate geometry and offsets

`configs/deck/deck.sample.yaml` shows a broader example with both a well plate and a standalone vial.

### Board Example

`configs/board/mofcat_board.yaml` mounts a UV-Vis spectrometer on the gantry:

```yaml
instruments:
  uvvis:
    type: uvvis_ccs
    serial_number: "M00801544"
    dll_path: "TLCCS_64.dll"
    default_integration_time_s: 0.24
    offset_x: 0.0
    offset_y: 0.0
    depth: 0.0
    measurement_height: 3.0
```

The instrument key `uvvis` is what the protocol refers to in move and scan steps.

### Protocol Examples

#### Minimal move protocol

`configs/protocol/move.yaml` moves the `uvvis` instrument to well `A1`:

```yaml
protocol:
  - move:
      instrument: uvvis
      position: plate_1.A1
```

#### Scan protocol

`configs/protocol/scan.yaml` first moves, then measures the whole plate using the `scan` command:

```yaml
protocol:
  - move:
      instrument: uvvis
      position: plate_1.A1

  - scan:
      plate: plate_1
      instrument: uvvis
      method: measure
```

This is a good starting point for a real experiment because it demonstrates the full link:

- `plate_1` comes from the deck YAML
- `uvvis` comes from the board YAML
- Reachability is validated against the gantry YAML before execution

## Example End-To-End Workflow

To run the checked-in MOFcat example:

```bash
python setup/validate_setup.py \
  configs/gantry/genmitsu_3018_PROver_v2.yaml \
  configs/deck/mofcat_deck.yaml \
  configs/board/mofcat_board.yaml \
  configs/protocol/scan.yaml
```

If that passes, run:

```bash
python setup/run_protocol.py \
  configs/gantry/genmitsu_3018_PROver_v2.yaml \
  configs/deck/mofcat_deck.yaml \
  configs/board/mofcat_board.yaml \
  configs/protocol/scan.yaml
```

To build your own experiment, copy one file from each config directory and keep the references aligned:

- Deck labware names must match protocol position targets
- Board instrument names must match protocol instrument names
- Gantry bounds must contain every deck position and every instrument-adjusted target

## Programmatic Usage

For Python-driven execution with managed instrument connection and cleanup:

```python
from protocol_engine.setup import run_protocol

results = run_protocol(
    "configs/gantry/genmitsu_3018_PROver_v2.yaml",
    "configs/deck/mofcat_deck.yaml",
    "configs/board/mofcat_board.yaml",
    "configs/protocol/scan.yaml",
)
```

Use `setup_protocol(...)` when you want to load and validate the configuration without executing it yet. Use `run_protocol(...)` or `setup/run_protocol.py` when you want the repo to manage execution lifecycle end to end.
