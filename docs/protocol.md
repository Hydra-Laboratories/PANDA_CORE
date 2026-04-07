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
  safe_z: [0.0, 0.0, -50.0]

protocol:
  # Home the gantry and zero coordinates
  - home:

  # Scan all wells: move to each well, run indentation
  - scan:
      plate: plate
      instrument: asmi
      method: indentation
      method_kwargs:
        z_limit: -83.0
        step_size: 0.01
        force_limit: 10.0
        measurement_height: -73.0
        baseline_samples: 10

  # Return to safe Z after scan
  - move:
      instrument: asmi
      position: safe_z

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
| `measure` | Single measurement with an instrument |
| `pick_up_tip` | Pipette: pick up a tip |
| `aspirate` | Pipette: draw liquid |
| `dispense` | Pipette: deliver liquid |
| `transfer` | Pipette: combined move + aspirate + move + dispense |
| `serial_transfer` | Pipette: sequential transfers across positions |
| `mix` | Pipette: aspirate/dispense repeatedly |
| `blowout` | Pipette: blow out remaining liquid |
| `drop_tip` | Pipette: drop the tip |
| `home` | Home the gantry |
| `pause` | Pause execution for N seconds |
| `breakpoint` | Debug pause with user prompt |

## Where Commands Live

The command implementations live under `src/protocol_engine/commands/`.

## Authoring Guidance

- Prefer explicit instrument names instead of relying on implicit defaults
- Use deck targets like `plate.A1` rather than hardcoded coordinates when possible
- Keep hardware-setup changes in deck or board config, not in protocol YAML
- Treat protocols as experiment definitions, not as calibration files
