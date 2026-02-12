# CNC Project Documentation for Agents

This repository contains code to control a CNC router (mill) using a Python-based driver that communicates over serial (GRBL).

## Key Components

### Source Code (`src/instrument_drivers/cnc_driver`)
- **`driver.py`**: Contains the `Mill` class, which is the main interface for controlling the CNC machine.
    - **Usage**: Use `with Mill() as mill:` to connect.
    - **Methods**: `mill.move_to_position(x, y, z)`, `mill.home()`, `mill.current_coordinates()`.
- **`instruments.py`**: Defines `Coordinates`, `InstrumentManager`, and `Instruments`. Handles instrument offsets.
- **`mock.py`**: Contains `MockMill` for offline testing.

### Testing
- **`test_cnc_move.py`**: A sample script to move the CNC mill 1mm in the X direction.
    - **Run with**: `python3 test_cnc_move.py` (requires CNC connection)
- **`tests/verify_cnc_move.py`**: Verifies logic of the move script using mocks.

## Usage Guide for Agents

1.  **Connecting**: Always use the context manager `with Mill() as mill:` to ensure proper connection and cleanup.
2.  **Moving**: Use `mill.move_to_position(x, y, z)` for safe moves. The driver handles validation against the working volume (negative coordinates mostly).
    - **Coordinates**: The machine typically operates in negative space relative to Home (0,0,0). e.g., X goes from 0 to -415.
3.  **Offsets**: Instruments have offsets managed by `InstrumentManager`.

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

### Labware Models (`src/labware`)
Geometry and positioning models for consumables on the deck.

- **`base.py`**: `Coordinate3D` and `Labware` base model. `Labware` manages a mapping from logical location IDs (e.g., `\"A1\"`) to absolute deck coordinates and exposes `get_location(location_id)`.
- **`well_plate.py`**: `WellPlate(Labware)` for multi-well plates (e.g., SBS 96-well). Stores plate dimensions (length, width, height), grid size (rows/columns), and a `wells` mapping from well ID to center coordinate. Also provides `get_well_center(well_id)`.
- **`vial.py`**: `Vial(Labware)` for vial racks. Stores vial geometry (height, diameter) and a `vials` mapping from vial ID (e.g., `\"A1\"`) to center coordinate, plus `get_vial_center(vial_id)`.
- **Usage**: Higher-level code can resolve targets like `\"A1\"` on a given labware instance into absolute XYZ coordinates, which can then be passed into the path planner or CNC driver.

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
