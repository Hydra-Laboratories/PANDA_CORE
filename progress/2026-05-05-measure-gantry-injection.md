# 2026-05-05 — Inject gantry into `measure` like `scan`; tighten dispatch

## Scope

Two related fixes for closed-loop methods invoked via the `measure` protocol
command, plus a packaging fix that surfaced during bring-up. Reshapes scan's
argument surface to match the architectural rule that scan owns multi-well
travel and nothing per-position.

## Commits

### 1. `10d1207` — Inject gantry into `measure` like `scan` via shared helper

`scan` already inspected the bound instrument method and injected
`context.board.gantry` when the method declared a `gantry` parameter. `measure`
did not, so any closed-loop method called via `measure` failed with
`TypeError: missing 1 required positional argument: 'gantry'`. This blocked
single-well indentation tests.

Extracted the inspect-based dispatch into
`protocol_engine.commands._dispatch.inject_runtime_args` and applied it from
both commands so they stay in sync.

### 2. `3164b6f` — Add `measurement_height` to `measure`, consolidate scan dispatch

After commit 1, `measure + method=indentation` still failed end-to-end:
`measure` had no protocol-level Z override, so `approach_and_descend` used
`instr.measurement_height` (0.0 in ASMI's board YAML), driving the gantry to
the deck floor before `indentation` started.

Per the design call: `measure` is the per-position primitive, so it owns
`measurement_height` (action Z); `safe_approach_height` stays scan-only since
only scan needs inter-well transit Z.

This commit:

- Added `measurement_height: float | None = None` parameter to `measure`. It
  is forwarded to both `approach_and_descend` (for the descent target) *and*
  through `inject_runtime_args` to the bound method, so closed-loop callees
  start from the same Z the gantry was descended to.
- Extended `inject_runtime_args` to handle `measurement_height` injection
  alongside `gantry`. `scan` was consolidated to use the same call shape —
  the duplicated inline `measurement_height` check and the scan-only
  `inspect` import were removed.

### 3. `84afec1` — Ship deck.labware.definitions data files in the wheel

`pip install`'d cubos crashed when a deck YAML used `load_name:
sbs_96_wellplate` because `<site-packages>/deck/labware/definitions/registry.yaml`
was missing. The registry plus per-definition config YAMLs (and CAD models)
live alongside Python modules but weren't listed in
`tool.setuptools.package-data`, so they got dropped on the way into the wheel.

Added `deck.labware.definitions` package-data globs (`registry.yaml`,
`*/*.yaml`, `*/*.glb`, `*/*.stl`, `*/*.step`). New
`tests/deck/test_definition_packaging.py` mirrors
`tests/instruments/test_registry_packaging.py`: builds a real wheel + sdist
via `setuptools.build_meta` and asserts the registry plus a canary
`SBS96WellPlate.yaml` are present in both.

### 4. (review-fix commit) — Drop `measurement_height` / `indentation_limit` from `scan`; tighten injection

PR review flagged that scan's pre-existing top-level `measurement_height` and
`indentation_limit` parameters violate the same architectural rule used to
keep `safe_approach_height` off `measure`: scan owns multi-well orchestration,
not per-position concerns. Worse, the helper's caller-wins guard from
commit 2 introduced a regression where YAML `method_kwargs.measurement_height`
would silently override the protocol-level Z the gantry actually descended to.

Resolution:

- Removed `measurement_height` and `indentation_limit` from `scan()`'s
  signature. They live in `method_kwargs` now (or fall back to the
  instrument's board-config default for `measurement_height`).
- Scan pops `measurement_height` out of `method_kwargs` to drive the descent
  target, then passes it through the helper, which re-injects it only when
  the bound method declares it (so methods like open-loop `measure` that
  don't take it don't TypeError).
- Tightened `inject_runtime_args`: runtime injection is now always the source
  of truth for both `gantry` and `measurement_height`. There's no legitimate
  case for a YAML-supplied gantry handle, and a `method_kwargs.measurement_height`
  diverging from the protocol command's descent target is the exact footgun
  this dispatch surface exists to prevent.
- Added a `ProtocolExecutionError` when the method declares `gantry` but
  `context.board.gantry` is None — clearer than the late `AttributeError`
  the closed-loop method would otherwise raise.
- Added validation messages for top-level `scan.measurement_height` /
  `scan.indentation_limit` in `protocol_semantics.py` so existing protocols
  using the old shape get a clear migration message.
- Migrated `configs/protocol/asmi_indentation.yaml` and affected scan /
  semantics tests so `measurement_height` / `indentation_limit` live inside
  `method_kwargs`.

## Tests added / strengthened

- `test_measure_injects_gantry_when_method_signature_declares_it`
- `test_measure_does_not_inject_gantry_when_method_does_not_declare_it`
- `test_measure_uses_protocol_measurement_height_for_descent`
- `test_measure_forwards_measurement_height_into_method_when_method_declares_it`
- `test_measure_zero_measurement_height_descends_to_zero_not_instrument_default`
  (boundary `is not None` regression guard)
- `test_measure_raises_when_method_requires_gantry_but_board_gantry_is_none`
  (None-gantry guard)
- `test_method_kwargs_measurement_height_passed_through_to_method` on the
  scan side, with an explicit gantry-injection assertion guarding the
  refactor.
- `tests/deck/test_definition_packaging.py::test_wheel_includes_deck_definition_yamls`

Migrated pre-existing protocol-semantics tests to put `measurement_height` /
`indentation_limit` inside `method_kwargs`. Updated the legacy-violation test
to expect the two new top-level rejections.

Full suite: 1033 passed.

## Working YAML after this PR

Single well via `measure`:

```yaml
- measure:
    instrument: asmi
    position: plate.E5
    method: indentation
    measurement_height: 27.0          # deck-frame action Z (measure-level)
    method_kwargs:
      indentation_limit: 17.0
      step_size: 0.01
      force_limit: 10.0
```

Full plate via `scan`:

```yaml
- scan:
    plate: plate
    instrument: asmi
    method: indentation
    entry_travel_height: 85.0
    interwell_travel_height: 35.0
    method_kwargs:
      measurement_height: 32.0        # action Z; lives with the method, not on scan
      indentation_limit: 30.0
      step_size: 0.1
      force_limit: 10.0
```

## Hardware impact

Touches: any protocol step that uses `measure` to invoke a closed-loop
instrument method, plus all `scan`-based protocols that previously used
top-level `scan.measurement_height` / `scan.indentation_limit` — those need
migration to `method_kwargs`.

Offline validation: pytest only — no live hardware exercised in this branch.

Required hardware validation by user: run an ASMI single-well measurement via
a `measure` step, and confirm baseline → descent → force-limit stop matches
per-well behavior under `scan`.

## Open follow-ups

- Long-term: scan could call `measure` for each well rather than
  reimplementing per-well approach/descend/act. Would make scan own only
  multi-well orchestration; not in scope for this PR.
- Longer term still, consider moving closed-loop `indentation` out of the
  ASMI driver and into a protocol-engine compound command.
