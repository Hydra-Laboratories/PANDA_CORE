# Getting Started

This page covers local setup, first validation steps, and how to work with the documentation site.

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

## Local Documentation Workflow

Serve the docs locally:

```bash
mkdocs serve
```

Build the static site:

```bash
mkdocs build
```

Read the generated API docs from the `API Reference` section. Those pages are built from the package tree during `mkdocs build` and should not be edited by hand.

## TODO(manual)

Fill in these repo-specific onboarding details before treating this as operator-ready documentation:

- Supported operating systems and Python versions in the lab environment
- Known-good USB serial adapters and port naming expectations
- Vendor driver download locations and version pins
- Which sample config files are canonical for each hardware installation
- Who owns calibration, maintenance, and protocol approval
