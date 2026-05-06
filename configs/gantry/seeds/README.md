# Gantry calibration seeds

These YAML files are first-time calibration inputs. They answer the chicken-and-egg problem for multi-instrument calibration: the calibration CLI needs to know which instruments are mounted, but their `offset_x`, `offset_y`, and `depth` values do not need to be correct yet.

Use a seed when creating or recalibrating a setup:

```bash
python setup/calibrate_multi_instrument_board.py \
  --gantry configs/gantry/seeds/<seed>.yaml \
  --output-gantry configs/gantry/<calibrated>.yaml
```

Seed rules:

- Top-level `instruments:` is the mounted instrument inventory.
- `offset_x`, `offset_y`, and `depth` are placeholders set to `0.0`.
- GRBL settings and working volumes are startup estimates copied from the current setup configs; verify controller `$3`/`$23`, homing, and travel before hardware use.
- Do not run real protocols with seed configs after calibration. Use the calibrated output under `configs/gantry/`.

Hardware safety: calibration can move the CNC gantry, change G54 work coordinates, and program soft limits. Run `--dry-run` first, then calibrate slowly with clear E-stop access.
