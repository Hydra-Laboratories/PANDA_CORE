# Getting Started

## Two Ways To Use CubOS

There are two entrypoints:

1. **YAML-based** - define your experiment across three YAML config files
   (gantry, deck, protocol) and run it from the command line.
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
  configs/protocol/asmi_move_a1.yaml
```

This loads all three configs, checks deck and instrument-adjusted positions
against the gantry working volume, validates protocol motion semantics, and
prints PASS/FAIL.

## Calibration

For a real setup, calibrate the persistent deck-origin WPos frame before
running protocols:

```bash
PYTHONPATH=src python setup/calibrate_deck_origin.py \
  --gantry configs/gantry/cub_xl_asmi.yaml
```

After the no-instrument FLB/BRT homing run is verified, calibrate the selected
instrument TCP:

```bash
PYTHONPATH=src python setup/calibrate_deck_origin.py \
  --gantry configs/gantry/cub_xl_asmi.yaml \
  --instrument asmi
```

The calibration script requires explicit `cnc.calibration_homing.runtime_brt`
and `origin_flb` profiles. It snapshots rollback GRBL settings, unlocks an
initial alarm if present, homes to FLB, sets G54 WPos `(0, 0, 0)`, actively
moves to an estimated BRT inspection pose from configured bounds minus 2 mm,
programs conservative soft limits, then restores the runtime BRT profile before
disconnecting without running BRT `$H`. BRT WPos is not used to discover
machine bounds.

For XY offset calibration, the operator jogs the selected TCP onto the physical
deck-center mark. The script asks interactively whether the TCP is touching
true deck bottom or whether the operator measured a ruler gap.

Keep `working_volume.z_min: 0.0` under this flow. A TCP that stops above deck
bottom records its lower reach under
`instruments.<name>.reach_limits.tcp_z_min`; safe left/right X reach is recorded
as `reach_limits.gantry_x_min/max` and enforced by setup validation.

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
  configs/protocol/asmi_move_a1.yaml
```

Move to ASMI indentation or scans only after the minimal move behaves as
expected on hardware.
