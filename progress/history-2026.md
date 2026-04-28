# 2026 Progress History (Compact)

## January
- **2026-01-23:** CNC connection performance improvements and homing latency reduction in the mill driver.

## February
- **2026-02-02:** Created YOLO webcam detection project and upgraded default model to YOLO11.
- **2026-02-10:** Made `test_cnc_move.py` CLI-configurable for hardware move smoke tests.
- **2026-02-11:** Hardware verification + Filmetrics instrument port (driver, models, exceptions, mocks, tests).
- **2026-02-12:** Protocol-engine readiness review; identified deck/labware-target compile gaps and API drift.
- **2026-02-15:** Added board scan + `measurement_height`; board YAML loader updates.
- **2026-02-16:** Migrated board helpers into protocol commands; moved board module into `src/board`.
- **2026-02-17:** Added setup orchestration + gantry/deck bounds validation flow.
- **2026-02-19:** Refactored broad exception handling and well-derivation logic.
- **2026-02-20:** Added `manual_origin` homing strategy and supporting tests/scripts.

## March
- **2026-03-02:** Planned positive-space gantry cutover and identified sequencing risks.
- **2026-03-09:** Enforced WPos behavior, added coordinate conversion coverage, improved gantry utilities.
- **2026-03-11:** Removed all `from src.` / `import src.` usage across runtime/tests/scripts.
- **2026-03-12:** Fixed gantry connect hangs in GRBL alarm state; added API timeout behavior.
- **2026-03-16:** Added gantry and ASMI extension methods for ASMI integration workflows.

## April
- **2026-04-03:** Added centralized instrument registry + vendor validation in board config.
- **2026-04-08:** Fixed packaging for `instruments/registry.yaml` and added artifact tests.
- **2026-04-09:** Added holder-labware scaffolding and generalized position iteration support.
- **2026-04-13:** Added potentiostat instrument support (offline + SDK-backed paths).
- **2026-04-15:** Landed ASMI dual-indentation review fixes and safety/test hardening.
- **2026-04-16:** Documented first-time CubXL connection blocker (firmware flash pending).
- **2026-04-22:** Clarified runner startup/scan semantics and alarm handling behavior.
- **2026-04-28:** Completed phase-2 motion refactor PR-review follow-up fixes.
