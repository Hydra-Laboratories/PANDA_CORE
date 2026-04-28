# Protocol

Protocols are ordered YAML step lists that compile into an executable `Protocol` object. At runtime, each step resolves to a registered command handler and executes against a shared `ProtocolContext`.

## Core Flow

1. Load protocol YAML.
2. Validate the schema and command arguments.
3. Compile each step into a `ProtocolStep`.
4. Inject a `ProtocolContext` containing the board, deck, logger, and optional persistence objects.
5. Run the steps sequentially.

## Config

Representative example:

```yaml
positions:
  park_position: [360.0, 260.0, 85.0]

protocol:
  # Home the gantry without redefining calibrated deck-origin WPos
  - home:

  # Scan all wells: move to each well, run indentation
  - scan:
      plate: plate
      instrument: asmi
      method: indentation
      measurement_height: 26.0
      entry_travel_height: 85.0
      interwell_travel_height: 35.0
      indentation_limit: 24.0
      method_kwargs:
        step_size: 0.01
        force_limit: 10.0
        baseline_samples: 10
        measure_with_return: false  # true = down + return (up) sampling

  # Return to park position after scan
  - move:
      instrument: asmi
      position: park_position

  # Home the gantry
  - home:
```

Use this file when:

- changing the experimental sequence
- adding measurement or liquid-handling steps
- adjusting step parameters without changing the machine layout

## Available Commands

| Command | Description |
|---------|-------------|
| `move` | Move an instrument to a deck position |
| `scan` | Iterate all wells on a plate, calling an instrument method per well |
| `measure` | Move to one deck position, then call an instrument method |
| `pick_up_tip` | Pipette: pick up a tip |
| `aspirate` | Pipette: draw liquid |
| `transfer` | Pipette: combined move + aspirate + move + dispense |
| `serial_transfer` | Pipette: sequential transfers across positions |
| `mix` | Pipette: aspirate/dispense repeatedly |
| `blowout` | Pipette: blow out remaining liquid |
| `drop_tip` | Pipette: drop the tip |
| `home` | Home the gantry |
| `pause` | Pause execution for N seconds |
| `breakpoint` | Debug pause with user prompt |

`dispense` exists as an internal helper used by `transfer`, but it is not currently registered as a YAML protocol command.

## Position Values

The `move` command accepts:

- a named position from the top-level `positions` mapping
- raw `[x, y, z]` coordinates
- a deck target string such as `plate_1.A1` or `vial_1`

The `measure` command requires both `instrument` and `position`. It resolves the deck target, approaches with the instrument's absolute `safe_approach_height`, descends to the instrument's absolute `measurement_height`, and then calls the selected method. The default method is `measure`.

## Scan Heights

Use these scan names for new protocols:

- `measurement_height` is the absolute deck-frame action/start Z for a scan target.
- `interwell_travel_height` is the between-well travel Z. When omitted, it
  defaults to `measurement_height`.
- `entry_travel_height` is the first transit Z into the scan. When omitted, it
  defaults to `interwell_travel_height`.
- `indentation_limit` is the ASMI indentation stopping Z. The legacy ASMI name
  `z_limit` is no longer accepted. Under the +Z-up deck frame, downward ASMI
  indentation requires `indentation_limit < measurement_height`.

These fields are absolute deck-frame Z planes, not offsets from the labware Z.
Runtime motion must not add them to, or subtract them from, labware Z.

Example:

```yaml
protocol:
  - measure:
      instrument: uvvis
      position: plate_1.A1
      method: measure
```

## Where Commands Live

The command implementations live under `src/protocol_engine/commands/`.

## Authoring Guidance

- Prefer explicit instrument names instead of relying on implicit defaults
- Use deck targets like `plate.A1` rather than hardcoded coordinates when possible
- Keep hardware-setup changes in deck or board config, not in protocol YAML
- Treat protocols as experiment definitions, not as calibration files
