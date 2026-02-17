# CNC Control Project

A standalone project for controlling a GRBL CNC mill.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Experiment Protocol Engine

This project features a robust **Protocol Engine** for defining and executing automated experiments on the CNC mill.

### Key Features
- **YAML-based Protocols**: Define experiments in simple YAML files (see `experiments/`).
- **Safe Path Planning**: Automatic "Safe Z" travel and optimization to prevent collisions.
- **Hardware Abstraction**: Clean separation between protocol logic and hardware drivers.
- **Labware Abstractions**: Centralized models for well plates and vials, making it easy to target logical positions (e.g., `A1`) and resolve them into absolute deck coordinates.

### Running an Experiment
1. **Configure Hardware**: Update `configs/genmitsu_3018_deck_config.yaml` with your machine bounds, camera source, and serial port.
2. **Define Experiment**: Create a YAML file in `experiments/` (e.g., `experiments/my_experiment.yaml`).
3. **Run**:
   ```bash
   python verify_experiment.py experiments/my_experiment.yaml
   ```

## Config Directory Structure

Config files are organized into subdirectories by type:

```
configs/
  machines/     # Machine configs (serial port, homing, working volume)
  decks/        # Deck configs (labware positions)
  boards/       # Board configs (instrument offsets)
  protocols/    # Protocol configs (command sequences)
```

## Machine Config

Machine YAML defines the CNC machine's working volume bounds, serial port, and homing strategy. Load with:

```python
from src.machine import load_machine_from_yaml

machine = load_machine_from_yaml("configs/machines/genmitsu_3018_PROver_v2.yaml")
# machine.working_volume.x_min, machine.working_volume.x_max, etc.
# machine.homing_strategy, machine.serial_port
```

See `configs/machines/genmitsu_3018_PROver_v2.yaml` for the required schema.

## Labware Models and Deck YAML

Logical labware (well plates and vials) is modeled in `src/deck/labware/`:

- `Labware` is a high-level base for shared behavior (`get_location`, `get_initial_position`) and common validation helpers.
- `WellPlate` defines all required plate fields directly: `name`, `model_name`, geometry (`length_mm`, `width_mm`, `height_mm`), layout (`rows`, `columns`), `wells`, and volume fields (`capacity_ul`, `working_volume_ul`).
- `Vial` defines all required vial fields directly: `name`, `model_name`, geometry (`height_mm`, `diameter_mm`), a single `location`, and volume fields.

**Deck configuration (YAML)** defines which labware is on the deck (no gantry/serial settings in the deck file). Use a strict deck YAML with a single top-level key `labware`; each entry is either a well plate (with two-point calibration A1 + A2 and x/y offsets) or a single vial (with explicit `location`). Load into Python objects with:

```python
from src.deck import load_deck_from_yaml

deck = load_deck_from_yaml("configs/decks/deck.sample.yaml")
# deck["plate_1"] -> WellPlate; deck["vial_1"] -> Vial
# deck.resolve("plate_1.A1")  # absolute XYZ coordinate
```

See `configs/decks/deck.sample.yaml` for the required schema. Validation is strict: missing, extra, or wrong-type fields raise `ValidationError`; two-point calibration for well plates must be axis-aligned (A1 and A2 share either x or y).

## Instrument Drivers

Lab instruments are implemented as `BaseInstrument` subclasses in `src/instruments/`.

### Filmetrics Film Thickness

Driver for the Filmetrics measurement system (`src/instruments/filmetrics/`). Communicates with a C# console app via stdin/stdout.

```python
from src.instruments.filmetrics import Filmetrics, MockFilmetrics

# Real hardware
fm = Filmetrics(exe_path="path/to/FilmetricsTool.exe", recipe_name="MyRecipe")
fm.connect()
result = fm.measure()
print(result.thickness_nm, result.goodness_of_fit, result.is_valid)
fm.disconnect()

# Testing
mock = MockFilmetrics()
mock.connect()
mock.measure()
print(mock.command_history)  # ['measure']
```

### Thorlabs CCS UV-Vis Spectrometer

Driver for Thorlabs CCS100/CCS175/CCS200 compact spectrometers (`src/instruments/uvvis_ccs/`). Communicates via the TLCCS DLL through ctypes.

```python
from src.instruments.uvvis_ccs import UVVisCCS, MockUVVisCCS

# Real hardware (requires TLCCS_64.dll and USB-connected spectrometer)
ccs = UVVisCCS(serial_number="M01216839", dll_path="TLCCS_64.dll")
ccs.connect()
ccs.set_integration_time(0.24)
spectrum = ccs.measure()
print(spectrum.wavelengths, spectrum.intensities, spectrum.is_valid)
ccs.disconnect()

# Testing
mock = MockUVVisCCS()
mock.connect()
mock.measure()
print(mock.command_history)  # ['measure']
```

## Protocol Setup and Validation

The `setup_protocol()` function loads all four configs, validates that all deck positions and gantry-computed positions are within the machine's working volume, and returns a ready-to-run `Protocol` + `ProtocolContext`:

```python
from src.protocol_engine.setup import setup_protocol

protocol, context = setup_protocol(
    machine_path="configs/machines/genmitsu_3018_PROver_v2.yaml",
    deck_path="configs/decks/mofcat_deck.yaml",
    board_path="configs/boards/mofcat_board.yaml",
    protocol_path="configs/protocols/protocol.sample.yaml",
)
# Protocol is ready to run once validation passes:
protocol.run(context)
```

Validation checks:
- All labware positions (every well, every vial) are within machine working volume
- For every (instrument, position) pair, the computed gantry position is within bounds
- Raises `SetupValidationError` with all violations listed if any checks fail

### Validate Setup (CLI)

Run validation from the command line to see human-readable output:

```bash
python setup/validate_setup.py \
    configs/machines/genmitsu_3018_PROver_v2.yaml \
    configs/decks/mofcat_deck.yaml \
    configs/boards/mofcat_board.yaml \
    configs/protocols/protocol.sample.yaml
```

The script prints step-by-step output: each config loaded with details (machine bounds, labware list, instruments, protocol steps), followed by deck and gantry bounds validation results, and a final PASS/FAIL summary.

## Development

Run unit tests:
```bash
pytest tests/
```
