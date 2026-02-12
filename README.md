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
 - **Labware Abstractions**: Centralized models for well plates and vial racks, making it easy to target logical positions (e.g., `A1`) and resolve them into absolute deck coordinates.

### Running an Experiment
1. **Configure Hardware**: Update `configs/genmitsu_3018_deck_config.yaml` with your machine bounds, camera source, and serial port.
2. **Define Experiment**: Create a YAML file in `experiments/` (e.g., `experiments/my_experiment.yaml`).
3. **Run**:
   ```bash
   python verify_experiment.py experiments/my_experiment.yaml
   ```

## Labware Models

Logical labware (well plates, vial racks, etc.) is modeled in `src/labware/`:

- `Labware` is the common base model that maps logical location IDs (like `A1`) to absolute deck coordinates and provides `get_location(location_id)`.
- `WellPlate` adds plate geometry (length, width, height, rows, columns) and a `wells` mapping, plus `get_well_center(well_id)`.
- `Vial` adds vial geometry (height, diameter) and a `vials` mapping, plus `get_vial_center(vial_id)`.

Future work will connect these models to YAML config so experiment definitions can refer to labware locations directly (e.g., `plate_1.A1`) and the protocol engine will automatically plan safe motion to those coordinates.

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

## Development

Run unit tests:
```bash
pytest tests/
```
