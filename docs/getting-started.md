# Getting Started

## Two Ways To Use CubOS

There are two entrypoints:

1. **YAML-based** - define your experiment across four YAML config files
   (gantry, deck, board, protocol) and run it from the command line.
2. **Python API** - import `setup_protocol()` and build experiments
   programmatically. See the [API Reference](reference/index.md) for details.

This guide focuses on the YAML-based workflow.

## Prerequisites

- Python 3.9+
- `pip`
- a GRBL-compatible CNC gantry over serial for hardware runs
- instrument-specific drivers when using real instruments

Hardware motion depends on controller settings and WPos calibration. If the
machine has not been normalized yet, start with
[Gantry Bring-Up](admin/gantry-bring-up.md), then run
[Calibrate Deck Origin](calibration.md).

## Installation

```bash
git clone https://github.com/Ursa-Laboratories/CubOS.git
cd CubOS
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## First Validation

Validate your YAML setup offline before connecting hardware:

```bash
PYTHONPATH=src python setup/validate_setup.py \
  configs/gantry/cub_xl_asmi.yaml \
  configs/deck/asmi_deck.yaml \
  configs/board/asmi_board.yaml \
  configs/protocol/asmi_move_a1.yaml
```

This loads all four configs, checks deck and instrument-adjusted positions
against the gantry working volume, validates protocol motion semantics, and
prints PASS/FAIL.

## Calibration

For a real setup, calibrate the persistent deck-origin WPos frame before
running protocols:

```bash
PYTHONPATH=src python setup/calibrate_deck_origin.py \
  --gantry configs/gantry/cub_xl_asmi.yaml \
  --instrument asmi
```

The calibration script homes the gantry, clears transient `G92` offsets, prompts
you to jog the active TCP to the front-left lower-reach origin, assigns X/Y, and
then assigns Z by bottom contact or a ruler-measured gap.

Use bottom mode when the TCP can safely touch true deck bottom:

```bash
PYTHONPATH=src python setup/calibrate_deck_origin.py \
  --gantry configs/gantry/cub_xl_asmi.yaml \
  --z-reference-mode bottom \
  --instrument asmi
```

Use ruler-gap mode when the TCP stops above deck bottom:

```bash
PYTHONPATH=src python setup/calibrate_deck_origin.py \
  --gantry configs/gantry/cub_xl_asmi.yaml \
  --z-reference-mode ruler-gap \
  --tip-gap-mm 5 \
  --instrument asmi
```

For one-instrument configs, use the measured lower-reach Z as
`working_volume.z_min`. For example, a TCP that stops 5 mm above deck and homes
to `Z=105` should use `z_min: 5.0`, `z_max: 105.0`. Multi-instrument configs
need per-instrument lower-reach limits instead of one global Z minimum.

## Interactive Jog Test

After calibration, run a small jog test and verify physical direction:

```bash
PYTHONPATH=src python setup/hello_world.py \
  --gantry configs/gantry/cub_xl_asmi.yaml
```

Expected directions:

- `+X` moves right
- `+Y` moves back, away from the operator
- `+Z` moves up
- `-Z` moves down

## Running A Protocol

Once validation, calibration, and jog checks pass, connect the gantry and run a
minimal protocol:

```bash
PYTHONPATH=src python setup/run_protocol.py \
  configs/gantry/cub_xl_asmi.yaml \
  configs/deck/asmi_deck.yaml \
  configs/board/asmi_board.yaml \
  configs/protocol/asmi_move_a1.yaml
```

Move to ASMI indentation or scans only after the minimal move behaves as
expected on hardware.
