"""Tests for raw keyboard helpers."""

from __future__ import annotations

import pytest

from setup import keyboard_input


class _FakeStdin:
    def __init__(self, chars: str):
        self._chars = iter(chars)

    def read(self, _count: int) -> str:
        return next(self._chars)


def test_unix_raw_ctrl_c_raises_keyboard_interrupt(monkeypatch):
    monkeypatch.setattr(keyboard_input.sys, "stdin", _FakeStdin("\x03"))

    with pytest.raises(KeyboardInterrupt):
        keyboard_input._unix_read_one_key()
