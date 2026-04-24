# CNC Project Documentation for Agents

This repository contains code to control a CNC router (mill) using a Python-based driver that communicates over serial (GRBL).

## Hardware Development Rule

This is software for a hardware repository. Any development work can affect real motion, instruments, samples, or connected controllers.

When making changes, always tell the user:

- What hardware the change can touch or affect, even if the change was only validated offline.
- What hardware tests the user must run before trusting the change on a real setup.
- Whether the change was tested only with mocks/offline validation, or also on physical hardware.

When opening or updating a PR, include a hardware impact section that lists:

- Hardware touched or potentially affected.
- Offline validation performed.
- Required hardware validation still pending for the user.

## Large-Refactor Checkpoint Rule

For large refactors, hardware-facing motion changes, or any task likely to outlive one agent context window, create and maintain an explicit checkpoint file under `progress/` before making broad edits. Use a descriptive name such as `progress/issue-87-phase-2-3-checkpoint.md`.

The checkpoint file should be the short-lived source of truth for the active task and should include:

- Current branch, issue/PR link, and task scope.
- Non-negotiable semantic contracts and safety assumptions.
- Files/configs already changed and files likely to change next.
- Tests and validation already run, including exact commands when useful.
- Hardware touched or potentially affected, plus required hardware validation still pending.
- Open risks, blockers, and next steps.

Update the checkpoint whenever the plan changes, before a handoff to another agent, and after each meaningful implementation/validation milestone. If context compacts, read the checkpoint before continuing.

When the task is complete, clean up the checkpoint before final handoff or merge: move any durable information into the issue, PR description, docs, or tests, then delete the temporary checkpoint file. If the checkpoint must remain because the task is still active or being handed to another agent, state that explicitly in the final response.

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
2.  **Moving**: Use `mill.move_to_position(x, y, z)` for safe moves. At the repo/user level, always think and communicate in positive `X`, `Y`, and `Z`.
    - **Coordinates**: The physical/workcell convention is positive `X`, positive `Y`, positive `Z` in the CubOS deck frame. Do not pre-flip signs in calling code to match raw CNC coordinates.
    - **Current XYZ convention**: In the high-level `src/gantry` wrapper, CubOS uses a front-left-bottom deck origin: `+X` operator-right, `+Y` away/back, `+Z` up, `-Z` down. The gantry boundary no longer applies a hidden `Z` sign flip; controller settings must make WPos match the CubOS deck frame.
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
    - **Important semantic split**:
        - Board/instrument `measurement_height` is the generic absolute deck-frame action Z used by shared protocol movement helpers when no protocol-level override is supplied.
        - `ASMI.indentation(..., measurement_height=...)` is the protocol/runtime absolute deck-frame Z for the start of the indentation.
    - **ASMI scan motion model**:
        - `scan.entry_travel_height` is an absolute deck-frame Z used only for the initial transit into the first well (e.g. A1).
        - `scan.interwell_travel_height` is an absolute deck-frame Z used for well-to-well travel inside the scan.
        - After the within-scan transit, `indentation()` moves to its own absolute `measurement_height`, collects baseline force, then performs the stepwise indentation.
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

- **`driver.py`**: `Pipette(BaseInstrument)` — serial driver with built-in offline mode.
    - **Constructor**: `Pipette(pipette_model, port, baud_rate=115200, command_timeout=30.0, name=None, offline=False)`
    - **Lifecycle**: `connect()`, `disconnect()`, `health_check()`, `warm_up()` (homes + primes)
    - **Commands**: `home()`, `prime(speed)`, `aspirate(volume_ul, speed)`, `dispense(volume_ul, speed)`, `blowout(speed)`, `mix(volume_ul, reps, speed)`, `pick_up_tip(speed)`, `drop_tip(speed)`, `get_status() -> PipetteStatus`, `drip_stop(volume_ul, speed)`
    - **Offline mode**: Pass `offline=True` for dry runs — simulates plunger state in memory without serial I/O.
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
  - `home`: home the gantry. With deck-origin configs it preserves the calibrated WPos frame; legacy non-deck-origin configs still zero at the homed pose.
  - `move`: move an instrument to a named position, raw `[x, y, z]`, or deck target.
    - Named/literal XYZ moves may also supply `travel_z` to force a retract-first transit (`Z -> XY -> final Z`).
    - Deck targets ignore `travel_z` and use `Board.move_to_labware()` with the instrument's board-configured absolute `safe_approach_height`.
    - Named positions such as `park_position` live in protocol YAML `positions:`; they are not deck/labware entries.
  - `scan`: iterate all wells on a plate, call an instrument method per well, and persist measurements when a `DataStore` is configured.
    - For generic instruments, omitted scan overrides fall back to the instrument's board-configured absolute `measurement_height` / `safe_approach_height`.
    - `scan.entry_travel_height` is an absolute deck-frame Z used only for the initial move into the first well.
    - `scan.interwell_travel_height` is an absolute deck-frame Z used only for well-to-well travel inside the scan.
    - Legacy scan names `entry_travel_z` and scan-level `safe_approach_height` are rejected before motion.
  - `measure`: move to one deck position and call an instrument method once.
  - `pause`: sleep for a fixed number of seconds.
  - `breakpoint`: pause until the user presses Enter.
  - Pipette commands: `aspirate`, `pick_up_tip`, `transfer`, `serial_transfer`, `mix`, `blowout`, `drop_tip`.
  - `dispense` exists as an internal helper only; use `transfer` in YAML so labware state is logged correctly.

### Gantry Config (`src/gantry`)
Gantry YAML loader and domain model for CNC gantry working volume and homing strategy.

- **Coordinate convention**: At the repo/user level we work in the CubOS deck frame: front-left-bottom origin, `+X` operator-right, `+Y` back/away, `+Z` up, `-Z` down. The `Gantry` boundary does not apply a hidden `Z` sign flip; controller settings must make WPos match this frame.
- **`yaml_schema.py`**: `GantryYamlSchema` with strict Pydantic validation (working volume bounds, homing strategy, serial port, and `cnc.total_z_height`).
- **`gantry_config.py`**: `GantryConfig` and `WorkingVolume` frozen dataclasses. `WorkingVolume.contains(x, y, z)` checks if a point is within bounds (inclusive). `GantryConfig.total_z_height` is the configured vertical envelope; deck `height` values are direct deck-frame Z values, not `total_z_height - height`. `GantryConfig.structure_clearance_z` is an optional absolute Z plane for home/park/edge-risk clearance. `HomingStrategy` enum: `STANDARD`, `XY_HARD_LIMITS`, `MANUAL_ORIGIN`.
- **`loader.py`**: `load_gantry_from_yaml(path)` and `load_gantry_from_yaml_safe(path)`.
- **Config files**: `configs/gantry/` (e.g., `cub_xl.yaml`).

### Validation (`src/validation`)
Bounds validation for protocol setup — ensures all deck positions and gantry-computed positions are within the gantry's working volume before the protocol runs.

- **`bounds.py`**: `validate_deck_positions(gantry, deck)` and `validate_gantry_positions(gantry, deck, board)`. Returns lists of `BoundsViolation` objects. Gantry formula: `gantry_x = target_x - offset_x`, `gantry_y = target_y - offset_y`, and `gantry_z = target_z + instrument.depth` in the +Z-up deck frame.
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
        - `InstrumentMeasurement` with potentiostat type → `potentiostat_measurements` (technique, JSON-encoded `time_s`/`voltage_v`/`current_a`, plus per-technique scalars: `sample_period_s`, `duration_s`, `step_potential_v`, `step_current_a`, `scan_rate_v_s`, `step_size_v`, `cycles`; run metadata `vendor`, `device_id`, `channel`, `started_at`, `stopped_at`, `aborted`, `stop_reason` each promoted to their own column)
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

- **`calibrate_deck_origin.py`**: One-instrument deck-origin calibration utility for issue #87-style configs. Homes the machine at the normalized back-right-top homing corner, clears transient `G92` offsets, asks for a known reference surface height above true deck/bottom Z=0, prompts the operator to jog one reference TCP to the front-left XY reference and known Z surface, sets that pose to `G10 L20 P1 X0 Y0 Z<reference_height>`, then re-homes and reports the measured physical working volume `(x_max, y_max, z_max)`. Use `--reference-z-mm 0` only when the TCP can touch the true bottom; use a known-height block/artifact otherwise. `--measure-reachable-z-min` can record the lowest safe reachable Z for that one TCP without resetting WPos.
    - **Usage**: `python setup/calibrate_deck_origin.py --gantry configs_new/gantry/cub_xl_asmi_deck_origin.yaml`
    - **Known-height artifact**: `python setup/calibrate_deck_origin.py --gantry <gantry.yaml> --reference-z-mm 10`
    - **Reach note**: `python setup/calibrate_deck_origin.py --gantry <gantry.yaml> --reference-z-mm 10 --measure-reachable-z-min`
    - **Dry run**: `python setup/calibrate_deck_origin.py --gantry <gantry.yaml> --dry-run`
    - **Safety**: only use with deck-origin gantry configs whose working-volume minima are all `0.0`; old negative-space configs are rejected.
- **`hello_world.py`**: Interactive jog test. Connects to the gantry (auto-scan, no config), homes the gantry, then lets you move the router with arrow keys and see live position updates.
    - **Usage**: `python3 setup/hello_world.py`
    - **Controls**: Arrow keys (X/Y ±1mm), Z key (Z down 1mm), X key (Z up 1mm), Q (quit)
    - **Dependencies**: `src/hardware/gantry.py` (Gantry class)
    - **TODO**: Replace or remove this legacy flow for the deck-origin scheme; its prompts/control text predate the new `+Z up` convention.
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
    - **Startup behavior**:
        - Connects to the gantry, clears the expected GRBL alarm state if present, and restores controller state.
        - Connects all board instruments before the first protocol step.
        - Disconnects instruments and gantry in `finally`, even on protocol failure.
    - **Dependencies**: `src/gantry`, `src/deck`, `src/board`, `src/protocol_engine`, `src/validation`
- **`keyboard_input.py`**: Helper module that reads single keypresses (including arrow keys) without requiring Enter. Uses `tty`/`termios` (Unix only).

### Calibration (`calibration/`)
- **`home_gantry.py`**: CNC homing wrapper that loads `configs/gantry/cub_xl.yaml`, connects to the gantry, and runs the configured homing sequence.
    - **Usage**: `python calibration/home_gantry.py`
    - **TODO**: Replace or remove this legacy wrapper; deck-origin calibration should use `setup/calibrate_deck_origin.py` so a known-height front-left reference surface is explicitly jogged and assigned before homed WPos is treated as measured working volume.

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
