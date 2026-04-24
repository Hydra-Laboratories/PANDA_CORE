"""Offline tests for setup/calibrate_deck_origin.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from setup.calibrate_deck_origin import (
    DeckOriginCalibrationResult,
    run_calibration,
)


def _write_gantry(path: Path, *, x_min: float = 0.0) -> Path:
    path.write_text(
        f"""\
serial_port: /dev/ttyUSB0
cnc:
  homing_strategy: standard
  total_z_height: 100.0
  y_axis_motion: head
  structure_clearance_z: 85.0
working_volume:
  x_min: {x_min}
  x_max: 400.0
  y_min: 0.0
  y_max: 300.0
  z_min: 0.0
  z_max: 100.0
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
            self.coords = {"x": 398.5, "y": 299.25, "z": 96.75}

    def clear_g92_offsets(self) -> None:
        self.calls.append(("clear_g92_offsets",))

    def set_work_coordinates(self, x: float, y: float, z: float) -> None:
        self.calls.append(("set_work_coordinates", x, y, z))
        self.coords = {"x": x, "y": y, "z": z}

    def get_coordinates(self) -> dict[str, float]:
        self.calls.append(("get_coordinates",))
        return self.coords

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


class _LimitRecoveringFakeGantry(_FakeGantry):
    def __init__(self, config: dict):
        super().__init__(config)
        self.fail_next_jog = True
        self.fail_next_recovery_readback = False

    def jog(
        self,
        x: float = 0,
        y: float = 0,
        z: float = 0,
        feed_rate: float = 2000,
    ) -> None:
        if self.fail_next_jog:
            self.fail_next_jog = False
            self.calls.append(("jog", x, y, z, feed_rate))
            raise RuntimeError("Alarm in status: <Alarm|WPos:0,0,0|Pn:Y>")
        super().jog(x=x, y=y, z=z, feed_rate=feed_rate)

    def get_coordinates(self) -> dict[str, float]:
        if self.fail_next_recovery_readback:
            self.fail_next_recovery_readback = False
            self.calls.append(("get_coordinates_failed",))
            raise RuntimeError("")
        return super().get_coordinates()


class _LimitRecoveringNoReadbackFakeGantry(_LimitRecoveringFakeGantry):
    def __init__(self, config: dict):
        super().__init__(config)
        self.fail_next_recovery_readback = True


def _key_reader(keys):
    iterator = iter(keys)

    def read():
        return next(iterator)

    return read


def test_run_calibration_jogs_origin_zeroes_wpos_and_measures_home(tmp_path):
    path = _write_gantry(tmp_path / "gantry.yaml")
    messages: list[str] = []

    result = run_calibration(
        path,
        output=messages.append,
        gantry_factory=_FakeGantry,
        key_reader=_key_reader(
            [
                ("LEFT", 1),
                ("DOWN", 2),
                ("Z", 3),
                ("\r", 1),
            ]
        ),
        stdin_flusher=lambda: None,
    )

    assert isinstance(result, DeckOriginCalibrationResult)
    assert result.reference_verification == (0.0, 0.0, 0.0)
    assert result.reference_surface_z_mm == 0.0
    assert result.reachable_z_min_mm is None
    assert result.measured_working_volume == (398.5, 299.25, 96.75)
    assert result.plan.origin_wpos == (0.0, 0.0, 0.0)
    assert _FakeGantry.instance.calls == [
        ("connect",),
        ("set_serial_timeout", 10.0),
        ("home",),
        ("set_serial_timeout", 1.0),
        ("clear_g92_offsets",),
        ("jog", -1.0, 0.0, 0.0, 800.0),
        ("get_coordinates",),
        ("jog", 0.0, -2.0, 0.0, 800.0),
        ("get_coordinates",),
        ("jog", 0.0, 0.0, -3.0, 800.0),
        ("get_coordinates",),
        ("get_coordinates",),
        ("set_work_coordinates", 0.0, 0.0, 0.0),
        ("get_coordinates",),
        ("set_serial_timeout", 10.0),
        ("home",),
        ("set_serial_timeout", 1.0),
        ("get_coordinates",),
        ("set_serial_timeout", 0.05),
        ("disconnect",),
    ]
    assert any("Z=0 mm surface" in message for message in messages)
    assert any("Measured physical working volume" in message for message in messages)


def test_run_calibration_assigns_known_artifact_height_to_reference_z(tmp_path):
    path = _write_gantry(tmp_path / "gantry.yaml")
    messages: list[str] = []

    result = run_calibration(
        path,
        output=messages.append,
        gantry_factory=_FakeGantry,
        key_reader=_key_reader([("\r", 1)]),
        stdin_flusher=lambda: None,
        reference_surface_z_mm=43.0,
    )

    assert isinstance(result, DeckOriginCalibrationResult)
    assert result.reference_verification == (0.0, 0.0, 43.0)
    assert result.reference_surface_z_mm == 43.0
    assert result.reachable_z_min_mm is None
    assert ("set_work_coordinates", 0.0, 0.0, 43.0) in _FakeGantry.instance.calls
    assert any("Z=43 mm surface" in message for message in messages)


def test_run_calibration_prompts_for_reference_height_when_omitted(tmp_path):
    path = _write_gantry(tmp_path / "gantry.yaml")
    prompts: list[str] = []

    def input_reader(prompt: str) -> str:
        prompts.append(prompt)
        return "12.5"

    result = run_calibration(
        path,
        output=lambda message: None,
        input_reader=input_reader,
        gantry_factory=_FakeGantry,
        key_reader=_key_reader([("\r", 1)]),
        stdin_flusher=lambda: None,
        reference_surface_z_mm=None,
    )

    assert isinstance(result, DeckOriginCalibrationResult)
    assert result.reference_verification == (0.0, 0.0, 12.5)
    assert prompts == ["Reference surface Z height in mm: "]


def test_run_calibration_records_optional_lowest_reachable_z(tmp_path):
    path = _write_gantry(tmp_path / "gantry.yaml")
    messages: list[str] = []

    result = run_calibration(
        path,
        output=messages.append,
        gantry_factory=_FakeGantry,
        key_reader=_key_reader(
            [
                ("\r", 1),  # confirm 43 mm artifact/reference surface
                ("Z", 10),  # lower 10 mm from the known surface
                ("\r", 1),
            ]
        ),
        stdin_flusher=lambda: None,
        reference_surface_z_mm=43.0,
        measure_reachable_z_min=True,
    )

    assert isinstance(result, DeckOriginCalibrationResult)
    assert result.reference_verification == (0.0, 0.0, 43.0)
    assert result.reachable_z_min_mm == pytest.approx(33.0)
    assert ("jog", 0.0, 0.0, -10.0, 800.0) in _FakeGantry.instance.calls
    assert any("Optional reachable-Z measurement" in message for message in messages)
    assert any("reference_tcp_reachable_z_min: 33.000" in message for message in messages)


def test_run_calibration_recovers_from_limit_alarm_during_jog(tmp_path):
    path = _write_gantry(tmp_path / "gantry.yaml")
    messages: list[str] = []

    result = run_calibration(
        path,
        output=messages.append,
        gantry_factory=_LimitRecoveringFakeGantry,
        key_reader=_key_reader(
            [
                ("DOWN", 1),
                ("DOWN", 1),
                ("\r", 1),
            ]
        ),
        stdin_flusher=lambda: None,
        limit_pull_off_mm=2.0,
    )

    assert isinstance(result, DeckOriginCalibrationResult)
    assert (
        ("jog", 0.0, -1.0, 0.0, 800.0)
        in _LimitRecoveringFakeGantry.instance.calls
    )
    assert ("jog_cancel",) in _LimitRecoveringFakeGantry.instance.calls
    assert ("unlock",) in _LimitRecoveringFakeGantry.instance.calls
    assert (
        ("jog", 0.0, 2.0, 0.0, 800.0)
        in _LimitRecoveringFakeGantry.instance.calls
    )
    assert any("Limit alarm detected" in message for message in messages)


def test_run_calibration_continues_when_recovery_readback_is_unavailable(tmp_path):
    path = _write_gantry(tmp_path / "gantry.yaml")
    messages: list[str] = []

    result = run_calibration(
        path,
        output=messages.append,
        gantry_factory=_LimitRecoveringNoReadbackFakeGantry,
        key_reader=_key_reader(
            [
                ("DOWN", 1),
                ("DOWN", 1),
                ("\r", 1),
            ]
        ),
        stdin_flusher=lambda: None,
        limit_pull_off_mm=2.0,
    )

    assert isinstance(result, DeckOriginCalibrationResult)
    assert ("get_coordinates_failed",) in (
        _LimitRecoveringNoReadbackFakeGantry.instance.calls
    )
    assert any("WPos readback is not available" in message for message in messages)


def test_dry_run_prints_commands_without_connecting(tmp_path):
    path = _write_gantry(tmp_path / "gantry.yaml")
    messages: list[str] = []

    def fail_factory(**kwargs):
        raise AssertionError("dry run should not construct a gantry")

    run_calibration(
        path,
        dry_run=True,
        output=messages.append,
        gantry_factory=fail_factory,
    )

    assert "  $H" in messages
    assert "  G92.1" in messages
    assert "  <interactive jog to front-left XY/known Z reference surface>" in messages
    assert "  G10 L20 P1 X0 Y0 Z0" in messages
    assert "No configured max travel values will be trusted as measured volume." in messages


def test_dry_run_prints_optional_lowest_reachable_z_step(tmp_path):
    path = _write_gantry(tmp_path / "gantry.yaml")
    messages: list[str] = []

    run_calibration(
        path,
        dry_run=True,
        output=messages.append,
        measure_reachable_z_min=True,
    )

    assert "  <optional jog to lowest safe reachable Z for this TCP>" in messages
    assert any("per-instrument lower bound" in message for message in messages)


def test_rejects_legacy_negative_space_config(tmp_path):
    path = _write_gantry(tmp_path / "legacy.yaml", x_min=-400.0)

    with pytest.raises(ValueError, match="Deck-origin calibration requires"):
        run_calibration(path, dry_run=True)
