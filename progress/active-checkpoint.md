# Active Checkpoint — Issue #87 Phase 2/3

- **Branch:** `codex/phase-2-refactor-motion`
- **Issue:** `Ursa-Laboratories/CubOS#87`
- **Scope:** Deck-origin (+Z-up) motion cutover across gantry, board, protocol motion helpers, and setup/homing semantics.
- **Status:** Offline implementation complete; physical hardware validation still pending.

## Non-negotiable contracts
- Deck frame is front-left-bottom origin with `+X` right, `+Y` back/away, `+Z` up.
- Travel/action heights are absolute deck-frame Z planes (`measurement_height`, `entry_travel_height`, `interwell_travel_height`, `interwell_scan_height` when present).
- Runtime must not recompute action Z using `labware_z ± height`.
- ASMI indentation downward motion must decrease Z.

## Changed areas (high level)
- Gantry boundary and motion semantics.
- Board move-to-labware behavior and scan/measure movement helpers.
- Protocol commands (`home`, `move`, `scan`, `measure`, pipette flow).
- Deck loader height semantics and setup validation.
- Setup scripts (`run_protocol`, calibration/jog helpers).

## Validation completed (offline)
- Unit/integration suites for motion semantics, command behavior, and loader/validation paths.
- PR review pass addressing critical findings for phase-2 refactor branch.

## Hardware impact and pending validation
- **Potentially affected hardware:** CNC gantry motion (XYZ), homing, board-mounted instruments (ASMI/Filmetrics/UV-Vis/Pipette/UV curing/Potentiostat) during protocol travel and measurement moves.
- **Offline validation performed:** Mock/unit/integration test coverage only (no physical actuation confirmed in this checkpoint file).
- **Required hardware validation before trust on real setup:**
  1. Re-run deck-origin calibration on target controller/settings.
  2. Validate homing + alarm recovery + preserve-WCS behavior.
  3. Validate bounded `move`, `scan`, and `measure` transits on sacrificial dry run.
  4. Validate ASMI indentation direction and limits on a controlled fixture.

## Open risks
- Controller-specific GRBL settings may still mismatch expected WPos frame.
- Multi-instrument lower-reach constraints need explicit per-instrument modeling beyond one-tool calibration assumptions.

## Next steps
1. Run hardware bring-up checklist on CubXL with calibrated deck-origin configs.
2. Record measured working-volume maxima/minima and update configs.
3. Capture physical validation evidence in PR/docs and retire checkpoint at merge.
