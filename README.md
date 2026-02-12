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

### Running an Experiment
1. **Configure Hardware**: Update `configs/genmitsu_3018_deck_config.yaml` with your machine bounds, camera source, and serial port.
2. **Define Experiment**: Create a YAML file in `experiments/` (e.g., `experiments/my_experiment.yaml`).
3. **Run**:
   ```bash
   python verify_experiment.py experiments/my_experiment.yaml
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

## Development

Run unit tests:
```bash
pytest tests/
```
