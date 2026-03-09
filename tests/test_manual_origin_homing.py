"""Tests for manual_origin homing strategy."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from gantry.gantry_config import GantryConfig, HomingStrategy, WorkingVolume
from gantry.yaml_schema import CncYaml, GantryYamlSchema
from gantry.loader import load_gantry_from_yaml


MANUAL_ORIGIN_YAML = """\
serial_port: /dev/cu.usbserial-2130
cnc:
  homing_strategy: manual_origin
  total_z_height: 90.0
working_volume:
  x_min: 0.0
  x_max: 300.0
  y_min: 0.0
  y_max: 200.0
  z_min: 0.0
  z_max: 80.0
"""


def _write_temp_yaml(content: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(content)
    f.close()
    return f.name


class TestManualOriginEnum:

    def test_manual_origin_enum_exists(self):
        assert hasattr(HomingStrategy, "MANUAL_ORIGIN")

    def test_manual_origin_enum_value(self):
        assert HomingStrategy.MANUAL_ORIGIN.value == "manual_origin"

    def test_manual_origin_constructable_from_string(self):
        strategy = HomingStrategy("manual_origin")
        assert strategy is HomingStrategy.MANUAL_ORIGIN


class TestManualOriginYamlSchema:

    def test_yaml_schema_accepts_manual_origin(self):
        schema = CncYaml(homing_strategy="manual_origin", total_z_height=90.0)
        assert schema.homing_strategy == "manual_origin"

    def test_full_yaml_schema_accepts_manual_origin(self):
        raw = {
            "serial_port": "/dev/ttyUSB0",
            "cnc": {"homing_strategy": "manual_origin", "total_z_height": 90.0},
            "working_volume": {
                "x_min": 0.0, "x_max": 300.0,
                "y_min": 0.0, "y_max": 200.0,
                "z_min": 0.0, "z_max": 80.0,
            },
        }
        schema = GantryYamlSchema.model_validate(raw)
        assert schema.cnc.homing_strategy == "manual_origin"


class TestManualOriginLoader:

    def test_load_manual_origin_yaml(self):
        path = _write_temp_yaml(MANUAL_ORIGIN_YAML)
        try:
            config = load_gantry_from_yaml(path)
            assert config.homing_strategy == HomingStrategy.MANUAL_ORIGIN
        finally:
            os.unlink(path)

    def test_load_desktop_config_file(self):
        """Load the actual Desktop config and verify manual_origin strategy."""
        from pathlib import Path

        config_path = (
            Path(__file__).parent.parent
            / "configs"
            / "gantry"
            / "genmitsu_3018_PRO_Desktop.yaml"
        )
        config = load_gantry_from_yaml(config_path)
        assert config.homing_strategy == HomingStrategy.MANUAL_ORIGIN


class TestGantryHomeDispatch:

    @patch("gantry.gantry.Mill")
    def test_home_dispatches_manual_origin(self, mock_mill_cls):
        from gantry.gantry import Gantry

        mock_mill = mock_mill_cls.return_value
        config = {"cnc": {"homing_strategy": "manual_origin"}}
        gantry = Gantry(config=config)

        gantry.home()
        mock_mill.home_manual_origin.assert_called_once()

    @patch("gantry.gantry.Mill")
    def test_home_dispatches_xy_hard_limits(self, mock_mill_cls):
        from gantry.gantry import Gantry

        mock_mill = mock_mill_cls.return_value
        config = {"cnc": {"homing_strategy": "xy_hard_limits"}}
        gantry = Gantry(config=config)

        gantry.home()
        mock_mill.home_xy_hard_limits.assert_called_once()

    @patch("gantry.gantry.Mill")
    def test_home_dispatches_standard(self, mock_mill_cls):
        from gantry.gantry import Gantry

        mock_mill = mock_mill_cls.return_value
        config = {"cnc": {"homing_strategy": "standard"}}
        gantry = Gantry(config=config)

        gantry.home()
        mock_mill.home.assert_called_once()

    @patch("gantry.gantry.Mill")
    def test_home_xy_ignores_config(self, mock_mill_cls):
        from gantry.gantry import Gantry

        mock_mill = mock_mill_cls.return_value
        config = {"cnc": {"homing_strategy": "manual_origin"}}
        gantry = Gantry(config=config)

        gantry.home_xy()
        mock_mill.home_xy_hard_limits.assert_called_once()


class TestMockMillManualOrigin:

    def test_mock_mill_home_manual_origin_sets_homed(self):
        from gantry.gantry_driver.mock import MockMill

        mill = MockMill()
        assert mill.homed is False
        mill.home_manual_origin()
        assert mill.homed is True
