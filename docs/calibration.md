# Gantry Calibration

Use `setup/calibrate_gantry.py` as the only user-facing calibration entrypoint.
It reads a seed YAML, counts mounted instruments, chooses the single- or
multi-instrument flow, and writes a calibrated gantry YAML.

## Run Guided Calibration

Single-instrument ASMI example:

```bash
PYTHONPATH=src python setup/calibrate_gantry.py \
  --seed configs/gantry/seeds/cub_xl_asmi.yaml \
  --output-gantry configs/gantry/cub_xl_asmi.yaml
```

Sterling three-instrument example:

```bash
PYTHONPATH=src python setup/calibrate_gantry.py \
  --seed configs/gantry/seeds/cub_xl_sterling_3_instrument.yaml \
  --output-gantry configs/gantry/cub_xl_sterling_3_instrument.yaml
```

The wrapper preflights the seed/output paths, lists detected instruments, and
asks for confirmation before connecting to hardware.

During jog steps:

- arrow keys jog X/Y
- `X` jogs `+Z` up
- `Z` jogs `-Z` down
- number keys change jog step size
- Enter confirms the current calibration step
- `Q` aborts

## Single-Instrument Flow

For a seed with one mounted instrument, the flow asks you to place a calibration
block at the front-left origin point and jog the instrument tip/probe to touch
the block top. It assigns X/Y/Z at that same physical pose, with Z set to the
calibration block height.

## Multi-Instrument Flow

For a seed with multiple mounted instruments, the flow asks you to pick the
left-most/reference instrument and the lowest instrument by number. It sets the
shared deck frame, asks for the calibration block height, then records each
instrument against the same physical block point to compute `offset_x`,
`offset_y`, and `depth`.

## After Calibration

Validate the calibrated gantry with a deck and protocol before running real
protocols:

```bash
PYTHONPATH=src python setup/validate_setup.py \
  configs/gantry/<calibrated>.yaml \
  configs/deck/<deck>.yaml \
  configs/protocol/<protocol>.yaml
```

Calibration can move hardware, change work coordinates, and program soft-limit
travel settings. Keep E-stop reachable and validate slowly on hardware.
