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

#### UV-Vis CCS Spectrometer (`src/instruments/uvvis_ccs`)
Driver for the Thorlabs CCS-series compact spectrometers (CCS100/CCS175/CCS200). Communicates with the instrument via the Thorlabs TLCCS DLL through ctypes. 3648-pixel linear CCD.

- **`driver.py`**: `UVVisCCS(BaseInstrument)` — the real DLL-based driver.
    - **Constructor**: `UVVisCCS(serial_number, dll_path="TLCCS_64.dll", default_integration_time_s=0.24, name=None)`
    - **Lifecycle**: `connect()`, `disconnect()`, `health_check()`
    - **Commands**: `set_integration_time(seconds)`, `get_integration_time()`, `measure() -> UVVisSpectrum`, `get_device_info()`
- **`mock.py`**: `MockUVVisCCS` — in-memory mock for testing. Tracks `command_history: list[str]`.
- **`models.py`**: `UVVisSpectrum` frozen dataclass (`wavelengths`, `intensities`, `integration_time_s`, `is_valid`, `num_pixels`). `NUM_PIXELS = 3648`.
- **`exceptions.py`**: `UVVisCCSError` hierarchy (`UVVisCCSConnectionError`, `UVVisCCSMeasurementError`, `UVVisCCSTimeoutError`).

#### Pipette (`src/instruments/pipette`)
Driver for Opentrons OT-2 and Flex pipettes. Communicates with the pipette motor via Arduino serial (Pawduino firmware). Supports 10 pipette models; the P300 single-channel has real calibrated values from PANDA-BEAR.

- **`driver.py`**: `Pipette(BaseInstrument)` — the real serial driver.
    - **Constructor**: `Pipette(pipette_model, port, baud_rate=115200, command_timeout=30.0, name=None)`
    - **Lifecycle**: `connect()`, `disconnect()`, `health_check()`, `warm_up()` (homes + primes)
    - **Commands**: `home()`, `prime(speed)`, `aspirate(volume_ul, speed)`, `dispense(volume_ul, speed)`, `blowout(speed)`, `mix(volume_ul, reps, speed)`, `pick_up_tip(speed)`, `drop_tip(speed)`, `get_status() -> PipetteStatus`, `drip_stop(volume_ul, speed)`
- **`mock.py`**: `MockPipette` — in-memory mock for testing. Tracks `command_history: list[str]`.
- **`models.py`**: `PipetteConfig` (frozen, per-model hardware description), `PipetteStatus`, `AspirateResult`, `MixResult` (all frozen dataclasses). `PIPETTE_MODELS` registry dict. `PipetteFamily` enum (OT2/FLEX).
- **`exceptions.py`**: `PipetteError` hierarchy (`PipetteConnectionError`, `PipetteCommandError`, `PipetteTimeoutError`, `PipetteConfigError`).

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

### Deck and Labware (`src/deck`)
Deck configuration loading, runtime deck container, and labware geometry/positioning models.

- **`src/deck/deck.py`**: `Deck` class — runtime container holding labware loaded from deck YAML. Provides dict-like access (`deck["plate_1"]`, `len(deck)`, `"plate_1" in deck`) and `deck.resolve("plate_1.A1")` for target-to-coordinate resolution. The raw labware dict is accessible via `deck.labware`.
- **Labware models** (`src/deck/labware/`):
  - **`labware.py`**: `Coordinate3D` and `Labware` base model. `Labware` provides high-level shared behavior (e.g., `get_location`, `get_initial_position`) and common validation helpers; concrete required fields live in subclasses. All models use strict schema (`extra='forbid'`).
  - **`well_plate.py`**: `WellPlate(Labware)` for multi-well plates (e.g., SBS 96-well). Required fields include `name`, `model_name`, dimensions, layout (`rows`, `columns`), `wells`, and volume fields (`capacity_ul`, `working_volume_ul`). Also provides `get_well_center(well_id)`.
  - **`vial.py`**: `Vial(Labware)` for a single vial. Required fields include `name`, `model_name`, geometry (`height_mm`, `diameter_mm`), single `location`, and volume fields (`capacity_ul`, `working_volume_ul`), plus `get_vial_center()`.
- **Deck configuration (YAML)**: Deck layout is defined in a **deck YAML** file (labware only; no gantry settings). Strict schema: only allowed fields; missing, extra, or wrong-type fields raise `ValidationError`.
  - **`src/deck/yaml_schema.py`**: Pydantic models for deck YAML: `DeckYamlSchema` (root, single key `labware`), `WellPlateYamlEntry` (two-point calibration points under `calibration.a1` and `calibration.a2`, axis-aligned only), `VialYamlEntry` (single vial location). Both require `model_name`. All use `extra='forbid'`.
  - **`src/deck/loader.py`**: `load_deck_from_yaml(path)` loads a deck YAML file and returns a `Deck` containing all labware. Well plates are built from calibration A1/A2 and x/y offsets (derived well positions); vials from a single explicit `location`.
  - **`src/deck/errors.py`**: `DeckLoaderError` for user-facing loader failures.
- **Sample config**: `configs/deck.sample.yaml` — one well plate and one vial; use as reference for required fields and two-point calibration format.
- **Sample inspection script**: `show_deck_objects.py` loads `configs/deck.sample.yaml` and prints the resulting object mapping.
- **Usage**: Load a deck with `load_deck_from_yaml("configs/deck.sample.yaml")` to get a `Deck` object. Access labware: `deck["plate_1"]`. Resolve targets: `deck.resolve("plate_1.A1")` for absolute XYZ.

### Data Persistence (`data/`)
SQLite-backed persistence layer for self-driving lab campaigns. All state lives in the database — Python objects are stateless to survive interrupts/crashes.

- **`data/data_store.py`**: `DataStore` class — owns a SQLite connection and provides the full persistence API.
    - **Constructor**: `DataStore(db_path="data/databases/panda_data.db")` — opens/creates DB and initialises schema. Use `":memory:"` for testing.
    - **Empty template**: `data/databases/panda_data.db` — pre-initialized empty database committed to the repo for schema inspection (`sqlite3 data/databases/panda_data.db ".schema"`).
    - **Context manager**: `with DataStore(...) as store:` for automatic cleanup.
    - **Campaign API**: `create_campaign(description, deck_config=None, board_config=None, gantry_config=None, protocol_config=None) -> int`
    - **Experiment API**: `create_experiment(campaign_id, labware_name, well_id, contents_json=None) -> int`
    - **Measurement API**: `log_measurement(experiment_id, result) -> int` — dispatches by type:
        - `UVVisSpectrum` → `uvvis_measurements` (wavelengths/intensities stored as little-endian BLOB via `struct.pack`)
        - `MeasurementResult` → `filmetrics_measurements` (thickness_nm, goodness_of_fit)
        - `str` (image path) → `camera_measurements`
    - **Labware API** (volume and content tracking, persisted to `labware` table):
        - `register_labware(campaign_id, labware_key, labware)` — registers a Vial (1 row) or WellPlate (1 row per well) with total/working volume from the model.
        - `record_dispense(campaign_id, labware_key, well_id, source_name, volume_ul)` — increments `current_volume_ul` and appends to `contents` JSON.
        - `get_contents(campaign_id, labware_key, well_id) -> list | None` — returns parsed contents list.
    - **Schema tables**: `campaigns`, `experiments`, `uvvis_measurements`, `filmetrics_measurements`, `camera_measurements`, `labware`

#### Protocol Integration
- **`ProtocolContext.data_store`**: Optional `DataStore` instance. When set (along with `campaign_id`), `scan` and `transfer` commands automatically persist measurements and labware state.
- **`ProtocolContext.campaign_id`**: Optional `int`. FK to the `campaigns` table.
- Commands work identically when `data_store` is `None` — no code changes needed for existing protocols.

### Experiments
- **`experiments/`**: Directory for storing YAML experiment definitions.
- **`verify_experiment.py`**: Main runner script. Loads an experiment (YAML), compiles it, and executes it on the hardware.
    - **Usage**: `python verify_experiment.py [experiment_file.yaml]`

## Usage Guide for Agents

1.  **Defining Experiments**: Create a YAML file in `experiments/` defining the sequence of moves and images.
2.  **Running**: Execute `python verify_experiment.py experiments/your_experiment.yaml`.
3.  **Connecting**: The system handles connection details (port, camera source) via `configs/genmitsu_3018_deck_config.yaml`.

### Setup (`setup/`)
First-run scripts for verifying hardware after unboxing.

- **`hello_world.py`**: Interactive jog test. Connects to the gantry (auto-scan, no config), homes the machine, then lets you move the router with arrow keys and see live position updates.
    - **Usage**: `python3 setup/hello_world.py`
    - **Controls**: Arrow keys (X/Y ±1mm), Z key (Z down 1mm), X key (Z up 1mm), Q (quit)
    - **Dependencies**: `src/hardware/gantry.py` (Gantry class)
- **`keyboard_input.py`**: Helper module that reads single keypresses (including arrow keys) without requiring Enter. Uses `tty`/`termios` (Unix only).

## Environment
- **Python**: 3.x
- **Dependencies**: `pyserial`, `opencv-python`, `pydantic`, `pyyaml`.
