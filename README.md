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

## Labware Models and Deck YAML

Logical labware (well plates and vials) is modeled in `src/labware/`:

- `Labware` is a high-level base for shared behavior (`get_location`, `get_initial_position`) and common validation helpers.
- `WellPlate` defines all required plate fields directly: `name`, `model_name`, geometry (`length_mm`, `width_mm`, `height_mm`), layout (`rows`, `columns`), `wells`, and volume fields (`capacity_ul`, `working_volume_ul`).
- `Vial` defines all required vial fields directly: `name`, `model_name`, geometry (`height_mm`, `diameter_mm`), a single `location`, and volume fields.

**Deck configuration (YAML)** defines which labware is on the deck (no gantry/serial settings in the deck file). Use a strict deck YAML with a single top-level key `labware`; each entry is either a well plate (with two-point calibration A1 + A2 and x/y offsets) or a single vial (with explicit `location`). Load into Python objects with:

```python
from src.labware.deck_loader import load_labware_from_deck_yaml

labware = load_labware_from_deck_yaml("configs/deck.sample.yaml")
# labware["plate_1"] -> WellPlate; labware["vial_1"] -> Vial
# labware["plate_1"].get_well_center("A1")  # absolute XYZ
```

See `configs/deck.sample.yaml` for the required schema. Validation is strict: missing, extra, or wrong-type fields raise `ValidationError`; two-point calibration for well plates must be axis-aligned (A1 and A2 share either x or y).

To quickly inspect loaded objects from the sample deck YAML, run:

```bash
python show_deck_objects.py
```

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
