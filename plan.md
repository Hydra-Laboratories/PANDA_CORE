# Plan: Manual Homing Strategy for Genmitsu 3018 PRO Desktop

## Context
The Genmitsu 3018 PRO Desktop has **no homing switches**. The user manually jogs
the machine to the origin corner before the software takes over. All coordinates
are **positive** (X: 0–280, Y: 0–170, Z: 0–40). Z=0 is retracted (safe height),
Z increases downward toward the deck.

## Coordinate Convention
- **Origin (0, 0, 0):** Front-left corner, gantry fully retracted (Z at top)
- **X+:** Moves right (0 → 280)
- **Y+:** Moves away from operator (0 → 170)
- **Z+:** Moves down toward deck surface (0 → 40)
- **Safe Z:** Z=0 (fully retracted)

## Changes

### 1. New homing strategy: `manual`

**`src/gantry/gantry_config.py`**
- Add `MANUAL = "manual"` to `HomingStrategy` enum

**`src/gantry/yaml_schema.py`**
- Add `"manual"` to the `homing_strategy` Literal type

### 2. `home_manual()` method in driver

**`src/gantry/gantry_driver/driver.py`**
- New method `home_manual()`:
  1. Prints a prompt: "Jog the machine to the origin position (front-left, Z fully retracted), then press Enter."
  2. Blocks on `input()` until user confirms
  3. Sends `G10 L20 P1 X0 Y0 Z0` — sets current WPos to (0,0,0)
  4. Sends `G90` — enforce absolute mode
  5. Sets `self.homed = True`
  6. Logs the action

### 3. Configure GRBL soft limits on connect

**`src/gantry/gantry_driver/driver.py`**
- New method `configure_soft_limits(x_max, y_max, z_max)`:
  1. Sends `$20=1` (enable soft limits)
  2. Sends `$130={x_max}` (X max travel)
  3. Sends `$131={y_max}` (Y max travel)
  4. Sends `$132={z_max}` (Z max travel)
  5. Updates `self.config` for each
- This will be called from `Gantry.home()` or `connect()` when
  the config provides working volume bounds and strategy is `manual`.

### 4. Wire into Gantry.home()

**`src/gantry/gantry.py`**
- Add `elif strategy == "manual":` branch that calls `self._mill.home_manual()`
- After homing, call `self._mill.configure_soft_limits(280, 170, 40)` using
  values from the working volume config

### 5. Update Genmitsu YAML config

**`configs/gantry/genmitsu_3018_PRO_Desktop.yaml`**
```yaml
serial_port: /dev/cu.usbserial-2130
cnc:
  homing_strategy: manual

working_volume:
  x_min: 0.0
  x_max: 280.0
  y_min: 0.0
  y_max: 170.0
  z_min: 0.0
  z_max: 40.0
```

### 6. Update safe_z_height and max_z_height defaults

Currently `safe_z_height = -10.0` and `max_z_height = 0.0`. With positive-Z-down:
- `max_z_height` = 0.0 (top of travel — this already works)
- `safe_z_height` should be a small positive number like 2.0 (slightly below retracted,
  enough clearance to safely traverse XY)

This needs to be configurable or derived from the working volume, but for now
the manual homing method will set `self.max_z_height = 0.0` (already correct)
and note that `safe_z_height` should be set to a small positive value for
positive-Z-down setups. We can wire this through config in a follow-up.

### 7. MockMill update

**`src/gantry/gantry_driver/mock.py`**
- Add `home_manual()` stub that sets coordinates to (0,0,0) and `self.homed = True`

### 8. Tests (TDD)

**`tests/gantry/driver/test_manual_homing.py`** — New test file:
- `test_home_manual_sets_wpos_to_zero` — verifies `G10 L20 P1 X0 Y0 Z0` is sent
- `test_home_manual_enforces_g90` — verifies G90 is sent after setting origin
- `test_home_manual_sets_homed_flag` — verifies `self.homed = True`
- `test_home_manual_prompts_user` — verifies `input()` is called (mocked)
- `test_configure_soft_limits_sends_correct_commands` — verifies $20=1, $130, $131, $132
- `test_configure_soft_limits_updates_config` — verifies config dict updated

**`tests/gantry/test_gantry.py`** — Add:
- `test_home_with_manual_strategy` — verifies Gantry.home() calls `home_manual()`

**`tests/gantry/test_yaml_schema.py`** — Add:
- `test_manual_homing_strategy_accepted` — verifies "manual" is valid in schema

### 9. Update AGENTS.md / README.md
- Document the new `manual` homing strategy and positive coordinate convention

## Files Changed (summary)
| File | Change |
|------|--------|
| `src/gantry/gantry_config.py` | Add `MANUAL` enum value |
| `src/gantry/yaml_schema.py` | Add `"manual"` to Literal |
| `src/gantry/gantry_driver/driver.py` | Add `home_manual()`, `configure_soft_limits()` |
| `src/gantry/gantry.py` | Wire manual strategy in `home()` |
| `src/gantry/gantry_driver/mock.py` | Add `home_manual()` stub |
| `configs/gantry/genmitsu_3018_PRO_Desktop.yaml` | Update to manual + positive coords |
| `tests/gantry/driver/test_manual_homing.py` | New: 6+ tests |
| `tests/gantry/test_gantry.py` | Add manual strategy test |
| `tests/gantry/test_yaml_schema.py` | Add manual schema test |
| `AGENTS.md` / `README.md` | Document new strategy |
| `progress/2026-02-19.md` | Update progress |

## What This Does NOT Change
- No changes to `current_coordinates()` — WPos enforcement already handles this
- No changes to movement commands — they already use WPos + G90
- No changes to instrument offsets — they work the same in positive coordinate space
- The existing `standard` and `xy_hard_limits` strategies are untouched
