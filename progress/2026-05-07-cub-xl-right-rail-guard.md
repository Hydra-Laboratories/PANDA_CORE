# Cub XL Right X-Max Rail Guard

## Scope

- Replace public gantry-YAML `machine_structures` with required top-level
  `gantry_type` (`cub` or `cub_xl`).
- Keep the Cub XL right X-max rail as built-in setup validation keyed by
  `gantry_type: cub_xl`.
- Reject protocols before motion when commanded instrument points or known
  travel segments would hit the built-in rail: X `480.0..540.0`,
  Y `0.0..300.0`, Z `0.0..100.0`.
- Preserve the high-clearance home behavior: home over the rail passes above
  rail height and fails at/below rail height.

## Changed Files

- `src/gantry/gantry_config.py`
- `src/gantry/__init__.py`
- `src/gantry/yaml_schema.py`
- `src/gantry/loader.py`
- `src/validation/protocol_semantics.py`
- `setup/validate_setup.py`
- `configs/gantry/*.yaml`
- `tests/gantry/test_yaml_schema.py`
- `tests/gantry/test_loader.py`
- `tests/validation/test_machine_structures.py`
- `tests/protocol_engine/test_mock_rail_guard_configs.py`
- `README.md`
- `docs/configuration.md`
- `docs/gantry.md`
- `AGENTS.md`

## Validation

- `python -m pytest tests/gantry/test_yaml_schema.py tests/gantry/test_loader.py tests/gantry/test_gantry_config.py tests/validation/test_machine_structures.py tests/protocol_engine/test_mock_rail_guard_configs.py -q`
  - Result: `92 passed`
- `python -m pytest tests/setup/test_protocol_setup.py tests/setup/test_integration.py tests/board/test_board_loader.py tests/setup/test_calibrate_deck_origin.py tests/setup/test_calibrate_multi_instrument_board.py -q`
  - Result: `79 passed`
- `python -m pytest tests/validation/test_protocol_semantics.py tests/validation/test_safe_z.py tests/validation/test_bounds_validation.py tests/protocol_engine/test_deck_origin_configs.py -q`
  - Result: `66 passed`
- `python -m pytest tests/protocol_engine/test_home_command.py tests/gantry/test_origin.py tests/test_holder_labware.py -q`
  - Result: `41 passed`
- `python setup/validate_setup.py configs/gantry/cub_xl_asmi.yaml configs/deck/asmi_deck.yaml configs/protocol/asmi_move_a1.yaml`
  - Result: `PASS`
- `python setup/validate_setup.py configs/gantry/cub_xl_asmi.yaml configs/deck/asmi_deck.yaml configs/protocol/asmi_indentation.yaml`
  - Result: `PASS`
- `python setup/validate_setup.py configs/gantry/cub_xl_sterling.yaml configs/deck/sterling_deck.yaml configs/protocol/sterling_park.yaml`
  - Result: `PASS`
- `python setup/validate_setup.py configs/gantry/cub_xl_sterling.yaml configs/deck/sterling_deck.yaml configs/protocol/sterling_vial_scan.yaml`
  - Result: `PASS`
- `python setup/validate_setup.py configs/gantry/cub_filmetrics.yaml configs/deck/filmetrics_deck.yaml configs/protocol/filmetrics_scan.yaml`
  - Result: `PASS`
- `python setup/validate_setup.py configs/gantry/cub_xl_panda.yaml configs/deck/panda_deck.yaml configs/protocol/panda_protocol.yaml`
  - Result: instrument loading still fails because the PANDA gantry uses
    placeholder instrument types not present in `src/instruments/registry.yaml`.
- `git diff --check`
  - Result: passed with no output

## Hardware Impact

- Potentially affected hardware: Cub XL CNC gantry motion and any mounted
  instrument whose commanded point or travel segment could enter the right
  X-max rail volume.
- This change is offline setup validation only; it does not add runtime
  actuation or controller-setting writes.

## Open Risks / Next Steps

- Physical hardware validation is still pending.
- Confirm on hardware that the built-in Cub XL rail envelope matches the
  physical right rail.
- Run a dry protocol that approaches near the rail at low Z and verify setup
  validation blocks it before any motion.
- Run a high-Z home/park-adjacent dry protocol over the rail envelope and
  verify setup validation allows it only above `z=100`.
