# BACKLOG

> **Every agent MUST check this file before starting work.**
> Mark items you're working on with `[IN PROGRESS - <branch>]`.
> Add new items as you discover them.
> When done, move items to Completed with the date.

## Bugs
(none)

## Features
- [ ] Add protocol command: `wait` (pause for N seconds)
- [ ] Add protocol command: `transfer` (aspirate from source, move, dispense to target)
- [ ] Camera instrument driver

## Tech Debt
- [ ] Resolve Python dual-import issue (both `src` and `.` on pythonpath causes `isinstance()` failures when mixing `from src.X` and `from X` imports)
- [ ] Consider switching to relative imports within `src/` packages to avoid dual-import entirely

## Agent Tasks
(none pending)

## Completed
- [x] 2026-03-08: Multi-agent scaffold — system_manifest.yaml, BACKLOG.md, contracts.py, MODULE.md files, validation scripts, pre-commit hook, CI updates
- [x] 2026-03-08: Fixed README.md merge conflict
- [x] 2026-03-08: Removed try/except import fallbacks in board.py, board/loader.py
- [x] 2026-02-19: Clean Code refactoring (exception handling, well derivation)
- [x] 2026-02-17: Protocol setup validation + OfflineGantry + bounds validation
- [x] 2026-02-16: Board helpers migrated to protocol commands
- [x] 2026-02-15: Board.scan() + measurement_height + Board YAML loader
- [x] 2026-02-12: Gantry refactor + Filmetrics driver port
- [x] 2026-02-11: CNC hardware verification + safety refactor
