# Getting Started

## Two Ways to Use CubOS

There are two entrypoints:

1. **YAML-based** — define your experiment across four YAML config files (gantry, deck, board, protocol) and run it from the command line. This is the recommended way to get started.
2. **Python API** — import `setup_protocol()` and build experiments programmatically. See the [API Reference](reference/index.md) for details.

This guide focuses on the YAML-based workflow.

## Prerequisites

- Python 3.9+
- `pip`

Hardware-dependent workflows may also require:

- a GRBL-compatible CNC gantry over serial
- instrument-specific drivers (see [Board](board.md) for the full list)

## Installation

```bash
git clone https://github.com/Hydra-Laboratories/CubOS.git
cd CubOS
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## First Validation

Validate your YAML setup offline (no hardware needed):

```bash
python setup/validate_setup.py \
    configs/gantry/asmi_gantry.yaml \
    configs/deck/asmi_deck.yaml \
    configs/board/asmi_board.yaml \
    configs/protocol/asmi_indentation.yaml
```

This loads all four configs, checks that every labware position and instrument-adjusted position is within the gantry working volume, and prints PASS/FAIL.

## Running a Protocol

Once validation passes, connect the gantry and run:

```bash
python setup/run_protocol.py \
    configs/gantry/asmi_gantry.yaml \
    configs/deck/asmi_deck.yaml \
    configs/board/asmi_board.yaml \
    configs/protocol/asmi_indentation.yaml
```

## Interactive Jog Test

For deck-origin configs, normalize `$3`/`$23` first, then calibrate WPos using
a reference surface with a known height above true deck/bottom Z=0:

```bash
python setup/calibrate_deck_origin.py --gantry configs_new/gantry/cub_xl_asmi_deck_origin.yaml
```

If the reference TCP touches or focuses on a 43 mm artifact at the front-left
XY reference point, pass that height explicitly:

```bash
python setup/calibrate_deck_origin.py --gantry configs_new/gantry/cub_xl_asmi_deck_origin.yaml --reference-z-mm 43
```

To also record the lowest safe reachable Z for that one TCP:

```bash
python setup/calibrate_deck_origin.py --gantry configs_new/gantry/cub_xl_asmi_deck_origin.yaml --reference-z-mm 43 --measure-reachable-z-min
```

The older jog helper is still available for connectivity checks, but it predates
the deck-origin bring-up flow:

```bash
python setup/hello_world.py
```
