# Protocols

Protocols are ordered YAML step lists that compile into an executable `Protocol` object. At runtime, each step resolves to a registered command handler and executes against a shared `ProtocolContext`.

## Core Flow

1. Load protocol YAML.
2. Validate the schema and command arguments.
3. Compile each step into a `ProtocolStep`.
4. Inject a `ProtocolContext` containing the board, deck, logger, and optional persistence objects.
5. Run the steps sequentially.

## Example

Minimal move-and-measure pattern:

```yaml
protocol:
  - move:
      instrument: uvvis
      position: plate_1.A1
  - measure:
      instrument: uvvis
```

## Where Commands Live

The command implementations live under `src/protocol_engine/commands/`.

Current command families in the codebase include:

- motion and homing
- pause and breakpoint behavior
- measurement
- scan behavior
- pipette operations

See the generated API reference for the exact module-level functions and signatures.

## Validation Expectations

Protocol execution should be preceded by:

- YAML schema validation
- registry validation for command names and arguments
- gantry/deck/board loading
- bounds validation against the configured working volume

That validation is what keeps a protocol typo or calibration mismatch from becoming a live hardware movement.

## Authoring Guidance

- Prefer explicit instrument names instead of relying on implicit defaults
- Use deck targets like `plate_1.A1` rather than hardcoded coordinates when possible
- Keep hardware-setup changes in deck or board config, not in protocol YAML
- Treat protocols as experiment definitions, not as calibration files

## TODO(manual)

- Add a command cookbook with one worked example per supported command
- Document any protocol style conventions used by the lab
- Define failure handling expectations: retry policy, pause policy, and operator intervention points
- Add examples for mixed workflows involving pipette + measurement + persistence
