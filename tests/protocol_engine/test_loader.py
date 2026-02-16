"""Tests for protocol YAML loading and compilation."""

import tempfile
from pathlib import Path

import pytest

from src.protocol_engine.errors import ProtocolLoaderError
from src.protocol_engine.loader import load_protocol_from_yaml, load_protocol_from_yaml_safe
from src.protocol_engine.protocol import Protocol


# ─── Valid protocol YAML fixtures ─────────────────────────────────────────────

VALID_SINGLE_MOVE = """
protocol:
  - move:
      instrument: pipette
      position: plate_1.A1
"""

VALID_TWO_MOVES = """
protocol:
  - move:
      instrument: pipette
      position: plate_1.A1
  - move:
      instrument: pipette
      position: plate_1.C9
"""


def _write_yaml(content: str) -> str:
    """Write YAML content to a temp file and return its path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(content)
    f.close()
    return f.name


# ─── Valid loading ────────────────────────────────────────────────────────────


def test_load_valid_protocol_returns_protocol():
    path = _write_yaml(VALID_SINGLE_MOVE)
    try:
        protocol = load_protocol_from_yaml(path)
        assert isinstance(protocol, Protocol)
    finally:
        Path(path).unlink(missing_ok=True)


def test_loaded_protocol_has_correct_step_count():
    path = _write_yaml(VALID_TWO_MOVES)
    try:
        protocol = load_protocol_from_yaml(path)
        assert len(protocol) == 2
    finally:
        Path(path).unlink(missing_ok=True)


def test_loaded_protocol_step_has_correct_command_name():
    path = _write_yaml(VALID_SINGLE_MOVE)
    try:
        protocol = load_protocol_from_yaml(path)
        assert protocol.steps[0].command_name == "move"
    finally:
        Path(path).unlink(missing_ok=True)


def test_loaded_protocol_step_has_correct_args():
    path = _write_yaml(VALID_SINGLE_MOVE)
    try:
        protocol = load_protocol_from_yaml(path)
        args = protocol.steps[0].args
        assert args == {"instrument": "pipette", "position": "plate_1.A1"}
    finally:
        Path(path).unlink(missing_ok=True)


def test_loaded_protocol_has_source_path():
    path = _write_yaml(VALID_SINGLE_MOVE)
    try:
        protocol = load_protocol_from_yaml(path)
        assert protocol.source_path == Path(path)
    finally:
        Path(path).unlink(missing_ok=True)


# ─── Safe loader error formatting ────────────────────────────────────────────


def test_safe_loader_unknown_command_has_clean_error():
    yaml = """
protocol:
  - unknown_cmd:
      a: b
"""
    path = _write_yaml(yaml)
    try:
        with pytest.raises(ProtocolLoaderError) as exc_info:
            load_protocol_from_yaml_safe(path)
        message = str(exc_info.value)
        assert "Protocol YAML error" in message
        assert "How to fix:" in message
    finally:
        Path(path).unlink(missing_ok=True)


def test_safe_loader_extra_args_has_clean_error():
    yaml = """
protocol:
  - move:
      instrument: pipette
      position: plate_1.A1
      extra_field: bad
"""
    path = _write_yaml(yaml)
    try:
        with pytest.raises(ProtocolLoaderError) as exc_info:
            load_protocol_from_yaml_safe(path)
        message = str(exc_info.value)
        assert "How to fix:" in message
    finally:
        Path(path).unlink(missing_ok=True)


def test_safe_loader_yaml_parse_error_has_clean_error():
    bad_yaml = "protocol:\n  - move:\n    instrument: [\n"
    path = _write_yaml(bad_yaml)
    try:
        with pytest.raises(ProtocolLoaderError) as exc_info:
            load_protocol_from_yaml_safe(path)
        message = str(exc_info.value)
        assert "parse error" in message.lower()
        assert "How to fix:" in message
    finally:
        Path(path).unlink(missing_ok=True)


def test_safe_loader_missing_file_has_clean_error():
    missing_path = "/tmp/this_protocol_does_not_exist_12345.yaml"
    with pytest.raises(ProtocolLoaderError) as exc_info:
        load_protocol_from_yaml_safe(missing_path)
    message = str(exc_info.value)
    assert "Protocol loader error" in message
    assert "How to fix:" in message


def test_empty_yaml_fails():
    path = _write_yaml("")
    try:
        with pytest.raises(Exception):
            load_protocol_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)
