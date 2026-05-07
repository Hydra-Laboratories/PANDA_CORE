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
        instr.indentation, {"step_size": 0.02}, ctx, measurement_height=0.0,
    )

    assert kwargs["gantry"] is sentinel
    assert kwargs["step_size"] == 0.02


def test_does_not_inject_gantry_when_method_does_not_declare_it():
    """Open-loop methods (no `gantry` parameter) must not receive a
    `gantry` kwarg — would TypeError on the unexpected argument."""
    instr = _ClosedLoopInstrument()
    ctx = _ctx()

    kwargs = inject_runtime_args(instr.measure, {}, ctx, measurement_height=0.0)

    assert "gantry" not in kwargs


def test_raises_when_method_requires_gantry_but_board_gantry_is_none():
    """Better than the late `AttributeError: 'NoneType'` the closed-loop
    method would otherwise raise inside its first `gantry.move(...)`."""
    instr = _ClosedLoopInstrument()
    ctx = _ctx(gantry=None)

    with pytest.raises(ProtocolExecutionError, match="gantry"):
        inject_runtime_args(instr.indentation, {}, ctx, measurement_height=0.0)


# ── measurement_height injection / type guard ─────────────────────────────

class _MethodWithMeasurementHeight(BaseInstrument):
    def __init__(self) -> None:
        super().__init__(
            name="indenter",
            offset_x=0.0, offset_y=0.0, depth=0.0,
        )

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def health_check(self) -> bool: return True

    def indentation(self, gantry, measurement_height: float = 0.0) -> dict:
        return {"gantry": gantry, "measurement_height": measurement_height}


def test_forwards_measurement_height_into_method_when_declared():
    instr = _MethodWithMeasurementHeight()
    sentinel = object()
    ctx = _ctx(gantry=sentinel)

    kwargs = inject_runtime_args(
        instr.indentation, {}, ctx, measurement_height=27.0,
    )

    assert kwargs["measurement_height"] == 27.0
    assert kwargs["gantry"] is sentinel


def test_does_not_forward_measurement_height_when_method_does_not_declare_it():
    instr = _ClosedLoopInstrument()
    ctx = _ctx()

    kwargs = inject_runtime_args(
        instr.indentation, {}, ctx, measurement_height=27.0,
    )

    assert "measurement_height" not in kwargs


def test_runtime_measurement_height_overrides_method_kwargs():
    """Engine value (the Z the gantry was descended to) is the source of
    truth, not whatever `method_kwargs` carried."""
    instr = _MethodWithMeasurementHeight()
    ctx = _ctx()

    kwargs = inject_runtime_args(
        instr.indentation, {"measurement_height": 99.0}, ctx,
        measurement_height=27.0,
    )

    assert kwargs["measurement_height"] == 27.0


def test_zero_measurement_height_forwarded_not_dropped():
    """Boundary case: `0.0` is a legitimate offset (touch labware rim),
    not 'unspecified'. Pin the `is not None` semantic so a future
    'simplify to truthy check' regression flips this test red."""
    instr = _MethodWithMeasurementHeight()
    sentinel = object()
    ctx = _ctx(gantry=sentinel)

    kwargs = inject_runtime_args(
        instr.indentation, {}, ctx, measurement_height=0.0,
    )

    assert kwargs["measurement_height"] == 0.0


@pytest.mark.parametrize("bad_value", ["", "27.0", "abc", float("nan"), float("inf"), True])
def test_rejects_non_finite_measurement_height(bad_value):
    """Non-numeric / non-finite values must fail at the dispatch boundary
    rather than slipping through to motion code where they would surface
    as opaque late TypeErrors."""
    instr = _MethodWithMeasurementHeight()
    ctx = _ctx()

    with pytest.raises(ProtocolExecutionError, match="measurement_height"):
        inject_runtime_args(
            instr.indentation, {}, ctx, measurement_height=bad_value,
        )


def test_method_kwargs_not_mutated():
    """The helper returns a fresh dict; the caller's `method_kwargs` is
    untouched. Important because callers reuse the same dict across loop
    iterations (e.g. scan's per-well loop)."""
    instr = _MethodWithMeasurementHeight()
    ctx = _ctx()
    original = {"measurement_height": 99.0}
    snapshot = dict(original)

    inject_runtime_args(
        instr.indentation, original, ctx, measurement_height=27.0,
    )

    assert original == snapshot
