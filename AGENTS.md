# CNC Project Documentation for Agents

This repository contains code to control a CNC router (mill) using a Python-based driver that communicates over serial (GRBL).

## Key Components

### Source Code (`src/cnc_control`)
- **`driver.py`**: Contains the `Mill` class, which is the main interface for controlling the CNC machine.
    - **Usage**: Use `with Mill() as mill:` to connect.
    - **Methods**: `mill.move_to_position(x, y, z)`, `mill.home()`, `mill.current_coordinates()`.
- **`tools.py`**: Defines `Coordinates`, `ToolManager`, and `Instruments`. Handles tool offsets.
- **`mock.py`**: Contains `MockMill` for offline testing.

### Testing
- **`test_cnc_move.py`**: A sample script to move the CNC mill 1mm in the X direction.
    - **Run with**: `python3 test_cnc_move.py` (requires CNC connection)
- **`tests/verify_cnc_move.py`**: Verifies logic of the move script using mocks.

## Usage Guide for Agents

1.  **Connecting**: Always use the context manager `with Mill() as mill:` to ensure proper connection and cleanup.
2.  **Moving**: Use `mill.move_to_position(x, y, z)` for safe moves. The driver handles validation against the working volume (negative coordinates mostly).
    - **Coordinates**: The machine typically operates in negative space relative to Home (0,0,0). e.g., X goes from 0 to -415.
3.  **Offsets**: Tools have offsets managed by `ToolManager`.

### Instruments (`src/instruments`)
Base classes and instrument drivers for lab equipment.

- **`base_instrument.py`**: `BaseInstrument` abstract class and `InstrumentError`. All instrument drivers inherit from this.
- **`__init__.py`**: Exports `BaseInstrument`, `InstrumentError`.

#### Filmetrics (`src/instruments/filmetrics`)
Driver for the Filmetrics film thickness measurement system. Communicates with a C# console app (`FilmetricsTool.exe`) via stdin/stdout text commands.

- **`driver.py`**: `Filmetrics(BaseInstrument)` — the real driver.
    - **Constructor**: `Filmetrics(exe_path, recipe_name, command_timeout=30.0, name=None)`
    - **Lifecycle**: `connect()`, `disconnect()`, `health_check()`
    - **Commands**: `acquire_sample()`, `acquire_reference(ref)`, `acquire_background()`, `commit_baseline()`, `measure() -> MeasurementResult`, `save_spectrum(id)`
- **`mock.py`**: `MockFilmetrics` — in-memory mock for testing. Tracks `command_history: list[str]`.
- **`models.py`**: `MeasurementResult` frozen dataclass (`thickness_nm`, `goodness_of_fit`, `is_valid`).
- **`exceptions.py`**: `FilmetricsError` hierarchy (`FilmetricsConnectionError`, `FilmetricsCommandError`, `FilmetricsParseError`).
- **`reference/`**: Copy of the C# source (`FilmetricsTool_program.cs`) for protocol reference.

#### UV-Vis CCS Spectrometer (`src/instruments/uvvis_ccs`)
Driver for the Thorlabs CCS-series compact spectrometers (CCS100/CCS175/CCS200). Communicates with the instrument via the Thorlabs TLCCS DLL through ctypes. 3648-pixel linear CCD.

- **`driver.py`**: `UVVisCCS(BaseInstrument)` — the real DLL-based driver.
    - **Constructor**: `UVVisCCS(serial_number, dll_path="TLCCS_64.dll", default_integration_time_s=0.24, name=None)`
    - **Lifecycle**: `connect()`, `disconnect()`, `health_check()`
    - **Commands**: `set_integration_time(seconds)`, `get_integration_time()`, `measure() -> UVVisSpectrum`, `get_device_info()`
- **`mock.py`**: `MockUVVisCCS` — in-memory mock for testing. Tracks `command_history: list[str]`.
- **`models.py`**: `UVVisSpectrum` frozen dataclass (`wavelengths`, `intensities`, `integration_time_s`, `is_valid`, `num_pixels`). `NUM_PIXELS = 3648`.
- **`exceptions.py`**: `UVVisCCSError` hierarchy (`UVVisCCSConnectionError`, `UVVisCCSMeasurementError`, `UVVisCCSTimeoutError`).

### Protocol Engine (`src/protocol_engine`)
A modular system for executing experiment sequences defined in code or YAML.

- **`schema.py`**: Pydantic models acting as the "Source of Truth" for valid actions (`MoveAction`, `ImageAction`) and sequences. Supports loading from YAML.
    - **Usage**: `ExperimentSequence.from_yaml("path/to/experiment.yaml")`
- **`config.py`**: `DeckConfig` class managing machine bounds, safe heights, and hardware settings (Config Loading).
    - **Config File**: `configs/genmitsu_3018_deck_config.yaml`
- **`path_planner.py`**: Generates safe, optimized `PathPlan`s between waypoints.
    - **Strategies**: 
        - Naive (Lift -> Travel -> Lower)
        - Optimized (Skip lift if safe, travel at start Z if safe)
- **`compiler.py`**: Converts high-level `ExperimentSequence` into granular hardware `ProtocolSteps`.
- **`camera.py`**: `Camera` class wrapping OpenCV for robust image capture (handles warmup, retries).
- **`executor.py`**: `ProtocolExecutor` that orchestrates the `Mill` and `Camera` to run the compiled protocol.

### Experiments
- **`experiments/`**: Directory for storing YAML experiment definitions.
- **`verify_experiment.py`**: Main runner script. Loads an experiment (YAML), compiles it, and executes it on the hardware.
    - **Usage**: `python verify_experiment.py [experiment_file.yaml]`

## Usage Guide for Agents

1.  **Defining Experiments**: Create a YAML file in `experiments/` defining the sequence of moves and images.
2.  **Running**: Execute `python verify_experiment.py experiments/your_experiment.yaml`.
3.  **Connecting**: The system handles connection details (port, camera source) via `configs/genmitsu_3018_deck_config.yaml`.

## Environment
- **Python**: 3.x
- **Dependencies**: `pyserial`, `opencv-python`, `pydantic`, `pyyaml`.
