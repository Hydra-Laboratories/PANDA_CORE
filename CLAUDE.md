Always write code in a clean and organized matter, implementing the best practices from the Clean Code book.
Test driven development for everything. Think about the design, what tests are needed, and write tests before implementing code. Make sure tests run as you move through each task.
Document each chat's progress and a markdown file in a directory called progress, dated to the current date. Make it if it doesn't exist yet.
When planning, make sure to ask follow up questions to confirm that everything I want in the plan I get down. 
Always make sure to add to the progress directory when you are working on the task for each chat. This ensures I have all context moving forward. Include what work was done, what issues were found and how they were resolved, and anything else highly important.
Make sure to clean up after yourself. Delete any files that are no longer needed. For example, if you write a test_s3_connection.py to verify s3 connectivity but we don't need it for later, delete it. Same goes with planning markdown files.
Always write clean code, using the principles from the book "Clean Code" by Robert Martin.
When you finish a task, make sure to update your progress in the progress/ directory.
If the task makes a fundamental change (i.e. you add a new command line argument, you add a brand new feature) make sure to add it to AGENTS.md and README.md such that another agent or human can understand for context easily if changes need to be made.
Always create a plan that I will review before executing when in planning mode.

## Multi-Agent Development

This codebase is designed for multiple AI coding agents to work in parallel.
Follow these instructions to avoid conflicts and maintain coordination.

### Before Starting Work
1. Read `system_manifest.yaml` to understand the module layout and dependency graph
2. Read `BACKLOG.md` and mark your task as `[IN PROGRESS - <branch>]`
3. Read the `MODULE.md` for any module you plan to touch
4. Check `src/contracts.py` for the interfaces you must satisfy

### While Working
5. Only import from a module's public API (its `__init__.py` / `__all__`)
6. Run the module's specific tests after each change (see system_manifest.yaml for test_command)
7. If you need to change `src/contracts.py`, coordinate via BACKLOG.md first
8. Keep progress notes in `progress/` files (not in MODULE.md)

### Before Committing
9. Run `python scripts/validate_agent_changes.py` to check affected tests
10. Update `BACKLOG.md` (mark completed, add new items discovered)
11. Update `progress/` with session notes
12. Only update MODULE.md if you changed the module's public interface

### Safe Parallel Zones (ZERO conflict risk)
- `src/instruments/pipette/` — Pipette driver (self-contained)
- `src/instruments/filmetrics/` — Filmetrics driver (self-contained)
- `src/instruments/uvvis_ccs/` — UV-Vis driver (self-contained)
- `src/instruments/<new>/` — Adding a new instrument
- `src/protocol_engine/commands/` — Each command file is self-contained
- `data/` — DataStore (only depends on instrument measurement types)
- `configs/` — YAML configuration files

### Coordination Required (check BACKLOG.md first)
- `src/contracts.py` — All cross-module interfaces
- `src/instruments/base_instrument.py` — BaseInstrument ABC (all instruments inherit)
- `src/protocol_engine/protocol.py` — ProtocolContext (used by all commands)
- `src/board/board.py` — Board.move() offset math (used by protocol_engine)
- `src/gantry/gantry.py` — Hardware interface
- `system_manifest.yaml` — System-wide metadata
