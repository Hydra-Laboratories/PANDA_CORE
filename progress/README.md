# Progress Index (Consolidated)

This directory was consolidated to reduce token load and make agent indexing faster.

## Files to read first

1. `progress/active-checkpoint.md` — current short-lived source of truth for in-flight work.
2. `progress/history-2026.md` — compact timeline of completed milestones.

## Archive policy

- Daily progress notes were merged into `history-2026.md`.
- If deep implementation details are needed, use `git log -- progress/` and commit diffs instead of restoring high-token daily notes.
