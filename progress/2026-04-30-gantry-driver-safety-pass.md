# 2026-04-30 Gantry Driver Safety Pass

## Scope
- Branch: `ben/gantry-driver-safety-pass-20260430`
- Goal: first small hardening PR for low-level gantry/G-code driver predictability.
- Initial target: reject non-finite motion values before the low-level driver formats G-code.

## Current Plan
1. Add a focused failing driver test for non-finite target and travel coordinates. Done.
2. Add the smallest validation layer at the `Mill` movement boundary. Done.
3. Run focused gantry driver tests, then broader feasible tests. Partially blocked by missing local dependencies; syntax and direct driver smoke checks run.
4. Commit, push, open a PR against `staging`, and include hardware impact plus verification. Pending.

## Work Completed
- Added a regression test proving `Mill.move_to_position()` rejects NaN/Inf target coordinates and NaN travel Z without emitting G-code.
- Re-enabled low-level target coordinate validation in `src/gantry/gantry_driver/driver.py`.
- Added finite-number validation before the no-op movement check so invalid travel Z cannot be hidden by an otherwise unchanged target.
- Added the same guard in movement command generation as a final boundary before raw G-code strings are formatted.

## Validation
- `python3 -m py_compile src/gantry/gantry_driver/driver.py tests/gantry/driver/test_gantry_driver.py` -> passed.
- Direct import/smoke harness with stubbed serial module -> passed (`driver validation smoke passed`).
- `python3 -m pytest tests/gantry/driver/test_gantry_driver.py -q` -> blocked: `/usr/bin/python3: No module named pytest`.
- `python3 -m pytest -q` -> blocked: `/usr/bin/python3: No module named pytest`.
- `PYTHONPATH=src python3 tests/gantry/driver/test_gantry_driver.py` -> blocked: `ModuleNotFoundError: No module named 'pydantic'`.
- `.venv/bin/python -m pip install -e '.[dev]'` -> blocked by restricted network/DNS while resolving build dependency `setuptools`.

## Hardware Impact
- Potentially affected hardware: CNC gantry XYZ motion only, through low-level G-code emission.
- Current validation: offline/mock tests only.
- Required physical validation before trust: dry-run a bounded gantry move sequence on the target controller and confirm valid finite moves still execute as expected.
