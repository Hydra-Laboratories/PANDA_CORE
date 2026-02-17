"""Tests for MachineConfig and WorkingVolume domain models."""

from __future__ import annotations

from src.machine.machine_config import MachineConfig, WorkingVolume


def _make_volume(
    x_min: float = -300.0,
    x_max: float = 0.0,
    y_min: float = -200.0,
    y_max: float = 0.0,
    z_min: float = -80.0,
    z_max: float = 0.0,
) -> WorkingVolume:
    return WorkingVolume(
        x_min=x_min, x_max=x_max,
        y_min=y_min, y_max=y_max,
        z_min=z_min, z_max=z_max,
    )


class TestWorkingVolume:

    def test_contains_interior_point(self):
        vol = _make_volume()
        assert vol.contains(-150.0, -100.0, -40.0) is True

    def test_contains_point_on_min_boundary(self):
        vol = _make_volume()
        assert vol.contains(-300.0, -200.0, -80.0) is True

    def test_contains_point_on_max_boundary(self):
        vol = _make_volume()
        assert vol.contains(0.0, 0.0, 0.0) is True

    def test_contains_point_on_mixed_boundaries(self):
        vol = _make_volume()
        assert vol.contains(-300.0, 0.0, -40.0) is True

    def test_rejects_point_beyond_x_min(self):
        vol = _make_volume()
        assert vol.contains(-300.001, -100.0, -40.0) is False

    def test_rejects_point_beyond_x_max(self):
        vol = _make_volume()
        assert vol.contains(0.001, -100.0, -40.0) is False

    def test_rejects_point_beyond_y_min(self):
        vol = _make_volume()
        assert vol.contains(-150.0, -200.001, -40.0) is False

    def test_rejects_point_beyond_y_max(self):
        vol = _make_volume()
        assert vol.contains(-150.0, 0.001, -40.0) is False

    def test_rejects_point_beyond_z_min(self):
        vol = _make_volume()
        assert vol.contains(-150.0, -100.0, -80.001) is False

    def test_rejects_point_beyond_z_max(self):
        vol = _make_volume()
        assert vol.contains(-150.0, -100.0, 0.001) is False

    def test_each_axis_checked_independently(self):
        vol = _make_volume()
        assert vol.contains(-150.0, -100.0, -80.001) is False
        assert vol.contains(-150.0, -200.001, -40.0) is False
        assert vol.contains(-300.001, -100.0, -40.0) is False

    def test_frozen_dataclass(self):
        vol = _make_volume()
        try:
            vol.x_min = 0.0
            assert False, "Should have raised"
        except AttributeError:
            pass


class TestMachineConfig:

    def test_stores_all_fields(self):
        vol = _make_volume()
        config = MachineConfig(
            serial_port="/dev/ttyUSB0",
            homing_strategy="xy_hard_limits",
            working_volume=vol,
        )
        assert config.serial_port == "/dev/ttyUSB0"
        assert config.homing_strategy == "xy_hard_limits"
        assert config.working_volume is vol

    def test_frozen_dataclass(self):
        config = MachineConfig(
            serial_port="/dev/ttyUSB0",
            homing_strategy="standard",
            working_volume=_make_volume(),
        )
        try:
            config.serial_port = "other"
            assert False, "Should have raised"
        except AttributeError:
            pass
