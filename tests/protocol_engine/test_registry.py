"""Tests for the @protocol_command decorator and CommandRegistry."""

import pytest
from pydantic import ValidationError

from src.protocol_engine.registry import (
    CommandRegistry,
    _build_schema_from_signature,
    protocol_command,
)


@pytest.fixture(autouse=True)
def _fresh_registry():
    """Reset the singleton before and after each test."""
    CommandRegistry.reset()
    yield
    CommandRegistry.reset()


# ─── Registration ────────────────────────────────────────────────────────────


def test_protocol_command_registers_function():
    @protocol_command("greet")
    def greet(context, name: str) -> None:
        pass

    reg = CommandRegistry.instance()
    assert "greet" in reg.command_names
    assert reg.get("greet").handler is greet


def test_protocol_command_uses_function_name_by_default():
    @protocol_command()
    def hello(context, msg: str) -> None:
        pass

    assert "hello" in CommandRegistry.instance().command_names


def test_protocol_command_uses_explicit_name():
    @protocol_command("custom_name")
    def my_func(context, x: int) -> None:
        pass

    reg = CommandRegistry.instance()
    assert "custom_name" in reg.command_names
    assert reg.get("custom_name").handler is my_func


def test_duplicate_command_name_raises():
    @protocol_command("dup")
    def first(context) -> None:
        pass

    with pytest.raises(ValueError, match="already registered"):

        @protocol_command("dup")
        def second(context) -> None:
            pass


def test_get_unknown_command_raises():
    reg = CommandRegistry.instance()
    with pytest.raises(KeyError, match="Unknown protocol command 'nope'"):
        reg.get("nope")


def test_get_unknown_command_lists_available():
    @protocol_command("alpha")
    def alpha(context) -> None:
        pass

    @protocol_command("beta")
    def beta(context) -> None:
        pass

    reg = CommandRegistry.instance()
    with pytest.raises(KeyError, match="alpha.*beta"):
        reg.get("nope")


def test_reset_clears_registry():
    @protocol_command("tmp")
    def tmp(context) -> None:
        pass

    assert "tmp" in CommandRegistry.instance().command_names
    CommandRegistry.reset()
    assert CommandRegistry.instance().command_names == []


def test_decorator_attaches_metadata():
    @protocol_command("meta")
    def meta(context, x: str) -> None:
        pass

    assert meta._protocol_command_name == "meta"
    assert meta._protocol_schema is not None


# ─── Schema generation ───────────────────────────────────────────────────────


def test_schema_generated_with_correct_fields():
    def sample(context, instrument: str, position: str) -> None:
        pass

    schema = _build_schema_from_signature("sample", sample)
    fields = set(schema.model_fields.keys())
    assert fields == {"instrument", "position"}


def test_schema_skips_context_and_self():
    def method(self, context, value: int) -> None:
        pass

    schema = _build_schema_from_signature("method", method)
    assert set(schema.model_fields.keys()) == {"value"}


def test_schema_forbids_extra_fields():
    def cmd(context, a: str) -> None:
        pass

    schema = _build_schema_from_signature("cmd", cmd)
    with pytest.raises(ValidationError, match="Extra inputs"):
        schema.model_validate({"a": "ok", "b": "extra"})


def test_schema_requires_all_parameters():
    def cmd(context, a: str, b: int) -> None:
        pass

    schema = _build_schema_from_signature("cmd", cmd)
    with pytest.raises(ValidationError):
        schema.model_validate({"a": "only_a"})


def test_schema_respects_default_values():
    def cmd(context, a: str, b: float = 50.0) -> None:
        pass

    schema = _build_schema_from_signature("cmd", cmd)
    result = schema.model_validate({"a": "hello"})
    assert result.a == "hello"
    assert result.b == 50.0


def test_schema_validates_successfully_with_all_fields():
    def cmd(context, instrument: str, position: str) -> None:
        pass

    schema = _build_schema_from_signature("cmd", cmd)
    result = schema.model_validate({"instrument": "pipette", "position": "plate_1.A1"})
    assert result.instrument == "pipette"
    assert result.position == "plate_1.A1"
