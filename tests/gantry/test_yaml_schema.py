"""Tests for gantry YAML schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gantry.yaml_schema import GantryYamlSchema


def _valid_gantry_dict() -> dict:
    return {
        "serial_port": "/dev/cu.usbserial-2130",
        "cnc": {"homing_strategy": "standard", "total_z_height": 90.0},
        "working_volume": {
            "x_min": 0.0,
            "x_max": 300.0,
            "y_min": 0.0,
            "y_max": 200.0,
            "z_min": 0.0,
            "z_max": 80.0,
        },
    }


class TestGantryYamlSchema:

    def test_valid_gantry_yaml_parses_all_fields(self):
        data = _valid_gantry_dict()
        schema = GantryYamlSchema.model_validate(data)

        assert schema.serial_port == "/dev/cu.usbserial-2130"
        assert schema.cnc.homing_strategy == "standard"
        assert schema.cnc.total_z_height == 90.0
        assert schema.working_volume.x_min == 0.0
        assert schema.working_volume.x_max == 300.0
        assert schema.working_volume.y_min == 0.0
        assert schema.working_volume.y_max == 200.0
        assert schema.working_volume.z_min == 0.0
        assert schema.working_volume.z_max == 80.0

    def test_only_standard_homing_strategy_accepted(self):
        data = _valid_gantry_dict()
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
        data["working_volume"]["x_min"] = 300.0
        data["working_volume"]["x_max"] = 0.0
        with pytest.raises(ValidationError, match="x_min"):
            GantryYamlSchema.model_validate(data)

    def test_y_min_ge_y_max_raises(self):
        data = _valid_gantry_dict()
        data["working_volume"]["y_min"] = 200.0
        data["working_volume"]["y_max"] = 0.0
        with pytest.raises(ValidationError, match="y_min"):
            GantryYamlSchema.model_validate(data)

    def test_z_min_ge_z_max_raises(self):
        data = _valid_gantry_dict()
        data["working_volume"]["z_min"] = 80.0
        data["working_volume"]["z_max"] = 0.0
        with pytest.raises(ValidationError, match="z_min"):
            GantryYamlSchema.model_validate(data)

    def test_equal_min_and_max_raises(self):
        data = _valid_gantry_dict()
        data["working_volume"]["x_min"] = 0.0
        data["working_volume"]["x_max"] = 0.0
        with pytest.raises(ValidationError, match="x_min"):
            GantryYamlSchema.model_validate(data)

    def test_missing_total_z_height_raises(self):
        data = _valid_gantry_dict()
        del data["cnc"]["total_z_height"]
        with pytest.raises(ValidationError, match="total_z_height"):
            GantryYamlSchema.model_validate(data)

    def test_total_z_height_must_be_positive(self):
        data = _valid_gantry_dict()
        data["cnc"]["total_z_height"] = 0.0
        with pytest.raises(ValidationError, match="total_z_height"):
            GantryYamlSchema.model_validate(data)

    def test_total_z_height_must_cover_working_z_max(self):
        data = _valid_gantry_dict()
        data["cnc"]["total_z_height"] = 79.9
        with pytest.raises(ValidationError, match="total_z_height"):
            GantryYamlSchema.model_validate(data)

    def test_safe_z_is_optional_and_parsed(self):
        data = _valid_gantry_dict()
        data["cnc"]["safe_z"] = 75.0
        schema = GantryYamlSchema.model_validate(data)
        assert schema.cnc.safe_z == 75.0
        assert schema.safe_z == 75.0

    def test_safe_z_defaults_to_z_max_when_omitted(self):
        data = _valid_gantry_dict()
        schema = GantryYamlSchema.model_validate(data)
        assert schema.cnc.safe_z is None
        assert schema.safe_z == schema.working_volume.z_max

    def test_safe_z_above_z_max_rejected(self):
        data = _valid_gantry_dict()
        data["cnc"]["safe_z"] = data["working_volume"]["z_max"] + 1.0
        with pytest.raises(ValidationError, match="safe_z"):
            GantryYamlSchema.model_validate(data)

    def test_safe_z_below_z_min_rejected(self):
        data = _valid_gantry_dict()
        data["cnc"]["safe_z"] = data["working_volume"]["z_min"] - 1.0
        with pytest.raises(ValidationError, match="safe_z"):
            GantryYamlSchema.model_validate(data)

    def test_old_structure_clearance_z_field_rejected(self):
        data = _valid_gantry_dict()
        data["cnc"]["structure_clearance_z"] = 75.0
        with pytest.raises(ValidationError):
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

    def test_instruments_are_parsed_when_present(self):
        data = _valid_gantry_dict()
        data["instruments"] = {
            "asmi": {
                "type": "asmi",
                "vendor": "vernier",
                "sensor_channels": [1],
            }
        }
        schema = GantryYamlSchema.model_validate(data)
        assert schema.instruments["asmi"].type == "asmi"
        assert schema.instruments["asmi"].model_extra["sensor_channels"] == [1]

    def test_instrument_measurement_height_no_longer_a_field(self):
        """`measurement_height` belongs on the protocol command, not the
        instrument config. Schema accepts it as a model_extra (no validation
        error), but `InstrumentYamlEntry` exposes no first-class attribute."""
        data = _valid_gantry_dict()
        data["instruments"] = {
            "filmetrics": {"type": "filmetrics", "vendor": "kla"},
        }
        schema = GantryYamlSchema.model_validate(data)
        assert not hasattr(schema.instruments["filmetrics"], "measurement_height")


class TestGrblSettingsYaml:

    def test_grbl_settings_optional(self):
        data = _valid_gantry_dict()
        schema = GantryYamlSchema.model_validate(data)
        assert schema.grbl_settings is None

    def test_grbl_settings_parsed(self):
        data = _valid_gantry_dict()
        data["grbl_settings"] = {
            "dir_invert_mask": 2,
            "status_report": 1,
            "max_travel_x": 300.0,
            "max_travel_y": 200.0,
            "max_travel_z": 80.0,
        }
        schema = GantryYamlSchema.model_validate(data)
        assert schema.grbl_settings.dir_invert_mask == 2
        assert schema.grbl_settings.status_report == 1
        assert schema.grbl_settings.max_travel_x == 300.0
        assert schema.grbl_settings.max_travel_y == 200.0

    def test_grbl_settings_all_fields_optional(self):
        data = _valid_gantry_dict()
        data["grbl_settings"] = {}
        schema = GantryYamlSchema.model_validate(data)
        assert schema.grbl_settings.dir_invert_mask is None
        assert schema.grbl_settings.max_travel_x is None

    def test_grbl_settings_extra_field_rejected(self):
        data = _valid_gantry_dict()
        data["grbl_settings"] = {"unknown_setting": 42}
        with pytest.raises(ValidationError):
            GantryYamlSchema.model_validate(data)

    def test_grbl_settings_boolean_fields(self):
        data = _valid_gantry_dict()
        data["grbl_settings"] = {
            "hard_limits": True,
            "soft_limits": False,
            "homing_enable": True,
        }
        schema = GantryYamlSchema.model_validate(data)
        assert schema.grbl_settings.hard_limits is True
        assert schema.grbl_settings.soft_limits is False
        assert schema.grbl_settings.homing_enable is True
