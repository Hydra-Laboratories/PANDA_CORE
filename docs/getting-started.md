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
    configs_new/gantry/cub_xl_asmi_deck_origin.yaml \
    configs_new/deck/asmi_deck_origin.yaml \
    configs_new/board/asmi_board_deck_origin.yaml \
    configs_new/protocol/asmi_move_a1_deck_origin.yaml
```

This loads all four configs, checks that every labware position and instrument-adjusted position is within the gantry working volume, and prints PASS/FAIL.

## Running a Protocol

Once validation passes, connect the gantry and run:

```bash
python setup/run_protocol.py \
    configs_new/gantry/cub_xl_asmi_deck_origin.yaml \
    configs_new/deck/asmi_deck_origin.yaml \
    configs_new/board/asmi_board_deck_origin.yaml \
    configs_new/protocol/asmi_move_a1_deck_origin.yaml
```

## Interactive Jog Test

For deck-origin configs, normalize `$3`/`$23` first, then calibrate WPos in
two parts: first jog to the front-left XY origin and lowest safe reachable Z
for the active TCP, then assign Z from bottom contact or a ruler-measured
deck-to-TCP gap:

```bash
python setup/calibrate_deck_origin.py --gantry configs_new/gantry/cub_xl_asmi_deck_origin.yaml --instrument asmi
```

If the TCP cannot reach true deck bottom, measure the vertical gap from deck to
TCP with a ruler and pass that gap explicitly:

```bash
python setup/calibrate_deck_origin.py --gantry configs_new/gantry/cub_xl_asmi_deck_origin.yaml --z-reference-mode ruler-gap --tip-gap-mm 5 --instrument filmetrics
```

If the TCP can safely touch true deck bottom, use bottom mode instead:

```bash
python setup/calibrate_deck_origin.py --gantry configs_new/gantry/cub_xl_asmi_deck_origin.yaml --z-reference-mode bottom
```

For one-instrument configs, use the measured lower-reach Z as
`working_volume.z_min`. For example, a TCP that stops 5 mm above deck and homes
to `Z=105` should use `z_min: 5.0`, `z_max: 105.0`. Multi-instrument configs
will need per-instrument lower-reach limits instead of one global Z minimum.

```bash
python setup/hello_world.py --gantry configs_new/gantry/cub_xl_asmi_deck_origin.yaml
```
