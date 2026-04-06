# Hardware Operations

This page is intentionally biased toward runbooks rather than code internals. The code can describe interfaces; it cannot safely infer lab operating procedures.

## Safe Execution Sequence

Recommended high-level order:

1. Verify the machine is physically clear and powered as expected.
2. Confirm the intended gantry, deck, board, and protocol YAML files.
3. Run offline validation.
4. Bring up the gantry and home it.
5. Connect instruments.
6. Run the protocol.
7. Review measurements and logs.
8. Disconnect and park the machine.

## Available Setup Tools

The repository already provides:

- `setup/hello_world.py`: interactive jog and bring-up script
- `setup/validate_setup.py`: offline config and bounds validation
- `setup/run_protocol.py`: validation followed by live execution

## What This Repo Covers Well

- motion control interfaces
- config validation
- protocol execution order
- some instrument and persistence abstractions

## What Must Be Supplied Manually

!!! warning "TODO(manual)"
    The following content should be written by the lab team before this page is treated as authoritative:

    - emergency stop and power-off procedure
    - pre-run safety checklist
    - homing checklist for each gantry model
    - calibration and probe-height procedure
    - acceptable consumables and mounting rules
    - end-of-run shutdown and cleaning steps
    - maintenance and service intervals

## Suggested Sections To Fill In

### Startup Checklist

`TODO(manual):` Write the exact startup steps, including power order, cable checks, and machine-clearance checks.

### Homing and Zeroing

`TODO(manual):` Record the approved homing procedure, what to watch for, and how to recover from bad homing results.

### Calibration

`TODO(manual):` Explain deck calibration, instrument offsets, and how calibration changes are reviewed before updating YAML.

### Alarm Recovery

`TODO(manual):` Document common GRBL alarm states, when `$X` unlock is acceptable, and when the run must be aborted.
