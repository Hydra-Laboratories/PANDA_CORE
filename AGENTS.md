# CNC Project Documentation for Agents

This repository contains code to control a CNC router (mill) using a Python-based driver that communicates over serial (GRBL).

## Key Components

### Source Code (`src/instrument_drivers/cnc_driver`)
- **`driver.py`**: Contains the `Mill` class, which is the main interface for controlling the CNC gantry.
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
    - **Coordinates**: The gantry typically operates in negative space relative to Home (0,0,0). e.g., X goes from 0 to -415.
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

#### ASMI Force Sensor (`src/instruments/asmi`)
Driver for the Vernier GoDirect force sensor used for ASMI indentation/force measurements over USB.

- **`driver.py`**: `ASMI(BaseInstrument)` — real GoDirect driver with `offline=True` support for dry runs.
    - **Constructor**: `ASMI(..., default_force=0.0, force_threshold=-100, z_target=-17.0, step_size=0.01, force_limit=15.0, baseline_samples=10, ...)`
    - **Lifecycle**: `connect()`, `disconnect()`, `health_check()`
    - **Commands**: `measure(n_samples=1)`, `get_status()`, `get_force_reading()`, `get_baseline_force(samples)`, `indentation(gantry, ...)`
- **`models.py`**: `MeasurementResult` and `ASMIStatus` frozen dataclasses.
- **`exceptions.py`**: `ASMIError` hierarchy.

#### UV Curing (`src/instruments/uv_curing`)
Driver for the Excelitas OmniCure S1500 PRO UV curing system over RS-232 serial.

- **`driver.py`**: `UVCuring(BaseInstrument)` — real serial driver with `offline=True` support for dry runs.
    - **Constructor**: `UVCuring(port="/dev/ttyACM0", baud_rate=19200, default_intensity=100.0, default_exposure_time=1.0, name=None, ...)`
    - **Lifecycle**: `connect()`, `disconnect()`, `health_check()`
    - **Commands**: `cure(intensity=None, exposure_time=None)`, `measure(**kwargs)` as a protocol-compatible alias, `get_status()`
- **`models.py`**: `CureResult` and `UVCuringStatus` frozen dataclasses.
- **`exceptions.py`**: `UVCuringError` hierarchy.

#### Pipette (`src/instruments/pipette`)
Driver for Opentrons OT-2 and Flex pipettes. Communicates with the pipette motor via Arduino serial (Pawduino firmware). Supports 10 pipette models; the P300 single-channel has real calibrated values from the BEAR-DEN workcell.

- **`driver.py`**: `Pipette(BaseInstrument)` — the real serial driver.
    - **Constructor**: `Pipette(pipette_model, port, baud_rate=115200, command_timeout=30.0, name=None)`
    - **Lifecycle**: `connect()`, `disconnect()`, `health_check()`, `warm_up()` (homes + primes)
    - **Commands**: `home()`, `prime(speed)`, `aspirate(volume_ul, speed)`, `dispense(volume_ul, speed)`, `blowout(speed)`, `mix(volume_ul, reps, speed)`, `pick_up_tip(speed)`, `drop_tip(speed)`, `get_status() -> PipetteStatus`, `drip_stop(volume_ul, speed)`
- **`mock.py`**: `MockPipette` — in-memory mock for testing. Tracks `command_history: list[str]`.
- **`models.py`**: `PipetteConfig` (frozen, per-model hardware description), `PipetteStatus`, `AspirateResult`, `MixResult` (all frozen dataclasses). `PIPETTE_MODELS` registry dict. `PipetteFamily` enum (OT2/FLEX).
- **`exceptions.py`**: `PipetteError` hierarchy (`PipetteConnectionError`, `PipetteCommandError`, `PipetteTimeoutError`, `PipetteConfigError`).

#### Potentiostat (`src/instruments/potentiostat`)
Driver for Admiral Instruments SquidStat potentiostats via the vendor `SquidstatPyLibrary` (Qt/PySide6 signal-slot API). Wraps the async vendor API in a blocking, synchronous facade matching the rest of the instrument stack: a lazy process-wide `QCoreApplication` plus a per-experiment `QEventLoop`. Vendor SDK is lazy-imported inside `connect()`; the package imports and runs in `offline=True` mode without it.

Install the optional extra to get the vendor SDK and numpy: `pip install -e ".[potentiostat]"`.

- **`driver.py`**: `Potentiostat(BaseInstrument)` — the real driver.
    - **Class attribute**: `vendor = "admiral"` — surfaced on every result so the persistence layer can tag rows.
    - **Constructor**: `Potentiostat(port, channel=0, command_timeout=600.0, name=None, offline=False)`
    - **Lifecycle**: `connect()`, `disconnect()`, `health_check()`
    - **Experiments**: `run_cv(CVParams) -> CVResult`, `run_ocp(OCPParams) -> OCPResult`, `run_ca(CAParams) -> CAResult`, `run_cp(CPParams) -> CPResult`
    - Offline mode returns deterministic synthetic traces (seeded RNG) so downstream code can be exercised without hardware.
- **`models.py`**: frozen param dataclasses (`CVParams`, `OCPParams`, `CAParams`, `CPParams`) with validation in `__post_init__`, and frozen result dataclasses (`OCPResult`, `CAResult`, `CPResult`, `CVResult`) carrying `tuple[float, ...]` traces (`time_s`, `voltage_v`, `current_a`), the requested technique scalars (e.g. `scan_rate_v_s`, `step_potential_v`, `cycles`), a `vendor` field, a `.technique` property, and a free-form `metadata` mapping (`device_id`, `channel`, `started_at`, `stopped_at`, `aborted`, `stop_reason`).
- **`exceptions.py`**: `PotentiostatError` hierarchy (`PotentiostatConnectionError`, `PotentiostatCommandError`, `PotentiostatTimeoutError`, `PotentiostatConfigError`).
- **Persistence**: results flow through `protocol_engine.measurements.normalize_measurement` (which recognises all four result types) into `DataStore.log_measurement`, which writes to the `potentiostat_measurements` table. See the data-layer section for the schema.

### Protocol Engine (`src/protocol_engine`)
A modular system for executing experiment sequences defined in code or YAML.

- **`protocol.py`**: `Protocol`, `ProtocolStep`, and `ProtocolContext` classes. `ProtocolContext` provides `board`, `deck`, and optionally `gantry` config to command handlers.
- **`yaml_schema.py`**: Pydantic schemas for protocol YAML (step validation against registered commands).
- **`loader.py`**: `load_protocol_from_yaml(path)` and `_safe` variant.
- **`registry.py`**: `CommandRegistry` singleton and `@protocol_command()` decorator for registering commands.
- **`setup.py`**: `setup_protocol(gantry_path, deck_path, board_path, protocol_path)` — loads all configs, validates bounds, and returns `(Protocol, ProtocolContext)` ready to run. Uses an offline `Gantry` by default for offline validation.
- **`commands/`**: Protocol command implementations:
  - `home`: home the gantry and zero coordinates.
  - `move`: move an instrument to a named position, raw `[x, y, z]`, or deck target.
  - `scan`: iterate all wells on a plate, call an instrument method per well, and persist measurements when a `DataStore` is configured.
  - `measure`: move to one deck position and call an instrument method once.
  - `pause`: sleep for a fixed number of seconds.
  - `breakpoint`: pause until the user presses Enter.
  - Pipette commands: `aspirate`, `pick_up_tip`, `transfer`, `serial_transfer`, `mix`, `blowout`, `drop_tip`.
  - `dispense` exists as an internal helper only; use `transfer` in YAML so labware state is logged correctly.

### Gantry Config (`src/gantry`)
Gantry YAML loader and domain model for CNC gantry working volume and homing strategy.

- **Coordinate convention**: All user-facing XYZ coordinates are positive-space. The `Gantry` wrapper translates user-space `(+)` coordinates to machine-space `(-)` GRBL coordinates internally.
- **`yaml_schema.py`**: `GantryYamlSchema` with strict Pydantic validation (working volume bounds, homing strategy, serial port, and `cnc.total_z_height`).
- **`gantry_config.py`**: `GantryConfig` and `WorkingVolume` frozen dataclasses. `WorkingVolume.contains(x, y, z)` checks if a point is within bounds (inclusive). `GantryConfig.total_z_height` is the top-reference height used for labware height conversion. `HomingStrategy` enum: `STANDARD`, `XY_HARD_LIMITS`, `MANUAL_ORIGIN`.
- **`loader.py`**: `load_gantry_from_yaml(path)` and `load_gantry_from_yaml_safe(path)`.
- **Config files**: `configs/gantry/` (e.g., `cubos_xl.yaml`).

### Validation (`src/validation`)
Bounds validation for protocol setup — ensures all deck positions and gantry-computed positions are within the gantry's working volume before the protocol runs.

- **`bounds.py`**: `validate_deck_positions(gantry, deck)` and `validate_gantry_positions(gantry, deck, board)`. Returns lists of `BoundsViolation` objects. Gantry formula: `gantry_pos = deck_pos - instrument_offset`.
- **`errors.py`**: `BoundsViolation` dataclass and `SetupValidationError` exception with all violations listed.

### Deck and Labware (`src/deck`)
Deck configuration loading, runtime deck container, and labware geometry/positioning models.

- **`src/deck/deck.py`**: `Deck` class — runtime container holding labware loaded from deck config files. Provides dict-like access (`deck["plate_1"]`, `len(deck)`, `"plate_1" in deck`) and `deck.resolve("plate_1.A1")` for target-to-coordinate resolution. The raw labware dict is accessible via `deck.labware`.
- **Labware models** (`src/deck/labware/`):
  - **`labware.py`**: `Coordinate3D`, `BoundingBoxGeometry`, and `Labware` base model. `Labware` provides high-level shared behavior (e.g., `get_location`, `get_initial_position`) plus shared `geometry` metadata. Current deck models populate `geometry` as a bounding box, even when they also retain convenience fields such as `length_mm` or `diameter_mm`. All models use strict schema (`extra='forbid'`).
  - **`holder.py`**: Shared holder infrastructure. Contains `HolderLabware` and `LabwareSlot`.
  - **`tip_holder.py`**: `TipHolder(HolderLabware)` with the tip-holder bounding-box dimensions.
  - **`tip_disposal.py`**: `TipDisposal(HolderLabware)` with the used-tip disposal bounding-box dimensions.
  - **`well_plate_holder.py`**: `WellPlateHolder(HolderLabware)` with the `SlideHolder_Top` dimensions and seat-height metadata.
  - **`vial_holder.py`**: `VialHolder(HolderLabware)` with the `9VialHolder20mL_TightFit` dimensions, seat-height metadata, and slot-count validation.
  - **`tip_rack.py`**: `TipRack(Labware)` for exact-position pipette pickup targets. Stores a mapping of tip IDs (e.g. `A1`, `B15`) to absolute pickup coordinates plus `z_pickup` and optional `z_drop`.
  - **`well_plate.py`**: `WellPlate(Labware)` for multi-well plates (e.g., SBS 96-well). Required fields include `name`, `model_name`, dimensions, layout (`rows`, `columns`), `wells`, and volume fields (`capacity_ul`, `working_volume_ul`). Also provides `get_well_center(well_id)`.
  - **`vial.py`**: `Vial(Labware)` for a single vial. Required fields include `name`, `model_name`, geometry (`height_mm`, `diameter_mm`), single `location`, and volume fields (`capacity_ul`, `working_volume_ul`), plus `get_vial_center()`.
- **Deck configuration (YAML)**: Deck layout is defined in a deck YAML file (labware only; no gantry settings). Strict schema: only allowed fields; missing, extra, or wrong-type fields raise `ValidationError`.
  - **`src/deck/yaml_schema.py`**: Pydantic models for deck config files: `DeckYamlSchema` (root, single key `labware`), `WellPlateYamlEntry` (two-point calibration points under `calibration.a1` and `calibration.a2`, axis-aligned only), `VialYamlEntry` (single vial location), `TipRackYamlEntry` (explicit tip pickup coordinates), plus holder entries for `tip_holder`, `tip_disposal`, `well_plate_holder`, and `vial_holder`. `VialHolderYamlEntry` can contain nested `vials`, and `WellPlateHolderYamlEntry` can contain a nested `well_plate`; their experiment Z is derived from the holder seat height. All use `extra='forbid'`.
  - **`src/deck/loader.py`**: `load_deck_from_yaml(path, total_z_height=None)` loads a deck YAML config and returns a `Deck` containing all labware. Well plates are built from calibration A1/A2 and x/y offsets (derived well positions); tip racks use explicit pickup coordinates; vials and holders are built from explicit `location` points. Nested holder children inherit their experiment Z from `holder.location.z + holder.labware_seat_height_from_bottom_mm`.
  - **`src/deck/errors.py`**: `DeckLoaderError` for user-facing loader failures.
- **Sample configs**:
  - `configs/deck/deck.sample.yaml` — one well plate and one vial; use as reference for required fields and two-point calibration format.
  - `configs/deck/panda_deck.yaml` — YAML deck config derived from `panda.json`, including two 2x15 tip racks, a nested well plate holder, and a nested vial holder.
- **Usage**: Load a deck with `load_deck_from_yaml("configs/deck/deck.sample.yaml", total_z_height=<float>)` or `load_deck_from_yaml("configs/deck/panda_deck.yaml", total_z_height=<float>)` to get a `Deck` object. Access labware: `deck["plate_1"]`. Resolve targets: `deck.resolve("plate_1.A1")` or nested targets like `deck.resolve("well_plate_holder.plate.A1")` for absolute XYZ.

### Config Directory Structure
Config files are organized by type:
```
configs/
  gantry/       # Gantry configs (serial port, homing, working volume)
  deck/         # Deck configs (labware positions)
  board/        # Board configs (instrument offsets)
  protocol/     # Protocol configs (command sequences)
```

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
        - `InstrumentMeasurement` with potentiostat type → `potentiostat_measurements` (technique, JSON-encoded `time_s`/`voltage_v`/`current_a`, plus per-technique scalars: `sample_period_s`, `duration_s`, `step_potential_v`, `step_current_a`, `scan_rate_v_s`, `step_size_v`, `cycles`; plus `vendor` and the full result `metadata_json`)
    - **Labware API** (volume and content tracking, persisted to `labware` table):
        - `register_labware(campaign_id, labware_key, labware)` — registers a Vial (1 row) or WellPlate (1 row per well) with total/working volume from the model.
        - `record_dispense(campaign_id, labware_key, well_id, source_name, volume_ul)` — increments `current_volume_ul` and appends to `contents` JSON.
        - `get_contents(campaign_id, labware_key, well_id) -> list | None` — returns parsed contents list.
    - **Schema tables**: `campaigns`, `experiments`, `uvvis_measurements`, `filmetrics_measurements`, `camera_measurements`, `asmi_measurements`, `potentiostat_measurements`, `labware`

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
3.  **Connecting**: The system handles connection details (port, serial) via config files in `configs/gantry/`, `configs/deck/`, `configs/board/`, and `configs/protocol/`.

### Setup (`setup/`)
First-run scripts for verifying hardware after unboxing.

- **`hello_world.py`**: Interactive jog test. Connects to the gantry (auto-scan, no config), homes the gantry, then lets you move the router with arrow keys and see live position updates.
    - **Usage**: `python3 setup/hello_world.py`
    - **Controls**: Arrow keys (X/Y ±1mm), Z key (Z down 1mm), X key (Z up 1mm), Q (quit)
    - **Dependencies**: `src/hardware/gantry.py` (Gantry class)
- **`home_manual.py`**: Manual origin homing script for the Genmitsu Desktop CNC (CUB). Connects to the CNC, runs the `manual_origin` homing strategy (interactive keyboard jogging to set work zero), and prints the working volume bounds.
    - **Usage**: `python setup/home_manual.py`
    - **Controls**: Arrow keys (X/Y ±1mm), Z key (Z down 1mm), X key (Z up 1mm), Enter (confirm origin)
    - **Dependencies**: `src/gantry` (Gantry, loader), `setup/keyboard_input.py`
- **`validate_setup.py`**: Validate a protocol setup by loading all 4 configs (gantry, deck, board, protocol) and checking that all deck and gantry positions are within the gantry's working volume.
    - **Usage**: `python setup/validate_setup.py <gantry.yaml> <deck.yaml> <board.yaml> <protocol.yaml>`
    - **Output**: Step-by-step loading status, labware/instrument summaries, bounds validation results, and a final PASS/FAIL verdict.
    - **Dependencies**: `src/gantry`, `src/deck`, `src/board`, `src/protocol_engine`, `src/validation`
- **`run_protocol.py`**: Load, validate, connect to hardware, and run a protocol end-to-end. Runs offline validation first, then connects to the gantry and executes the protocol.
    - **Usage**: `python setup/run_protocol.py <gantry.yaml> <deck.yaml> <board.yaml> <protocol.yaml>`
    - **Dependencies**: `src/gantry`, `src/deck`, `src/board`, `src/protocol_engine`, `src/validation`
- **`keyboard_input.py`**: Helper module that reads single keypresses (including arrow keys) without requiring Enter. Uses `tty`/`termios` (Unix only).

### Calibration (`calibration/`)
- **`home_gantry.py`**: CNC homing wrapper that loads `configs/gantry/cubos_xl.yaml`, connects to the gantry, and runs the configured homing sequence.
    - **Usage**: `python calibration/home_gantry.py`

### Development Commands
- **Install for development**:
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  pip install -e ".[dev]"
  ```
- **Install docs extras**: `pip install -e ".[docs,dev]"`
- **Run tests**: `pytest tests/`
- **Build/serve docs**: use MkDocs commands from the docs environment, e.g. `mkdocs build` or `mkdocs serve`.

## Environment
- **Python**: 3.9+
- **Dependencies**: `pyserial`, `pydantic`, `pyyaml`.
- **Optional/dev dependencies**: `pytest`; docs extras install MkDocs and mkdocstrings.
