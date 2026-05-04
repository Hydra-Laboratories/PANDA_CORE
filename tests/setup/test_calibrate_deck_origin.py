"""Offline tests for setup/calibrate_deck_origin.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from gantry.gantry_driver.exceptions import CommandExecutionError, LocationNotFound
from setup.calibrate_deck_origin import (
    DeckOriginCalibrationResult,
    run_calibration,
)


def _write_gantry(path: Path, *, include_profiles: bool = True) -> Path:
    calibration_homing = ""
    if include_profiles:
        calibration_homing = """\
  calibration_homing:
    runtime_brt:
      dir_invert_mask: 1
      homing_dir_mask: 0
    origin_flb:
      dir_invert_mask: 1
      homing_dir_mask: 7
"""
    path.write_text(
        f"""\
serial_port: /dev/ttyUSB0
cnc:
  homing_strategy: standard
  total_z_height: 100.0
  y_axis_motion: head
  structure_clearance_z: 85.0
{calibration_homing}working_volume:
  x_min: 0.0
  x_max: 306.0
  y_min: 0.0
  y_max: 300.0
  z_min: 0.0
  z_max: 100.0
grbl_settings:
  dir_invert_mask: 1
  status_report: 0
  soft_limits: true
  hard_limits: true
  homing_enable: true
  homing_dir_mask: 0
  homing_pull_off: 2.0
  max_travel_x: 306.0
  max_travel_y: 300.0
  max_travel_z: 100.0
instruments:
  asmi:
    type: asmi
    vendor: vernier
    measurement_height: 26.0
    safe_approach_height: 35.0
""",
        encoding="utf-8",
    )
    return path


class _FakeGantry:
    instance: "_FakeGantry"

    physical_limits = {"x": 306.0, "y": 300.0, "z": 100.0}

    def __init__(self, config: dict):
        self.config = config
        self.calls: list[tuple] = []
        self.coords = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.settings = {
            "$3": "1",
            "$20": "1",
            "$21": "1",
            "$22": "1",
            "$23": "0",
            "$27": "2.0",
            # Deliberately stale. The calibration must not use this as X max.
            "$130": "180.0",
            "$131": "300.0",
            "$132": "100.0",
        }
        self.statuses: list[str] = []
        _FakeGantry.instance = self

    def connect(self) -> None:
        self.calls.append(("connect",))

    def disconnect(self) -> None:
        self.calls.append(("disconnect",))

    def query_raw_status(self) -> str:
        self.calls.append(("query_raw_status",))
        if self.statuses:
            return self.statuses.pop(0)
        return (
            f"<Idle|WPos:{self.coords['x']:.3f},"
            f"{self.coords['y']:.3f},{self.coords['z']:.3f}>"
        )

    def unlock(self) -> None:
        self.calls.append(("unlock",))

    def read_grbl_settings(self) -> dict[str, str]:
        self.calls.append(("read_grbl_settings",))
        return dict(self.settings)

    def set_grbl_setting(self, setting: str, value: float | int | bool) -> None:
        code = setting if setting.startswith("$") else f"${setting}"
        self.calls.append(("set_grbl_setting", code, value))
        self.settings[code] = str(int(value) if isinstance(value, bool) else value)

    def home(self) -> None:
        self.calls.append(("home", self.settings["$3"], self.settings["$23"]))
        if self.settings["$23"] == "7":
            self.coords = {"x": 0.0, "y": 0.0, "z": 0.0}
        else:
            self.coords = {
                "x": float(self.settings["$130"]),
                "y": float(self.settings["$131"]),
                "z": float(self.settings["$132"]),
            }

    def enforce_work_position_reporting(self) -> None:
        self.calls.append(("enforce_work_position_reporting",))

    def activate_work_coordinate_system(self, system: str = "G54") -> None:
        self.calls.append(("activate_work_coordinate_system", system))

    def clear_g92_offsets(self) -> None:
        self.calls.append(("clear_g92_offsets",))

    def set_work_coordinates(
        self,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
    ) -> None:
        self.calls.append(("set_work_coordinates", x, y, z))
        if x is not None:
            self.coords["x"] = x
        if y is not None:
            self.coords["y"] = y
        if z is not None:
            self.coords["z"] = z

    def get_coordinates(self) -> dict[str, float]:
        self.calls.append(("get_coordinates",))
        return dict(self.coords)

    def move_to(
        self,
        x: float,
        y: float,
        z: float,
        travel_z: float | None = None,
    ) -> None:
        self.calls.append(("move_to", x, y, z, travel_z))
        for axis, value in {"x": x, "y": y, "z": z}.items():
            if value > self.physical_limits[axis]:
                raise CommandExecutionError(f"alarm: hard limit {axis}")
        self.coords = {"x": x, "y": y, "z": z}

    def jog(
        self,
        x: float = 0,
        y: float = 0,
        z: float = 0,
        feed_rate: float = 2000,
    ) -> None:
        self.calls.append(("jog", x, y, z, feed_rate))
        target = {
            "x": self.coords["x"] + x,
            "y": self.coords["y"] + y,
            "z": self.coords["z"] + z,
        }
        for axis, value in target.items():
            if value > self.physical_limits[axis]:
                raise CommandExecutionError(f"alarm: hard limit {axis}")
            if value < -0.001:
                raise CommandExecutionError(f"error:15 {axis}")
        self.coords = target

    def jog_cancel(self) -> None:
        self.calls.append(("jog_cancel",))

    def set_serial_timeout(self, timeout: float) -> None:
        self.calls.append(("set_serial_timeout", timeout))

    def configure_soft_limits_from_spans(
        self,
        *,
        max_travel_x: float,
        max_travel_y: float,
        max_travel_z: float,
        tolerance_mm: float = 0.001,
    ) -> None:
        self.calls.append(
            (
                "configure_soft_limits_from_spans",
                max_travel_x,
                max_travel_y,
                max_travel_z,
                tolerance_mm,
            )
        )
        self.settings["$130"] = str(max_travel_x)
        self.settings["$131"] = str(max_travel_y)
        self.settings["$132"] = str(max_travel_z)
        self.settings["$20"] = "1"
        self.settings["$22"] = "1"


class _StartupAlarmFakeGantry(_FakeGantry):
    def __init__(self, config: dict):
        super().__init__(config)
        self.statuses = [
            "<Alarm|WPos:0.000,0.000,0.000|Pn:X>",
            "<Idle|WPos:0.000,0.000,0.000>",
        ]


class _FailAfterFlbZeroFakeGantry(_FakeGantry):
    def set_work_coordinates(
        self,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
    ) -> None:
        super().set_work_coordinates(x=x, y=y, z=z)
        if x == 0.0 and y == 0.0 and z == 0.0:
            raise CommandExecutionError("G-code rejected: error:9")


class _TransientRecoveryReadFailureFakeGantry(_FakeGantry):
    def __init__(self, config: dict):
        super().__init__(config)
        self._limit_alarm_pending = False
        self._fail_next_recovery_read = False

    def jog(
        self,
        x: float = 0,
        y: float = 0,
        z: float = 0,
        feed_rate: float = 2000,
    ) -> None:
        target = {
            "x": self.coords["x"] + x,
            "y": self.coords["y"] + y,
            "z": self.coords["z"] + z,
        }
        if any(target[axis] > self.physical_limits[axis] for axis in target):
            self._limit_alarm_pending = True
            return super().jog(x=x, y=y, z=z, feed_rate=feed_rate)
        super().jog(x=x, y=y, z=z, feed_rate=feed_rate)
        if self._limit_alarm_pending and (x < 0 or y < 0 or z < 0):
            self._limit_alarm_pending = False
            self._fail_next_recovery_read = True

    def get_coordinates(self) -> dict[str, float]:
        if self._fail_next_recovery_read:
            self._fail_next_recovery_read = False
            raise LocationNotFound()
        return super().get_coordinates()


def _key_reader(keys):
    iterator = iter(keys)

    def read():
        return next(iterator)

    return read


def _responses(values):
    iterator = iter(values)

    def read(_prompt: str) -> str:
        return next(iterator)

    return read


def test_run_calibration_estimates_bounds_without_brt_home(tmp_path):
    path = _write_gantry(tmp_path / "gantry.yaml")
    messages: list[str] = []

    result = run_calibration(
        path,
        "asmi",
        output=messages.append,
        input_reader=_responses(["y", "", "y", "n"]),
        gantry_factory=_FakeGantry,
        key_reader=_key_reader(
            [
                ("\r", 1),       # known XY reference at estimated center
                ("Z", 10),       # deck touch / lower reach
                ("\r", 1),
                ("LEFT", 50),    # left X reach
                ("\r", 1),
                ("RIGHT", 100),  # right X reach
                ("\r", 1),
            ]
        ),
        stdin_flusher=lambda: None,
    )

    assert isinstance(result, DeckOriginCalibrationResult)
    assert result.measured_working_volume == (304.0, 298.0, 98.0)
    assert result.grbl_max_travel == (304.0, 298.0, 98.0)
    assert result.instrument_name == "asmi"
    assert result.instrument_calibration is not None
    assert result.instrument_calibration.offset_x == pytest.approx(0.0)
    assert result.instrument_calibration.offset_y == pytest.approx(0.0)
    assert result.instrument_calibration.depth == pytest.approx(88.0)
    assert result.instrument_calibration.reach_limits["gantry_x_min"] == pytest.approx(102.0)
    assert result.instrument_calibration.reach_limits["gantry_x_max"] == pytest.approx(202.0)
    assert result.instrument_calibration.reach_limits["tcp_z_min"] == 0.0

    calls = _FakeGantry.instance.calls
    assert ("set_grbl_setting", "$3", 1) in calls
    assert ("set_grbl_setting", "$23", 7) in calls
    assert ("home", "1", "7") in calls
    assert ("set_work_coordinates", 0.0, 0.0, 0.0) in calls
    assert ("configure_soft_limits_from_spans", 304.0, 298.0, 98.0, 0.25) in calls
    assert ("set_grbl_setting", "$23", 0) in calls
    assert ("home", "1", "0") not in calls
    assert any("BRT $H is not run" in message for message in messages)
    assert any("estimated BRT inspection pose" in message for message in messages)
    assert any("Full gantry YAML to copy/paste" in message for message in messages)


def test_run_calibration_unlocks_startup_alarm_before_homing(tmp_path):
    path = _write_gantry(tmp_path / "gantry.yaml")

    run_calibration(
        path,
        output=lambda message: None,
        input_reader=_responses(["y", "n"]),
        gantry_factory=_StartupAlarmFakeGantry,
        key_reader=_key_reader([]),
        stdin_flusher=lambda: None,
    )

    calls = _StartupAlarmFakeGantry.instance.calls
    assert ("unlock",) in calls
    assert calls.index(("unlock",)) < calls.index(("home", "1", "7"))


def test_limit_alarm_recovery_retries_transient_wpos_readback_failure(tmp_path):
    path = _write_gantry(tmp_path / "gantry.yaml")
    messages: list[str] = []

    result = run_calibration(
        path,
        output=messages.append,
        input_reader=_responses(["y", "n"]),
        gantry_factory=_TransientRecoveryReadFailureFakeGantry,
        key_reader=_key_reader([]),
        stdin_flusher=lambda: None,
    )

    assert result.measured_working_volume == (304.0, 298.0, 98.0)
    assert any("estimated BRT inspection pose" in message for message in messages)


def test_run_calibration_defaults_to_no_instrument_bounds_only(tmp_path):
    path = _write_gantry(tmp_path / "gantry.yaml")
    messages: list[str] = []

    result = run_calibration(
        path,
        output=messages.append,
        input_reader=_responses(["y", "n"]),
        gantry_factory=_FakeGantry,
        key_reader=_key_reader([]),
        stdin_flusher=lambda: None,
    )

    assert isinstance(result, DeckOriginCalibrationResult)
    assert result.measured_working_volume == (304.0, 298.0, 98.0)
    assert result.instrument_name is None
    assert result.instrument_calibration is None
    assert any(call[0] == "move_to" for call in _FakeGantry.instance.calls)
    assert any("No instrument supplied" in message for message in messages)


def test_run_calibration_restores_runtime_profile_and_disconnects_on_failure(tmp_path):
    path = _write_gantry(tmp_path / "gantry.yaml")

    with pytest.raises(CommandExecutionError, match="error:9"):
        run_calibration(
            path,
            "asmi",
            output=lambda message: None,
            input_reader=_responses(["y"]),
            gantry_factory=_FailAfterFlbZeroFakeGantry,
            key_reader=_key_reader([]),
            stdin_flusher=lambda: None,
        )

    calls = _FailAfterFlbZeroFakeGantry.instance.calls
    assert ("set_grbl_setting", "$3", 1) in calls
    assert ("set_grbl_setting", "$23", 0) in calls
    assert ("disconnect",) in calls
    assert calls.index(("set_grbl_setting", "$23", 0)) < calls.index(("disconnect",))


def test_run_calibration_refuses_missing_calibration_profiles(tmp_path):
    path = _write_gantry(tmp_path / "gantry.yaml", include_profiles=False)

    with pytest.raises(ValueError, match="calibration_homing"):
        run_calibration(
            path,
            output=lambda message: None,
            gantry_factory=_FakeGantry,
        )


def test_interactive_jog_refuses_to_send_out_of_bounds_move(tmp_path):
    path = _write_gantry(tmp_path / "gantry.yaml")
    messages: list[str] = []

    run_calibration(
        path,
        "asmi",
        output=messages.append,
        input_reader=_responses(["y", "", "y", "n"]),
        gantry_factory=_FakeGantry,
        key_reader=_key_reader(
            [
                ("G0 X0", 1),    # accidental typed command; ignored
                ("LEFT", 1000),  # outside estimated bounds; ignored
                ("\r", 1),
                ("\r", 1),
                ("\r", 1),
                ("RIGHT", 1),
                ("\r", 1),
            ]
        ),
        stdin_flusher=lambda: None,
    )

    assert ("jog", -1000.0, 0.0, 0.0, 600.0) not in _FakeGantry.instance.calls
    assert any("outside estimated bounds" in message for message in messages)
