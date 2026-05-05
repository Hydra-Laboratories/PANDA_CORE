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

## Update — second commit on this branch

After the first commit, single-well indentation via `measure` still failed
end-to-end: `measure` had no protocol-level Z override, so
`approach_and_descend` used `instr.measurement_height` (0.0 in the ASMI board
config), which drove the gantry to the deck floor before `indentation` even
started.

Per the design call: `measure` is the per-position primitive, so it owns
`measurement_height` (action Z); `safe_approach_height` stays scan-only since
only scan needs to manage inter-well transit Z.

This commit:

- Adds `measurement_height: float | None = None` parameter to `measure`. It is
  forwarded to both `approach_and_descend` (for the descent target) *and*
  through `inject_runtime_args` to the bound method (so closed-loop callees
  start from the same Z the gantry descended to).
- Extends `inject_runtime_args` to also handle `measurement_height` injection.
  `scan` now uses the same call shape as `measure` — the duplicated inline
  `measurement_height` check has been removed, along with `scan`'s now-unused
  `inspect` import.
- Two new measure tests:
  - `test_measure_uses_protocol_measurement_height_for_descent` — descent goes
    to the protocol value, not `instr.measurement_height`.
  - `test_measure_forwards_measurement_height_into_method_when_method_declares_it`
    — uses a real `BaseInstrument` subclass with `measurement_height` in its
    method signature; asserts both gantry and `measurement_height` are
    injected.

After both commits, the working YAML for a single-well indent looks like:

```yaml
- measure:
    instrument: asmi
    position: plate.E5
    method: indentation
    measurement_height: 27.0
    method_kwargs:
      indentation_limit: 17.0
      step_size: 0.01
      force_limit: 10.0
```

## Open follow-ups

- Long-term: scan could call `measure` for each well rather than reimplementing
  the per-well approach/descend/act flow itself. That would make the
  one-vs-many distinction the only thing scan owns, with measure handling the
  per-position primitive. Not in scope for this PR.
- Longer term still, consider moving closed-loop `indentation` out of the ASMI
  driver and into a protocol-engine compound command.
