# 2026-05-04 Gantry driver status re-query hardening

## Scope

Active PR: https://github.com/Ursa-Laboratories/CubOS/pull/109
Branch: `ben/gantry-driver-position-parse-20260501`
Base: `upstream/staging` at `68384188912e0fe6d50345a026d5ed3855bf0e69`

Small follow-up hardening: make `Mill.current_coordinates()` actively re-query GRBL with `?` after an incomplete/noisy status fragment, instead of only draining whatever serial bytes happen to remain buffered.

## Hardware impact

Potentially affects GRBL gantry/CNC status polling before reporting coordinates. This does not change move command geometry or feed rates, but it changes retry behavior when the serial status read is incomplete/noisy.

## Validation

- Added regression coverage that a truncated `<Idle|WPos:...` fragment causes `current_coordinates()` to issue another `?` query before accepting the next complete status.
- Offline/mock validation only; no physical gantry tested.

Exact local checks run:

```text
/tmp/cubos-gantry-venv/bin/python -m pytest tests/gantry/driver/test_wpos_enforcement.py tests/gantry/driver/test_gantry_driver.py -q
=> 39 passed, 4 subtests passed in 1.17s

/tmp/cubos-gantry-venv/bin/python -m py_compile src/gantry/gantry_driver/driver.py tests/gantry/driver/test_wpos_enforcement.py
=> passed (no output)

git diff --check
=> passed (no output)
```

## Required hardware validation

On a real GRBL gantry, confirm repeated `current_coordinates()` calls still return WPos reliably after normal serial chatter and during idle status polling.
