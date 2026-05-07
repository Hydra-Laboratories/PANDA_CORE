# Cub XL Right X-Max Rail Guard

## Scope

- Add top-level gantry `machine_structures` schema/loading support.
- Encode the Cub XL right X-max rail as a fixed box at X `480.0..540.0`,
  Y `0.0..300.0`, Z `0.0..100.0`.
- Validate protocol move/home/scan instrument points and known travel segments
  against machine structures separately from working-volume bounds.

## Changed Files

- `src/gantry/gantry_config.py`
- `src/gantry/yaml_schema.py`
- `src/gantry/loader.py`
- `src/validation/protocol_semantics.py`
- `configs/gantry/cub_xl_asmi.yaml`
- `configs/gantry/cub_xl_panda.yaml`
- `configs/gantry/cub_xl_sterling.yaml`
- `tests/gantry/test_yaml_schema.py`
- `tests/gantry/test_loader.py`
- `tests/validation/test_machine_structures.py`
- `README.md`
- `docs/configuration.md`
- `docs/gantry.md`
- `AGENTS.md`

## Validation

- `python -m pytest tests/gantry/test_yaml_schema.py tests/gantry/test_loader.py tests/validation/test_machine_structures.py tests/validation/test_protocol_semantics.py tests/validation/test_structure_clearance.py tests/protocol_engine/test_deck_origin_configs.py -q`
  - Result: `75 passed`
- `python -m pytest tests/gantry -q`
  - Result: `202 passed, 4 subtests passed`
- `python setup/validate_setup.py configs/gantry/cub_xl_asmi.yaml configs/deck/asmi_deck.yaml configs/protocol/asmi_move_a1.yaml`
  - Result: `PASS`
- `python setup/validate_setup.py configs/gantry/cub_xl_asmi.yaml configs/deck/asmi_deck.yaml configs/protocol/asmi_indentation.yaml`
  - Result: `PASS`
- `python setup/validate_setup.py configs/gantry/cub_xl_sterling.yaml configs/deck/sterling_deck.yaml configs/protocol/sterling_park.yaml`
  - Result: `PASS`
- `python setup/validate_setup.py configs/gantry/cub_xl_sterling.yaml configs/deck/sterling_deck.yaml configs/protocol/sterling_vial_scan.yaml`
  - Result: `PASS`
- `git diff --check`
  - Result: passed with no output
- Physical hardware validation is still pending.

## Hardware Impact

- Potentially affected hardware: Cub XL CNC gantry motion and any mounted
  instrument whose commanded point or travel segment could enter the right
  X-max rail volume.
- The change is offline validation only; it does not add runtime actuation or
  controller-setting writes.

## Open Risks / Next Steps

- Confirm on hardware that the measured rail box matches the physical right
  rail envelope.
- Run a dry protocol that approaches near the rail at low Z and verify setup
  validation blocks it before any motion.
- Run a high-Z park/home-adjacent dry protocol that crosses or sits over the
  rail envelope and verify setup validation allows it only above `z=100`.
