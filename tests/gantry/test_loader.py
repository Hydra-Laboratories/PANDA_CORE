"""Tests for gantry YAML loader."""

from __future__ import annotations

import os
import tempfile

import pytest

from src.gantry.errors import GantryLoaderError
from src.gantry.gantry_config import GantryConfig
from src.gantry.loader import load_gantry_from_yaml, load_gantry_from_yaml_safe


VALID_GANTRY_YAML = """\
serial_port: /dev/cu.usbserial-2130
cnc:
  homing_strategy: xy_hard_limits
working_volume:
  x_min: -300.0
  x_max: 0.0
  y_min: -200.0
  y_max: 0.0
  z_min: -80.0
  z_max: 0.0
"""


def _write_temp_yaml(content: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(content)
    f.close()
    return f.name


class TestLoadGantryFromYaml:

    def test_load_valid_gantry_returns_gantry_config(self):
        path = _write_temp_yaml(VALID_GANTRY_YAML)
        try:
            result = load_gantry_from_yaml(path)
            assert isinstance(result, GantryConfig)
        finally:
            os.unlink(path)

    def test_loaded_gantry_has_correct_bounds(self):
        path = _write_temp_yaml(VALID_GANTRY_YAML)
        try:
            config = load_gantry_from_yaml(path)
            vol = config.working_volume
            assert vol.x_min == -300.0
            assert vol.x_max == 0.0
            assert vol.y_min == -200.0
            assert vol.y_max == 0.0
            assert vol.z_min == -80.0
            assert vol.z_max == 0.0
        finally:
            os.unlink(path)

    def test_loaded_gantry_has_serial_port(self):
        path = _write_temp_yaml(VALID_GANTRY_YAML)
        try:
            config = load_gantry_from_yaml(path)
            assert config.serial_port == "/dev/cu.usbserial-2130"
        finally:
            os.unlink(path)

    def test_loaded_gantry_has_homing_strategy(self):
        path = _write_temp_yaml(VALID_GANTRY_YAML)
        try:
            config = load_gantry_from_yaml(path)
            assert config.homing_strategy == "xy_hard_limits"
        finally:
            os.unlink(path)

    def test_missing_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_gantry_from_yaml("/nonexistent/path.yaml")

    def test_invalid_yaml_raises(self):
        path = _write_temp_yaml("{{invalid yaml: [")
        try:
            with pytest.raises(Exception):
                load_gantry_from_yaml(path)
        finally:
            os.unlink(path)

    def test_missing_working_volume_raises_validation_error(self):
        yaml_content = """\
serial_port: /dev/ttyUSB0
cnc:
  homing_strategy: standard
"""
        path = _write_temp_yaml(yaml_content)
        try:
            with pytest.raises(Exception, match="working_volume"):
                load_gantry_from_yaml(path)
        finally:
            os.unlink(path)

    def test_reversed_bounds_raises_validation_error(self):
        yaml_content = """\
serial_port: /dev/ttyUSB0
cnc:
  homing_strategy: standard
working_volume:
  x_min: 0.0
  x_max: -300.0
  y_min: -200.0
  y_max: 0.0
  z_min: -80.0
  z_max: 0.0
"""
        path = _write_temp_yaml(yaml_content)
        try:
            with pytest.raises(Exception, match="x_min"):
                load_gantry_from_yaml(path)
        finally:
            os.unlink(path)

    def test_extra_top_level_key_raises(self):
        yaml_content = VALID_GANTRY_YAML + "extra_key: value\n"
        path = _write_temp_yaml(yaml_content)
        try:
            with pytest.raises(Exception):
                load_gantry_from_yaml(path)
        finally:
            os.unlink(path)

    def test_empty_file_raises(self):
        path = _write_temp_yaml("")
        try:
            with pytest.raises(Exception):
                load_gantry_from_yaml(path)
        finally:
            os.unlink(path)


class TestLoadGantryFromYamlSafe:

    def test_safe_returns_gantry_config_on_valid_yaml(self):
        path = _write_temp_yaml(VALID_GANTRY_YAML)
        try:
            result = load_gantry_from_yaml_safe(path)
            assert isinstance(result, GantryConfig)
        finally:
            os.unlink(path)

    def test_safe_wraps_validation_error_in_gantry_loader_error(self):
        yaml_content = """\
serial_port: /dev/ttyUSB0
cnc:
  homing_strategy: standard
"""
        path = _write_temp_yaml(yaml_content)
        try:
            with pytest.raises(GantryLoaderError):
                load_gantry_from_yaml_safe(path)
        finally:
            os.unlink(path)

    def test_safe_wraps_file_not_found_in_gantry_loader_error(self):
        with pytest.raises(GantryLoaderError):
            load_gantry_from_yaml_safe("/nonexistent/path.yaml")

    def test_safe_error_has_how_to_fix_guidance(self):
        yaml_content = """\
serial_port: /dev/ttyUSB0
cnc:
  homing_strategy: standard
"""
        path = _write_temp_yaml(yaml_content)
        try:
            with pytest.raises(GantryLoaderError, match="How to fix"):
                load_gantry_from_yaml_safe(path)
        finally:
            os.unlink(path)

    def test_safe_wraps_yaml_parse_error(self):
        path = _write_temp_yaml("{{bad yaml")
        try:
            with pytest.raises(GantryLoaderError, match="How to fix"):
                load_gantry_from_yaml_safe(path)
        finally:
            os.unlink(path)
