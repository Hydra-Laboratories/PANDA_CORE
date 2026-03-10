"""Tests for auto-pause injection into protocols."""

from __future__ import annotations

import pytest

from protocol_engine.dry_run import DepletionEvent, inject_pauses
from protocol_engine.protocol import Protocol, ProtocolStep


def _noop_handler(context, **kwargs):
    pass


def _make_steps(n: int) -> list[ProtocolStep]:
    return [
        ProtocolStep(
            index=i,
            command_name="aspirate",
            handler=_noop_handler,
            args={"position": "vial_1", "volume_ul": 100.0},
        )
        for i in range(n)
    ]


class TestInjectPausesSingleDepletion:

    def test_pause_inserted_before_depletion_step(self):
        steps = _make_steps(3)
        protocol = Protocol(steps=steps)

        depletions = [
            DepletionEvent(
                step_index=1,
                command_name="aspirate",
                labware_key="vial_1",
                well_id=None,
                event_type="underflow",
                shortfall=50.0,
                message="underflow",
            ),
        ]

        result = inject_pauses(protocol, depletions)
        assert len(result) == 4
        assert result.steps[1].command_name == "pause"
        assert result.steps[1].args["reason"] == "refill"
        assert result.steps[1].args["labware_key"] == "vial_1"

    def test_steps_re_indexed(self):
        steps = _make_steps(3)
        protocol = Protocol(steps=steps)

        depletions = [
            DepletionEvent(
                step_index=1,
                command_name="aspirate",
                labware_key="vial_1",
                well_id=None,
                event_type="underflow",
                shortfall=50.0,
                message="underflow",
            ),
        ]

        result = inject_pauses(protocol, depletions)
        for i, step in enumerate(result.steps):
            assert step.index == i


class TestInjectPausesMultipleDepletions:

    def test_multiple_pauses_inserted_correctly(self):
        steps = _make_steps(5)
        protocol = Protocol(steps=steps)

        depletions = [
            DepletionEvent(
                step_index=1,
                command_name="aspirate",
                labware_key="vial_1",
                well_id=None,
                event_type="underflow",
                shortfall=50.0,
                message="underflow at step 1",
            ),
            DepletionEvent(
                step_index=3,
                command_name="aspirate",
                labware_key="vial_1",
                well_id=None,
                event_type="underflow",
                shortfall=30.0,
                message="underflow at step 3",
            ),
        ]

        result = inject_pauses(protocol, depletions)
        assert len(result) == 7  # 5 original + 2 pauses

        pause_indices = [
            i for i, s in enumerate(result.steps)
            if s.command_name == "pause"
        ]
        assert len(pause_indices) == 2

    def test_all_steps_re_indexed_after_multiple_insertions(self):
        steps = _make_steps(4)
        protocol = Protocol(steps=steps)

        depletions = [
            DepletionEvent(
                step_index=0,
                command_name="aspirate",
                labware_key="vial_1",
                well_id=None,
                event_type="underflow",
                shortfall=50.0,
                message="underflow",
            ),
            DepletionEvent(
                step_index=2,
                command_name="aspirate",
                labware_key="vial_1",
                well_id=None,
                event_type="underflow",
                shortfall=30.0,
                message="underflow",
            ),
        ]

        result = inject_pauses(protocol, depletions)
        for i, step in enumerate(result.steps):
            assert step.index == i


class TestInjectPausesNoDepletions:

    def test_no_depletions_returns_same_protocol(self):
        steps = _make_steps(3)
        protocol = Protocol(steps=steps)

        result = inject_pauses(protocol, [])
        assert len(result) == 3
