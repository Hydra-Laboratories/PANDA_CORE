"""Direct unit tests for `inject_runtime_args` — the dispatch boundary
shared by `measure` and `scan`.

The 12 #114-era tests in `test_measure_command.py` that previously
covered these behaviors were dropped during the labware-relative merge;
this file is the regression-protection replacement.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from instruments.base_instrument import BaseInstrument
from protocol_engine.commands._dispatch import inject_runtime_args
from protocol_engine.errors import ProtocolExecutionError
from protocol_engine.protocol import ProtocolContext


class _ClosedLoopInstrument(BaseInstrument):
    """Real-class fake whose `indentation` declares a `gantry` parameter,
    mirroring `ASMI.indentation`.

    `inspect.signature` reads the actual function signature, so a real
    subclass is required — `MagicMock` would expose its synthetic signature
    instead, defeating the gantry-injection branch.
    """

    def __init__(self) -> None:
        super().__init__(
            name="indenter",
            offset_x=0.0, offset_y=0.0, depth=0.0,
        )

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def health_check(self) -> bool: return True

    def indentation(self, gantry, step_size: float = 0.01) -> dict:
        return {"gantry": gantry, "step_size": step_size}

    def measure(self) -> str:
        return "no-gantry"


def _ctx(gantry: object | None = ...) -> ProtocolContext:
    """Build a minimal ProtocolContext with a configurable board.gantry."""
    board = MagicMock()
    board.gantry = object() if gantry is ... else gantry
    deck = MagicMock()
    return ProtocolContext(board=board, deck=deck)


# ── Gantry injection ──────────────────────────────────────────────────────

def test_injects_gantry_when_method_signature_declares_it():
    instr = _ClosedLoopInstrument()
    sentinel = object()
    ctx = _ctx(gantry=sentinel)

    kwargs = inject_runtime_args(
        instr.indentation, {"step_size": 0.02}, ctx, measurement_z=0.0,
    )

    assert kwargs["gantry"] is sentinel
    assert kwargs["step_size"] == 0.02


def test_does_not_inject_gantry_when_method_does_not_declare_it():
    """Open-loop methods (no `gantry` parameter) must not receive a
    `gantry` kwarg — would TypeError on the unexpected argument."""
    instr = _ClosedLoopInstrument()
    ctx = _ctx()

    kwargs = inject_runtime_args(instr.measure, {}, ctx, measurement_z=0.0)

    assert "gantry" not in kwargs


def test_raises_when_method_requires_gantry_but_board_gantry_is_none():
    """Better than the late `AttributeError: 'NoneType'` the closed-loop
    method would otherwise raise inside its first `gantry.move(...)`."""
    instr = _ClosedLoopInstrument()
    ctx = _ctx(gantry=None)

    with pytest.raises(ProtocolExecutionError, match="gantry"):
        inject_runtime_args(instr.indentation, {}, ctx, measurement_z=0.0)


# ── absolute Z injection (measurement_z, target_z) ───────────────────────

class _MethodWithAbsoluteZs(BaseInstrument):
    def __init__(self) -> None:
        super().__init__(
            name="indenter",
            offset_x=0.0, offset_y=0.0, depth=0.0,
        )

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def health_check(self) -> bool: return True

    def indentation(
        self, gantry, *, measurement_z: float, target_z: float = 0.0,
    ) -> dict:
        return {"gantry": gantry, "measurement_z": measurement_z, "target_z": target_z}


def test_forwards_measurement_z_into_method_when_declared():
    instr = _MethodWithAbsoluteZs()
    sentinel = object()
    ctx = _ctx(gantry=sentinel)

    kwargs = inject_runtime_args(
        instr.indentation, {}, ctx, measurement_z=27.0, target_z=22.0,
    )

    assert kwargs["measurement_z"] == 27.0
    assert kwargs["target_z"] == 22.0
    assert kwargs["gantry"] is sentinel


def test_does_not_forward_target_z_when_method_does_not_declare_it_and_caller_omits_it():
    """The `target_z` is engine-injected only when both (a) the method
    declares it and (b) the caller supplied a value. A method without
    `target_z` and a caller that doesn't supply one should leave the
    kwarg out — that's the open-loop case (e.g. `measure`)."""
    instr = _ClosedLoopInstrument()
    ctx = _ctx()

    kwargs = inject_runtime_args(
        instr.indentation, {}, ctx, measurement_z=27.0,
    )

    assert "measurement_z" not in kwargs  # method doesn't declare it either
    assert "target_z" not in kwargs


def test_runtime_measurement_z_overrides_method_kwargs():
    """Engine value (the Z the gantry was descended to) is the source of
    truth, not whatever `method_kwargs` carried."""
    instr = _MethodWithAbsoluteZs()
    ctx = _ctx()

    kwargs = inject_runtime_args(
        instr.indentation, {"measurement_z": 99.0}, ctx,
        measurement_z=27.0, target_z=22.0,
    )

    assert kwargs["measurement_z"] == 27.0


def test_zero_measurement_z_forwarded_not_dropped():
    """Boundary case: `0.0` is a legitimate absolute Z. Pin so a future
    'simplify to truthy check' regression flips this test red."""
    instr = _MethodWithAbsoluteZs()
    sentinel = object()
    ctx = _ctx(gantry=sentinel)

    kwargs = inject_runtime_args(
        instr.indentation, {}, ctx, measurement_z=0.0, target_z=-1.0,
    )

    assert kwargs["measurement_z"] == 0.0


def test_target_z_omitted_when_caller_passes_none():
    """`target_z` is optional — `measure` doesn't have a deepest plane.
    A None-valued `target_z` must not be forwarded as `target_z=None`
    (would override a method default with None)."""
    instr = _MethodWithAbsoluteZs()
    ctx = _ctx(gantry=object())

    kwargs = inject_runtime_args(
        instr.indentation, {}, ctx, measurement_z=27.0,
    )

    assert "target_z" not in kwargs


@pytest.mark.parametrize("bad_value", ["", "27.0", "abc", float("nan"), float("inf"), True])
def test_rejects_non_finite_measurement_z(bad_value):
    """Non-numeric / non-finite values must fail at the dispatch boundary
    rather than slipping through to motion code where they would surface
    as opaque late TypeErrors."""
    instr = _MethodWithAbsoluteZs()
    ctx = _ctx()

    with pytest.raises(ProtocolExecutionError, match="measurement_z"):
        inject_runtime_args(
            instr.indentation, {}, ctx, measurement_z=bad_value,
        )


@pytest.mark.parametrize("bad_value", ["", "abc", float("nan"), float("inf"), True])
def test_rejects_non_finite_target_z(bad_value):
    instr = _MethodWithAbsoluteZs()
    ctx = _ctx()

    with pytest.raises(ProtocolExecutionError, match="target_z"):
        inject_runtime_args(
            instr.indentation, {}, ctx, measurement_z=10.0, target_z=bad_value,
        )


def test_required_target_z_missing_raises_actionable_error():
    """If a method requires `target_z` (no default) and the engine has no
    value to inject, surface a `ProtocolExecutionError` naming the
    user-facing field. The bare Python `TypeError` from a missing-required
    keyword call is unactionable mid-protocol."""
    instr = _MethodWithAbsoluteZs()
    ctx = _ctx(gantry=object())

    # Build a method whose `target_z` is required (no default).
    class _Required(BaseInstrument):
        def __init__(self) -> None:
            super().__init__(name="x", offset_x=0.0, offset_y=0.0, depth=0.0)
        def connect(self) -> None: ...
        def disconnect(self) -> None: ...
        def health_check(self) -> bool: return True
        def indentation(self, gantry, *, measurement_z: float, target_z: float) -> dict:
            return {"target_z": target_z}

    required = _Required()
    with pytest.raises(ProtocolExecutionError, match="indentation_limit_height"):
        inject_runtime_args(
            required.indentation, {}, ctx, measurement_z=10.0,
        )


def test_target_z_supplied_to_method_without_target_z_raises():
    """If the user supplies `indentation_limit_height` but the chosen
    method does not consume `target_z`, refusing the dispatch beats
    silently dropping the depth bound — a typo like `method: indent`
    (vs `indentation`) would otherwise sail through."""
    instr = _ClosedLoopInstrument()  # indentation(self, gantry, step_size=...)
    ctx = _ctx()

    with pytest.raises(ProtocolExecutionError, match="silently ignored"):
        inject_runtime_args(
            instr.indentation, {}, ctx,
            measurement_z=10.0, target_z=5.0,
        )


def test_method_kwargs_not_mutated():
    """The helper returns a fresh dict; the caller's `method_kwargs` is
    untouched. Important because callers reuse the same dict across loop
    iterations (e.g. scan's per-well loop)."""
    instr = _MethodWithAbsoluteZs()
    ctx = _ctx()
    original = {"measurement_z": 99.0}
    snapshot = dict(original)

    inject_runtime_args(
        instr.indentation, original, ctx, measurement_z=27.0,
    )

    assert original == snapshot
