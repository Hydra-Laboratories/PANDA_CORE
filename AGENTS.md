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

- **`protocol.py`**: `Protocol`, `ProtocolStep`, and `ProtocolContext` classes. `ProtocolContext` provides `board`, `deck`, and optionally `machine` to command handlers.
- **`yaml_schema.py`**: Pydantic schemas for protocol YAML (step validation against registered commands).
- **`loader.py`**: `load_protocol_from_yaml(path)` and `_safe` variant.
- **`registry.py`**: `CommandRegistry` singleton and `@protocol_command()` decorator for registering commands.
- **`setup.py`**: `setup_protocol(machine_path, deck_path, board_path, protocol_path)` — loads all configs, validates bounds, and returns `(Protocol, ProtocolContext)` ready to run. Uses a mock gantry by default for offline validation.
- **`commands/`**: Protocol command implementations (`move.py`, `pipette.py`, `scan.py`).

### Machine Config (`src/machine`)
Machine YAML loader and domain model for CNC machine working volume and homing strategy.

- **`yaml_schema.py`**: `MachineYamlSchema` with strict Pydantic validation (working volume bounds, homing strategy, serial port).
- **`machine_config.py`**: `MachineConfig` and `WorkingVolume` frozen dataclasses. `WorkingVolume.contains(x, y, z)` checks if a point is within bounds (inclusive).
- **`loader.py`**: `load_machine_from_yaml(path)` and `load_machine_from_yaml_safe(path)`.
- **Config files**: `configs/machines/` (e.g., `genmitsu_3018_PROver_v2.yaml`).

### Validation (`src/validation`)
Bounds validation for protocol setup — ensures all deck positions and gantry-computed positions are within the machine's working volume before the protocol runs.

- **`bounds.py`**: `validate_deck_positions(machine, deck)` and `validate_gantry_positions(machine, deck, board)`. Returns lists of `BoundsViolation` objects. Gantry formula: `gantry_pos = deck_pos - instrument_offset`.
- **`errors.py`**: `BoundsViolation` dataclass and `SetupValidationError` exception with all violations listed.

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
- **Sample config**: `configs/decks/deck.sample.yaml` — one well plate and one vial; use as reference for required fields and two-point calibration format.
- **Usage**: Load a deck with `load_deck_from_yaml("configs/decks/deck.sample.yaml")` to get a `Deck` object. Access labware: `deck["plate_1"]`. Resolve targets: `deck.resolve("plate_1.A1")` for absolute XYZ.

### Config Directory Structure
Config files are organized by type:
```
configs/
  machines/     # Machine configs (serial port, homing, working volume)
  decks/        # Deck configs (labware positions)
  boards/       # Board configs (instrument offsets)
  protocols/    # Protocol configs (command sequences)
```

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
- **`validate_setup.py`**: Validate a protocol setup by loading all 4 configs (machine, deck, board, protocol) and checking that all deck and gantry positions are within the machine's working volume.
    - **Usage**: `python setup/validate_setup.py <machine.yaml> <deck.yaml> <board.yaml> <protocol.yaml>`
    - **Output**: Step-by-step loading status, labware/instrument summaries, bounds validation results, and a final PASS/FAIL verdict.
    - **Dependencies**: `src/machine`, `src/deck`, `src/board`, `src/protocol_engine`, `src/validation`
- **`keyboard_input.py`**: Helper module that reads single keypresses (including arrow keys) without requiring Enter. Uses `tty`/`termios` (Unix only).

## Environment
- **Python**: 3.x
- **Dependencies**: `pyserial`, `opencv-python`, `pydantic`, `pyyaml`.
