# 2026-05-05 — Inject gantry into `measure` like `scan`

## Scope

`scan` already inspects the bound instrument method's signature and, if it
declares a `gantry` parameter, passes `context.board.gantry` to it. That's how
`ASMI.indentation` (closed-loop Z stepping + force feedback) works under
`scan`. `measure` was the open-loop sibling — it called the method with only
the YAML-supplied `method_kwargs`, so any closed-loop method called via
`measure` blew up with `TypeError: missing 1 required positional argument:
'gantry'`.

This change makes `measure` behave like `scan` for that path, and consolidates
the dispatch logic so the two stay in sync.

## What changed

- New `src/protocol_engine/commands/_dispatch.py` with
  `inject_runtime_args(callable_method, method_kwargs, context)`. Returns a
  fresh kwargs dict; injects `gantry` from `context.board.gantry` when the
  method's signature declares it. Caller-supplied `gantry` always wins.
- `measure.py` now calls `inject_runtime_args` between `approach_and_descend`
  and the method invocation. No protocol YAML changes required.
- `scan.py` replaces its inline gantry-injection block with the helper. Its
  scan-only `measurement_height` injection (which depends on
  `normalize_scan_arguments`) stays inline because it has no analogue in
  `measure`.

## Tests

- New `test_measure_command.py::test_measure_injects_gantry_when_method_signature_declares_it`
  — uses a real `BaseInstrument` subclass (`MagicMock` doesn't expose real
  signatures to `inspect.signature`) whose `indentation(gantry, ...)` records
  the kwargs it was called with. Asserts `gantry` is the sentinel from
  `context.board.gantry`.
- New `test_measure_command.py::test_measure_does_not_inject_gantry_when_method_does_not_declare_it`
  — same fake's open-loop `measure()` is invoked; assertion is implicit (no
  TypeError on extra kwarg).
- All 1028 existing tests still pass (`pytest tests/`).

## Hardware impact

- Affects: any protocol step that uses `measure` to invoke a closed-loop
  instrument method. In practice, ASMI single-well indentation runs.
- Offline validation: pytest only.
- Required hardware validation by user: run an ASMI single-well measurement
  via a `measure` step (e.g. `asmi_indentation_test.yaml` against a known
  plate) and confirm baseline + descent + force-limit stop behave the same as
  the per-well behavior under `scan`.

## Open follow-ups

- `scan.py` still has scan-specific `measurement_height` injection inline. If
  more context-dependent params show up (e.g. `data_store`, `board`), revisit
  whether they belong in `inject_runtime_args` too.
- Longer term, consider moving closed-loop `indentation` out of the ASMI
  driver and into a protocol-engine compound command. Tracked separately;
  not addressed here.
