# Module: protocol_engine

## Purpose
Protocol loading, command registry with `@protocol_command` decorator, execution engine, and setup orchestration. Defines the ProtocolContext that all commands receive.

## Public API (`__init__.py`)
- `Protocol` — Executable sequence of validated steps
- `ProtocolContext` — Runtime context (board, deck, gantry, data_store, campaign_id)
- `ProtocolStep` — Single compiled step
- `CommandRegistry` — Singleton registry for command handlers
- `protocol_command` — Decorator to register a command
- `ProtocolExecutionError`, `ProtocolLoaderError` — Exceptions
- `load_protocol_from_yaml()` / `load_protocol_from_yaml_safe()` — YAML loading

## Contract
None (protocol_engine is the top-level orchestrator).

## Internal Structure
- `protocol.py` — `Protocol`, `ProtocolContext`, `ProtocolStep` (COORDINATION REQUIRED)
- `registry.py` — `CommandRegistry` singleton, `@protocol_command` decorator
- `setup.py` — `setup_protocol()` orchestration (loads all configs, validates)
- `loader.py` — Protocol YAML loading
- `yaml_schema.py` — Pydantic schema for protocol YAML
- `errors.py` — Exception classes
- `commands/` — Command implementations (SAFE PARALLEL ZONE)
  - `move.py` — `move` command
  - `pipette.py` — `aspirate`, `dispense`, `blowout`, `mix`, etc.
  - `scan.py` — `scan` command (row-major well traversal + measurement)

## Dependencies
`board`, `deck`, `gantry`, `instruments`, `validation`

## Dependents
`setup/` scripts

## Rules for Agents
- `commands/` is a SAFE PARALLEL ZONE — each command file is self-contained
- New commands: create a new file in `commands/`, use `@protocol_command("name")`
- COORDINATION REQUIRED for `protocol.py` — `ProtocolContext` changes affect all commands
- Don't modify `registry.py` unless changing the registration mechanism itself

## Test Command
```bash
pytest tests/protocol_engine/ -v
```
