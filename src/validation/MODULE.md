# Module: validation

## Purpose
Bounds validation: checks all deck positions and gantry-computed positions against the gantry's working volume before protocol execution.

## Public API (`__init__.py`)
- `validate_deck_positions(gantry, deck)` — Check labware positions
- `validate_gantry_positions(gantry, deck, board)` — Check instrument-adjusted positions
- `BoundsViolation` — Dataclass describing a single violation
- `SetupValidationError` — Exception collecting all violations

## Contract
None.

## Internal Structure
- `bounds.py` — Validation functions
- `errors.py` — `BoundsViolation` dataclass, `SetupValidationError`

## Dependencies
`gantry` (GantryConfig, WorkingVolume), `deck` (Deck, labware types), `board` (Board)

## Dependents
`protocol_engine` (via `setup.py`)

## Rules for Agents
- Gantry formula: `gantry_pos = deck_pos - instrument_offset`
- Violations are collected (not raised one at a time) for complete reporting
- Adding new labware types requires updating `_get_all_positions()` in `bounds.py`

## Test Command
```bash
pytest tests/validation/ -v
```
