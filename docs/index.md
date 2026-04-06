# PANDA Core

PANDA Core is the Python control layer for a CNC-based lab platform. It combines:

- Gantry motion control for GRBL-based hardware
- Instrument drivers for measurement and liquid handling
- YAML-defined protocols for experiment execution
- Offline validation before real hardware moves
- SQLite-backed experiment persistence and analysis utilities

This site is set up as a practical operator and developer wiki:

- The narrative guides are written manually where operator knowledge matters.
- The API reference is generated from the Python package tree at build time.
- Pages marked `TODO(manual)` are deliberate placeholders for lab-specific knowledge that cannot be inferred safely from code alone.

## Quick Start

Install the project in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .[docs,dev]
```

Run a safe offline validation first:

```bash
python setup/validate_setup.py \
  configs/gantry/genmitsu_3018_PROver_v2.yaml \
  configs/deck/mofcat_deck.yaml \
  configs/board/mofcat_board.yaml \
  configs/protocol/scan.yaml
```

Build the docs locally:

```bash
mkdocs serve
```

## What To Read First

- [Getting Started](getting-started.md) for installation, local docs, and first commands
- [Architecture](architecture.md) for the package-level system map
- [Configuration](configuration.md) for the four YAML surfaces
- [Protocols](protocols.md) for how protocol execution is assembled and validated
- [Hardware Operations](hardware-operations.md) for runbooks and safety placeholders
- [API Reference](reference/index.md) for generated module docs

## Documentation Status

!!! warning "Manual content still needed"
    This site is scaffolded to be immediately useful, but several pages intentionally leave room for operator-written content:

    - hardware safety and lockout procedures
    - calibration and re-calibration workflows
    - vendor driver acquisition and installation notes
    - experiment-specific protocol conventions
    - backup, retention, and incident handling policies
