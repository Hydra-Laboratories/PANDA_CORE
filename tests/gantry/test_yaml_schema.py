"""Tests for gantry YAML schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.gantry.yaml_schema import GantryYamlSchema


def _valid_gantry_dict() -> dict:
    return {
        "serial_port": "/dev/cu.usbserial-2130",
        "cnc": {"homing_strategy": "xy_hard_limits"},
        "working_volume": {
            "x_min": -300.0,
            "x_max": 0.0,
            "y_min": -200.0,
            "y_max": 0.0,
            "z_min": -80.0,
            "z_max": 0.0,
        },
    }


class TestGantryYamlSchema:

    def test_valid_gantry_yaml_parses_all_fields(self):
        data = _valid_gantry_dict()
        schema = GantryYamlSchema.model_validate(data)

        assert schema.serial_port == "/dev/cu.usbserial-2130"
        assert schema.cnc.homing_strategy == "xy_hard_limits"
        assert schema.working_volume.x_min == -300.0
        assert schema.working_volume.x_max == 0.0
        assert schema.working_volume.y_min == -200.0
        assert schema.working_volume.y_max == 0.0
        assert schema.working_volume.z_min == -80.0
        assert schema.working_volume.z_max == 0.0

    def test_standard_homing_strategy_accepted(self):
        data = _valid_gantry_dict()
        data["cnc"]["homing_strategy"] = "standard"
        schema = GantryYamlSchema.model_validate(data)
        assert schema.cnc.homing_strategy == "standard"

    def test_invalid_homing_strategy_rejected(self):
        data = _valid_gantry_dict()
        data["cnc"]["homing_strategy"] = "unknown_strategy"
        with pytest.raises(ValidationError):
            GantryYamlSchema.model_validate(data)

    def test_missing_serial_port_raises(self):
        data = _valid_gantry_dict()
        del data["serial_port"]
        with pytest.raises(ValidationError, match="serial_port"):
            GantryYamlSchema.model_validate(data)

    def test_missing_cnc_section_raises(self):
        data = _valid_gantry_dict()
        del data["cnc"]
        with pytest.raises(ValidationError, match="cnc"):
            GantryYamlSchema.model_validate(data)

    def test_missing_working_volume_raises(self):
        data = _valid_gantry_dict()
        del data["working_volume"]
        with pytest.raises(ValidationError, match="working_volume"):
            GantryYamlSchema.model_validate(data)

    @pytest.mark.parametrize("field", ["x_min", "x_max", "y_min", "y_max", "z_min", "z_max"])
    def test_missing_bound_field_raises(self, field: str):
        data = _valid_gantry_dict()
        del data["working_volume"][field]
        with pytest.raises(ValidationError):
            GantryYamlSchema.model_validate(data)

    def test_x_min_ge_x_max_raises(self):
        data = _valid_gantry_dict()
        data["working_volume"]["x_min"] = 0.0
        data["working_volume"]["x_max"] = -300.0
        with pytest.raises(ValidationError, match="x_min"):
            GantryYamlSchema.model_validate(data)

    def test_y_min_ge_y_max_raises(self):
        data = _valid_gantry_dict()
        data["working_volume"]["y_min"] = 10.0
        data["working_volume"]["y_max"] = -200.0
        with pytest.raises(ValidationError, match="y_min"):
            GantryYamlSchema.model_validate(data)

    def test_z_min_ge_z_max_raises(self):
        data = _valid_gantry_dict()
        data["working_volume"]["z_min"] = 0.0
        data["working_volume"]["z_max"] = -80.0
        with pytest.raises(ValidationError, match="z_min"):
            GantryYamlSchema.model_validate(data)

    def test_equal_min_and_max_raises(self):
        data = _valid_gantry_dict()
        data["working_volume"]["x_min"] = 0.0
        data["working_volume"]["x_max"] = 0.0
        with pytest.raises(ValidationError, match="x_min"):
            GantryYamlSchema.model_validate(data)

    def test_extra_top_level_key_rejected(self):
        data = _valid_gantry_dict()
        data["unknown_field"] = "value"
        with pytest.raises(ValidationError):
            GantryYamlSchema.model_validate(data)

    def test_extra_working_volume_key_rejected(self):
        data = _valid_gantry_dict()
        data["working_volume"]["extra_field"] = 42
        with pytest.raises(ValidationError):
            GantryYamlSchema.model_validate(data)

    def test_extra_cnc_key_rejected(self):
        data = _valid_gantry_dict()
        data["cnc"]["extra_field"] = "value"
        with pytest.raises(ValidationError):
            GantryYamlSchema.model_validate(data)
