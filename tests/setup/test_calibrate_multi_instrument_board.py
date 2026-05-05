"""Offline tests for setup/calibrate_multi_instrument_board.py."""

from __future__ import annotations

from pathlib import Path

import yaml

from setup.calibrate_multi_instrument_board import (
    MultiInstrumentCalibrationResult,
    compute_instrument_calibration,
    run_multi_instrument_calibration,
)


def _write_multi_gantry(path: Path) -> Path:
    path.write_text(
        """\
serial_port: /dev/ttyUSB0
cnc:
  homing_strategy: standard
  total_z_height: 100.0
  y_axis_motion: head
working_volume:
  x_min: 0.0
  x_max: 400.0
  y_min: 0.0
  y_max: 300.0
  z_min: 0.0
  z_max: 100.0
grbl_settings:
  status_report: 0
  soft_limits: true
  homing_enable: true
  max_travel_x: 400.0
  max_travel_y: 300.0
  max_travel_z: 100.0
instruments:
  left_probe:
    type: asmi
    vendor: vernier
    offset_x: 99.0
    offset_y: 99.0
    depth: 99.0
    measurement_height: 10.0
    safe_approach_height: 50.0
    offline: true
  camera:
    type: uv_curing
    vendor: excelitas
    offset_x: 1.0
    offset_y: 2.0
    depth: 3.0
    measurement_height: 20.0
    safe_approach_height: 60.0
    offline: true
""",
        encoding="utf-8",
    )
    return path


class _FakeGantry:
    instance: "_FakeGantry"

    def __init__(self, config: dict):
        self.config = config
        self.calls: list[tuple] = []
        self.coords = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.home_count = 0
        _FakeGantry.instance = self

    def connect(self) -> None:
        self.calls.append(("connect",))

    def disconnect(self) -> None:
        self.calls.append(("disconnect",))

    def home(self) -> None:
        self.calls.append(("home",))
        self.home_count += 1
        if self.home_count == 2:
            self.coords = {"x": 398.0, "y": 299.0, "z": 88.0}
        elif self.home_count >= 3:
            self.coords = {"x": 398.0, "y": 299.0, "z": 96.0}

    def move_to(self, x: float, y: float, z: float, travel_z=None) -> None:
        self.calls.append(("move_to", x, y, z, travel_z))
        self.coords = {"x": x, "y": y, "z": z}

    def clear_g92_offsets(self) -> None:
        self.calls.append(("clear_g92_offsets",))

    def enforce_work_position_reporting(self) -> None:
        self.calls.append(("enforce_work_position_reporting",))

    def activate_work_coordinate_system(self, system: str = "G54") -> None:
        self.calls.append(("activate_work_coordinate_system", system))

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

    def jog(
        self,
        x: float = 0,
        y: float = 0,
        z: float = 0,
        feed_rate: float = 2000,
    ) -> None:
        self.calls.append(("jog", x, y, z, feed_rate))
        self.coords = {
            "x": self.coords["x"] + x,
            "y": self.coords["y"] + y,
            "z": self.coords["z"] + z,
        }

    def jog_cancel(self) -> None:
        self.calls.append(("jog_cancel",))

    def stop(self) -> None:
        self.calls.append(("stop",))

    def unlock(self) -> None:
        self.calls.append(("unlock",))

    def set_serial_timeout(self, timeout: float) -> None:
        self.calls.append(("set_serial_timeout", timeout))

    def read_grbl_settings(self) -> dict[str, str]:
        self.calls.append(("read_grbl_settings",))
        return {"$20": "0"}

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


def _key_reader(keys):
    iterator = iter(keys)

    def read():
        return next(iterator)

    return read


def test_compute_instrument_calibration_inverts_board_move_math():
    calibration = compute_instrument_calibration(
        gantry_coords={"x": 90.0, "y": 120.0, "z": 30.0},
        artifact_xyz=(100.0, 125.0, 4.0),
    )

    assert calibration == {"offset_x": 10.0, "offset_y": 5.0, "depth": 26.0}


def test_dry_run_prompts_for_only_operator_choices(tmp_path):
    path = _write_multi_gantry(tmp_path / "gantry.yaml")
    inputs = iter(["", "", "100", "125", "4"])
    messages: list[str] = []

    result = run_multi_instrument_calibration(
        path,
        dry_run=True,
        output=messages.append,
        input_reader=lambda _prompt: next(inputs),
    )

    assert result is None
    assert any("Available instruments" in message for message in messages)
    assert any("Dry run only" in message for message in messages)


def test_multi_instrument_calibration_sets_xy_before_z_and_updates_yaml(tmp_path):
    path = _write_multi_gantry(tmp_path / "gantry.yaml")
    out_path = tmp_path / "calibrated.yaml"
    messages: list[str] = []

    result = run_multi_instrument_calibration(
        path,
        reference_instrument="left_probe",
        lowest_instrument="left_probe",
        artifact_xyz=(100.0, 125.0, 4.0),
        instruments_to_calibrate=("left_probe", "camera"),
        skip_soft_limit_config=False,
        output_gantry_path=out_path,
        write_gantry_yaml=True,
        output=messages.append,
        input_reader=lambda _prompt: "y",
        gantry_factory=_FakeGantry,
        key_reader=_key_reader(
            [
                ("LEFT", 2),
                ("DOWN", 1),
                ("\r", 1),  # confirm XY origin: only X/Y are zeroed
                ("Z", 3),
                ("\r", 1),  # confirm lowest instrument Z zero
                ("RIGHT", 10),
                ("UP", 5),
                ("X", 2),
                ("\r", 1),  # left_probe artifact point
                ("RIGHT", 15),
                ("UP", 7),
                ("X", 6),
                ("\r", 1),  # camera artifact point
            ]
        ),
        stdin_flusher=lambda: None,
    )

    assert isinstance(result, MultiInstrumentCalibrationResult)
    assert result.xy_origin_verification == (0.0, 0.0, 0.0)
    assert result.z_origin_verification == (398.0, 299.0, 0.0)
    assert result.measured_working_volume == (398.0, 299.0, 96.0)
    assert result.instrument_calibrations["left_probe"] == {
        "offset_x": -308.0,
        "offset_y": -179.0,
        "depth": 94.0,
    }
    assert result.instrument_calibrations["camera"] == {
        "offset_x": -323.0,
        "offset_y": -186.0,
        "depth": 100.0,
    }

    set_wpos_calls = [
        call for call in _FakeGantry.instance.calls if call[0] == "set_work_coordinates"
    ]
    assert set_wpos_calls[0] == ("set_work_coordinates", 0.0, 0.0, None)
    assert set_wpos_calls[1] == ("set_work_coordinates", None, None, 0.0)

    written = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert written["working_volume"] == {
        "x_min": 0.0,
        "x_max": 398.0,
        "y_min": 0.0,
        "y_max": 299.0,
        "z_min": 0.0,
        "z_max": 96.0,
    }
    assert written["cnc"]["total_z_height"] == 96.0
    assert written["grbl_settings"]["max_travel_x"] == 398.0
    assert written["grbl_settings"]["max_travel_y"] == 299.0
    assert written["grbl_settings"]["max_travel_z"] == 96.0
    assert written["instruments"]["camera"]["measurement_height"] == 20.0
    assert written["instruments"]["camera"]["offset_x"] == -323.0
    assert written["instruments"]["camera"]["offset_y"] == -186.0
    assert written["instruments"]["camera"]["depth"] == 100.0
    assert not [call for call in _FakeGantry.instance.calls if call[0] == "move_to"]
