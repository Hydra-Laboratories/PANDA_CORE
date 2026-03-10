"""Tests for protocol error recovery in Protocol.run()."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from protocol_engine.errors import ProtocolExecutionError
from protocol_engine.protocol import Protocol, ProtocolContext, ProtocolStep


def _make_context(pause_handler=None):
    ctx = MagicMock(spec=ProtocolContext)
    ctx.logger = MagicMock()
    ctx.pause_handler = pause_handler
    ctx.last_completed_step = -1
    return ctx


def _success_handler(context, **kwargs):
    return "ok"


def _failing_handler(context, **kwargs):
    raise ProtocolExecutionError("Step failed")


class TestLastCompletedStep:

    def test_updated_after_each_step(self):
        steps = [
            ProtocolStep(index=0, command_name="cmd1", handler=_success_handler, args={}),
            ProtocolStep(index=1, command_name="cmd2", handler=_success_handler, args={}),
            ProtocolStep(index=2, command_name="cmd3", handler=_success_handler, args={}),
        ]
        protocol = Protocol(steps=steps)
        ctx = _make_context()
        protocol.run(ctx)

        assert ctx.last_completed_step == 2

    def test_starts_at_negative_one(self):
        protocol = Protocol(steps=[])
        ctx = _make_context()
        protocol.run(ctx)

        assert ctx.last_completed_step == -1

    def test_tracks_up_to_failure(self):
        steps = [
            ProtocolStep(index=0, command_name="cmd1", handler=_success_handler, args={}),
            ProtocolStep(index=1, command_name="cmd2", handler=_failing_handler, args={}),
        ]
        protocol = Protocol(steps=steps)
        ctx = _make_context()

        with pytest.raises(ProtocolExecutionError):
            protocol.run(ctx)

        assert ctx.last_completed_step == 0


class TestErrorRecoveryWithHandler:

    def test_handler_called_on_execution_error(self):
        handler_mock = MagicMock()

        steps = [
            ProtocolStep(index=0, command_name="cmd1", handler=_failing_handler, args={}),
        ]
        protocol = Protocol(steps=steps)
        ctx = _make_context(pause_handler=handler_mock)

        # Handler returns without raising, so step should be retried.
        # But the step will fail again — this time we need a handler that
        # modifies the step to succeed on retry.
        call_count = 0

        def handler_that_fixes(context, step, exception):
            nonlocal call_count
            call_count += 1
            # Replace the handler with one that succeeds
            step.handler = _success_handler

        ctx.pause_handler = handler_that_fixes

        protocol.run(ctx)
        assert call_count == 1
        assert ctx.last_completed_step == 0

    def test_error_reraised_without_handler(self):
        steps = [
            ProtocolStep(index=0, command_name="cmd1", handler=_failing_handler, args={}),
        ]
        protocol = Protocol(steps=steps)
        ctx = _make_context(pause_handler=None)

        with pytest.raises(ProtocolExecutionError, match="Step failed"):
            protocol.run(ctx)

    def test_handler_that_raises_propagates_error(self):
        def handler_that_raises(context, step, exception):
            raise exception

        steps = [
            ProtocolStep(index=0, command_name="cmd1", handler=_failing_handler, args={}),
        ]
        protocol = Protocol(steps=steps)
        ctx = _make_context(pause_handler=handler_that_raises)

        with pytest.raises(ProtocolExecutionError):
            protocol.run(ctx)


class TestSuccessfulStepsTracked:

    def test_all_successful_steps_tracked(self):
        steps = [
            ProtocolStep(index=0, command_name="cmd1", handler=_success_handler, args={}),
            ProtocolStep(index=1, command_name="cmd2", handler=_success_handler, args={}),
        ]
        protocol = Protocol(steps=steps)
        ctx = _make_context()
        results = protocol.run(ctx)

        assert len(results) == 2
        assert ctx.last_completed_step == 1
