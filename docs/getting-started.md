# Getting Started

This page covers local setup and the first validation steps.

## Prerequisites

Core software:

- Python 3.9+
- `pip`
- a virtual environment tool such as `venv`

Hardware-dependent workflows may also require:

- a GRBL-compatible CNC gantry over serial
- the Thorlabs TLCCS DLL for `uvvis_ccs`
- the Filmetrics console executable for the Filmetrics driver
- the appropriate serial-connected pipette hardware when using the real pipette driver

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .[dev,docs]
```

If you want just the runtime package without docs tooling:

```bash
pip install -e .
```

## First Validation Flow

Use the repository in this order:

1. Validate the YAML setup offline.
2. Review the reported bounds and command validation output.
3. Connect to hardware only after the offline setup passes.
4. Run the protocol end-to-end.

Offline validation:

```bash
python setup/validate_setup.py \
  configs/gantry/genmitsu_3018_PROver_v2.yaml \
  configs/deck/mofcat_deck.yaml \
  configs/board/mofcat_board.yaml \
  configs/protocol/scan.yaml
```

Hardware execution:

```bash
python setup/run_protocol.py \
  configs/gantry/genmitsu_3018_PROver_v2.yaml \
  configs/deck/mofcat_deck.yaml \
  configs/board/mofcat_board.yaml \
  configs/protocol/scan.yaml
```

Interactive gantry bring-up:

```bash
python3 setup/hello_world.py
```
