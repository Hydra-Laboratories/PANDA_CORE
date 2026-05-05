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

  # Scan all wells: travel at gantry safe_z to the first well, descend to
  # safe_approach_height above each plate surface, then to measurement_height.
  - scan:
      plate: plate
      instrument: asmi
      method: indentation
      # safe_approach_height is the labware-relative XY-travel offset
      # between wells (mm above the plate surface). Required.
      safe_approach_height: 8.0
      # measurement_height (the action plane offset) may be set here OR on
      # the instrument config — exactly one place (XOR rule). Here we let
      # the instrument config supply it.
      indentation_limit: 5.0   # magnitude: descend 5 mm into the well
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

The `measure` command requires `instrument` and `position`. It travels XY
at the gantry's absolute `safe_z`, descends to
`labware.height_mm + measurement_height`, and calls the selected method.
The default method is `measure`. `measurement_height` may be set on the
command or on the instrument config — exactly one source (XOR rule).

## Scan Heights

Scan heights are *labware-relative* offsets above `labware.height_mm`
(positive = above the plate surface; negative = below):

- `measurement_height` is the action plane offset. Set it on the protocol
  command or on the instrument config — exactly one place (XOR rule).
- `safe_approach_height` is the between-wells XY-travel offset, required
  on every scan. Must be at or above `measurement_height` in +Z-up.
- `indentation_limit` is a sign-agnostic *magnitude* — the descent
  distance below the action plane. Legacy ASMI `z_limit` is rejected.

Inter-labware travel and the entry approach for the first well of a scan
use the gantry's absolute `safe_z`, not these labware-relative fields.

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
