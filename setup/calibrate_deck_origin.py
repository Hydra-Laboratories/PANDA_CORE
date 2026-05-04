"""Set FLB deck-origin WPos and move to conservative machine bounds.

This script is intentionally narrow:

1. Load one gantry YAML from the constant below.
2. Apply the explicit FLB calibration homing profile.
3. Home FLB and set G54 WPos to X0 Y0 Z0.
4. Move to the configured working-volume maxima minus a safety margin.
5. Optionally write an updated gantry YAML to a new file.

It does not calibrate instruments, restore BRT settings, or run BRT homing.
"""

from __future__ import annotations

import copy
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import yaml

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from gantry import Gantry, load_gantry_from_yaml  # noqa: E402
from gantry.gantry_config import HomingProfile  # noqa: E402
from gantry.gantry_driver.exceptions import (  # noqa: E402
    CommandExecutionError,
    LocationNotFound,
    MillConnectionError,
    StatusReturnError,
)


GANTRY_PATH = project_root / "configs/gantry/cub_xl_sterling.yaml"
BOUND_SAFETY_MARGIN_MM = 2.0
TOLERANCE_MM = 0.25
MOVE_TOLERANCE_MM = 5.0
HOMING_SERIAL_TIMEOUT_S = 10.0
MOVE_SERIAL_TIMEOUT_S = 1.0
LIMIT_PULL_OFF_MM = 2.0
RECOVERY_FEED_RATE = 200.0
RECOVERY_STATUS_RETRIES = 8
RECOVERY_STATUS_RETRY_DELAY_S = 0.25
ROLLBACK_CODES = ("$3", "$20", "$21", "$22", "$23", "$27", "$130", "$131", "$132")


@dataclass(frozen=True)
class DeckOriginCalibrationResult:
    measured_working_volume: tuple[float, float, float]
    flb_zero_verification: tuple[float, float, float]
    grbl_max_travel: tuple[float, float, float]


class _GantryLike(Protocol):
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def home(self) -> None: ...
    def enforce_work_position_reporting(self) -> None: ...
    def activate_work_coordinate_system(self, system: str = "G54") -> None: ...
    def clear_g92_offsets(self) -> None: ...
    def set_work_coordinates(
        self,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
    ) -> None: ...
    def get_coordinates(self) -> dict[str, float]: ...
    def move_to(
        self,
        x: float,
        y: float,
        z: float,
        travel_z: float | None = None,
    ) -> None: ...
    def jog(
        self,
        x: float = 0,
        y: float = 0,
        z: float = 0,
        feed_rate: float = 2000,
    ) -> None: ...
    def unlock(self) -> None: ...
    def read_grbl_settings(self) -> dict[str, str]: ...
    def set_grbl_setting(self, setting: str, value: float | int | bool) -> None: ...


def _load_raw_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Gantry config is empty or invalid: {path}")
    return config


def _round_mm(value: float) -> float:
    return round(float(value), 3)


def _coords_tuple(coords: dict[str, float]) -> tuple[float, float, float]:
    return (float(coords["x"]), float(coords["y"]), float(coords["z"]))


def _parse_setting_float(settings: dict[str, str], code: str) -> float | None:
    raw = settings.get(code)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _require_profile(raw_config: dict[str, Any], name: str) -> HomingProfile:
    calibration = raw_config.get("cnc", {}).get("calibration_homing")
    if not isinstance(calibration, dict):
        raise ValueError(
            "Gantry YAML must define cnc.calibration_homing.runtime_brt and "
            "cnc.calibration_homing.origin_flb. The script will not infer $3 or $23."
        )
    raw_profile = calibration.get(name)
    if not isinstance(raw_profile, dict):
        raise ValueError(
            f"Gantry YAML must define cnc.calibration_homing.{name}. "
            "The script will not infer $3 or $23."
        )
    return HomingProfile(
        dir_invert_mask=int(raw_profile["dir_invert_mask"]),
        homing_dir_mask=int(raw_profile["homing_dir_mask"]),
    )


def _query_raw_status(gantry: _GantryLike) -> str:
    query = getattr(gantry, "query_raw_status", None)
    if callable(query):
        return str(query())
    getter = getattr(gantry, "get_status", None)
    if callable(getter):
        return str(getter())
    return ""


def _set_serial_timeout(gantry: _GantryLike, timeout_s: float) -> None:
    setter = getattr(gantry, "set_serial_timeout", None)
    if callable(setter):
        setter(timeout_s)


def _assert_near_xyz(
    coords: dict[str, float],
    *,
    expected: dict[str, float],
    tolerance_mm: float,
    label: str,
) -> None:
    misses = [
        f"{axis}: got {float(coords[axis]):.4f}, expected {float(expected[axis]):.4f}"
        for axis in ("x", "y", "z")
        if abs(float(coords[axis]) - float(expected[axis])) > tolerance_mm
    ]
    if misses:
        raise RuntimeError(
            f"{label} did not verify within {tolerance_mm} mm: "
            + "; ".join(misses)
        )


def _looks_like_limit_alarm(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        token in message
        for token in ("alarm", "check limits", "hard limit", "limit", "pn:", "error:9")
    )


def _restore_setting(
    gantry: _GantryLike,
    live_settings: dict[str, str],
    code: str,
    output: Callable[[str], None],
) -> None:
    if code not in live_settings:
        return
    value = live_settings[code]
    output(f"Restoring original setting {code}={value}.")
    gantry.set_grbl_setting(code, float(value))


def _unlock_startup_alarm_if_needed(
    gantry: _GantryLike,
    output: Callable[[str], None],
) -> None:
    raw_status = _query_raw_status(gantry)
    if raw_status and "alarm" in raw_status.lower():
        output(f"Startup GRBL alarm captured: {raw_status}")
        output("Sending $X unlock before calibration homing.")
        gantry.unlock()
        final_status = _query_raw_status(gantry)
        if final_status and "alarm" in final_status.lower():
            raise MillConnectionError(
                f"GRBL remained in alarm after unlock; status: {final_status}"
            )


def _read_rollback_settings(
    gantry: _GantryLike,
    output: Callable[[str], None],
) -> dict[str, str]:
    settings = gantry.read_grbl_settings()
    output("Rollback GRBL settings from live controller:")
    for code in ROLLBACK_CODES:
        output(f"  {code}={settings.get(code, '<missing>')}")
    return settings


def _apply_homing_profile(
    gantry: _GantryLike,
    profile: HomingProfile,
    *,
    label: str,
    output: Callable[[str], None],
) -> None:
    output(
        f"Applying {label} homing profile: "
        f"$3={profile.dir_invert_mask}, $23={profile.homing_dir_mask}, $22=1"
    )
    try:
        gantry.set_grbl_setting("$3", profile.dir_invert_mask)
        gantry.set_grbl_setting("$23", profile.homing_dir_mask)
        gantry.set_grbl_setting("$22", 1)
    except (CommandExecutionError, StatusReturnError, MillConnectionError) as exc:
        raise CommandExecutionError(
            f"Failed to apply {label} homing profile: {exc}"
        ) from exc


def _home_flb_and_zero_wpos(
    gantry: _GantryLike,
    flb_profile: HomingProfile,
    output: Callable[[str], None],
) -> dict[str, float]:
    output("Disabling soft limits for origin setup ($20=0).")
    gantry.set_grbl_setting("$20", 0)
    _apply_homing_profile(gantry, flb_profile, label="origin_flb", output=output)

    output("Homing to FLB...")
    _set_serial_timeout(gantry, HOMING_SERIAL_TIMEOUT_S)
    gantry.home()
    _set_serial_timeout(gantry, MOVE_SERIAL_TIMEOUT_S)

    output("Activating G54 and clearing transient G92 offsets...")
    gantry.enforce_work_position_reporting()
    gantry.activate_work_coordinate_system("G54")
    gantry.clear_g92_offsets()

    output("Setting FLB home pose to G54 WPos X=0 Y=0 Z=0...")
    gantry.set_work_coordinates(x=0.0, y=0.0, z=0.0)
    coords = dict(gantry.get_coordinates())
    _assert_near_xyz(
        coords,
        expected={"x": 0.0, "y": 0.0, "z": 0.0},
        tolerance_mm=TOLERANCE_MM,
        label="FLB WPos zero",
    )
    output(f"FLB WPos zero verified: X={coords['x']:.3f} Y={coords['y']:.3f} Z={coords['z']:.3f}")
    return coords


def _configured_axis_max(raw_config: dict[str, Any], axis: str) -> float:
    working_volume = raw_config.get("working_volume")
    if not isinstance(working_volume, dict):
        raise RuntimeError("Gantry YAML must define working_volume.")
    raw = working_volume.get(f"{axis}_max")
    if raw is None:
        raise RuntimeError(f"working_volume.{axis}_max is missing from gantry YAML.")
    return float(raw)


def _estimate_bounds(
    raw_config: dict[str, Any],
    live_settings: dict[str, str],
    output: Callable[[str], None],
) -> dict[str, float]:
    bounds: dict[str, float] = {}
    for axis in ("x", "y", "z"):
        configured = _configured_axis_max(raw_config, axis)
        usable = configured - BOUND_SAFETY_MARGIN_MM
        if usable <= TOLERANCE_MM:
            raise RuntimeError(
                f"Configured {axis.upper()} max is too small for a "
                f"{BOUND_SAFETY_MARGIN_MM:g} mm safety margin: {configured:.3f}."
            )
        bounds[axis] = _round_mm(usable)
        live_code = {"x": "$130", "y": "$131", "z": "$132"}[axis]
        live = _parse_setting_float(live_settings, live_code)
        if live is not None and abs(live - configured) > MOVE_TOLERANCE_MM:
            output(
                f"Note: live {live_code}={live:.3f} differs from YAML "
                f"working_volume.{axis}_max={configured:.3f}; using YAML minus margin."
            )
    return bounds


def _recover_limit_alarm(
    gantry: _GantryLike,
    delta: dict[str, float],
    output: Callable[[str], None],
) -> None:
    pull_off = {"x": 0.0, "y": 0.0, "z": 0.0}
    for axis, value in delta.items():
        if value > 0:
            pull_off[axis] = -LIMIT_PULL_OFF_MM
        elif value < 0:
            pull_off[axis] = LIMIT_PULL_OFF_MM

    output(
        "Limit alarm detected. Unlocking GRBL and pulling off the switch "
        f"by {LIMIT_PULL_OFF_MM:g} mm."
    )
    hard_limits_disabled = False
    try:
        gantry.unlock()
        output("Temporarily disabling hard limits for pull-off ($21=0).")
        gantry.set_grbl_setting("$21", 0)
        hard_limits_disabled = True
        gantry.unlock()
        gantry.jog(feed_rate=RECOVERY_FEED_RATE, **pull_off)
    finally:
        if hard_limits_disabled:
            output("Re-enabling hard-limit alarms ($21=1).")
            gantry.set_grbl_setting("$21", 1)

    last_error: Exception | None = None
    for attempt in range(1, RECOVERY_STATUS_RETRIES + 1):
        raw_status = _query_raw_status(gantry)
        if raw_status and "alarm" in raw_status.lower():
            output(f"Controller still reports alarm after pull-off (attempt {attempt}): {raw_status}")
            gantry.unlock()
            time.sleep(RECOVERY_STATUS_RETRY_DELAY_S)
            continue
        try:
            gantry.enforce_work_position_reporting()
            coords = gantry.get_coordinates()
            output(
                "Recovered after limit alarm; current WPos "
                f"X={coords['x']:.3f} Y={coords['y']:.3f} Z={coords['z']:.3f}"
            )
            return
        except (
            CommandExecutionError,
            LocationNotFound,
            StatusReturnError,
            MillConnectionError,
        ) as exc:
            last_error = exc
            output(f"WPos readback failed during limit recovery (attempt {attempt}): {exc}")
            time.sleep(RECOVERY_STATUS_RETRY_DELAY_S)
    raise RuntimeError("Could not recover a valid WPos readback after limit alarm.") from last_error


def _move_and_verify(
    gantry: _GantryLike,
    target: dict[str, float],
    *,
    label: str,
    output: Callable[[str], None],
) -> None:
    output(
        f"Moving to {label}: "
        f"X={target['x']:.3f} Y={target['y']:.3f} Z={target['z']:.3f}"
    )
    current = gantry.get_coordinates()
    delta = {
        axis: float(target[axis]) - float(current[axis])
        for axis in ("x", "y", "z")
    }
    try:
        gantry.move_to(target["x"], target["y"], target["z"])
    except (CommandExecutionError, StatusReturnError) as exc:
        if _looks_like_limit_alarm(exc):
            output(f"{label} hit a limit alarm. Recovering before abort.")
            _recover_limit_alarm(gantry, delta, output)
        raise

    coords = gantry.get_coordinates()
    overshoots = []
    for axis in ("x", "y", "z"):
        if float(coords[axis]) > float(target[axis]) + TOLERANCE_MM:
            overshoots.append(
                f"{axis.upper()} got {float(coords[axis]):.3f}, target {float(target[axis]):.3f}"
            )
    if overshoots:
        raise RuntimeError(f"{label} overshot the requested target: " + "; ".join(overshoots))
    _assert_near_xyz(
        coords,
        expected=target,
        tolerance_mm=MOVE_TOLERANCE_MM,
        label=label,
    )


def _move_to_bounds(
    gantry: _GantryLike,
    bounds: dict[str, float],
    output: Callable[[str], None],
) -> None:
    output("")
    output(
        "Moving to estimated bounds from configured working_volume maxima "
        f"minus {BOUND_SAFETY_MARGIN_MM:g} mm:"
    )
    output(f"  X={bounds['x']:.3f} Y={bounds['y']:.3f} Z={bounds['z']:.3f}")

    current = gantry.get_coordinates()
    _move_and_verify(
        gantry,
        {"x": float(current["x"]), "y": float(current["y"]), "z": bounds["z"]},
        label="estimated +Z bound",
        output=output,
    )
    _move_and_verify(
        gantry,
        {"x": bounds["x"], "y": float(current["y"]), "z": bounds["z"]},
        label="estimated +X bound",
        output=output,
    )
    _move_and_verify(
        gantry,
        {"x": bounds["x"], "y": bounds["y"], "z": bounds["z"]},
        label="estimated bounds",
        output=output,
    )


def _program_travel_spans(
    gantry: _GantryLike,
    max_travel: dict[str, float],
    output: Callable[[str], None],
) -> None:
    output("")
    output("Programming conservative travel spans and leaving soft limits disabled:")
    output(f"  $130={max_travel['max_travel_x']:.3f}")
    output(f"  $131={max_travel['max_travel_y']:.3f}")
    output(f"  $132={max_travel['max_travel_z']:.3f}")
    gantry.set_grbl_setting("$130", max_travel["max_travel_x"])
    gantry.set_grbl_setting("$131", max_travel["max_travel_y"])
    gantry.set_grbl_setting("$132", max_travel["max_travel_z"])
    gantry.set_grbl_setting("$22", 1)
    gantry.set_grbl_setting("$20", 0)


def _max_travel_from_bounds(bounds: dict[str, float]) -> dict[str, float]:
    return {
        "max_travel_x": _round_mm(bounds["x"]),
        "max_travel_y": _round_mm(bounds["y"]),
        "max_travel_z": _round_mm(bounds["z"]),
    }


def _build_gantry_grbl_settings(
    *,
    gantry_raw: dict[str, Any],
    max_travel: dict[str, float],
    runtime_profile: HomingProfile,
) -> dict[str, Any]:
    settings: dict[str, Any] = {}
    gantry_settings = gantry_raw.get("grbl_settings")
    if isinstance(gantry_settings, dict):
        settings.update(gantry_settings)
    settings.update(
        {
            "dir_invert_mask": runtime_profile.dir_invert_mask,
            "status_report": 0,
            "soft_limits": False,
            "hard_limits": True,
            "homing_enable": True,
            "homing_dir_mask": runtime_profile.homing_dir_mask,
            "max_travel_x": max_travel["max_travel_x"],
            "max_travel_y": max_travel["max_travel_y"],
            "max_travel_z": max_travel["max_travel_z"],
        }
    )
    return settings


def _updated_gantry_yaml_text(
    raw_config: dict[str, Any],
    *,
    measured_coords: dict[str, float],
    max_travel: dict[str, float],
    runtime_profile: HomingProfile,
) -> str:
    updated = copy.deepcopy(raw_config)
    updated.setdefault("cnc", {})["total_z_height"] = _round_mm(measured_coords["z"])
    updated["working_volume"] = {
        "x_min": 0.0,
        "x_max": _round_mm(measured_coords["x"]),
        "y_min": 0.0,
        "y_max": _round_mm(measured_coords["y"]),
        "z_min": 0.0,
        "z_max": _round_mm(measured_coords["z"]),
    }
    updated["grbl_settings"] = _build_gantry_grbl_settings(
        gantry_raw=raw_config,
        max_travel=max_travel,
        runtime_profile=runtime_profile,
    )
    return yaml.safe_dump(updated, sort_keys=False)


def _print_yaml_block(yaml_text: str, output: Callable[[str], None]) -> None:
    output("")
    output("Full gantry YAML to copy/paste:")
    output("```yaml")
    for line in yaml_text.rstrip().splitlines():
        output(line)
    output("```")


def _maybe_write_gantry_yaml(
    yaml_text: str,
    *,
    gantry_path: Path,
    input_reader: Callable[[str], str],
    output: Callable[[str], None],
) -> None:
    response = input_reader("Write updated gantry YAML to a new file? [y/N]: ").strip().lower()
    if response not in ("y", "yes"):
        output("Skipping gantry YAML write.")
        return
    raw_output_path = input_reader("New gantry YAML path: ").strip()
    if not raw_output_path:
        output("No output path supplied; skipping gantry YAML write.")
        return
    output_path = Path(raw_output_path).expanduser()
    if not output_path.is_absolute():
        output_path = gantry_path.parent / output_path
    output_path = output_path.resolve()
    if output_path == gantry_path:
        output("Refusing to overwrite the input gantry YAML; skipping write.")
        return
    if output_path.exists():
        output(f"Refusing to overwrite existing file {output_path}; skipping write.")
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml_text, encoding="utf-8")
    output(f"Wrote updated gantry YAML: {output_path}")


def _confirm_preflight(
    gantry_path: Path,
    input_reader: Callable[[str], str],
    output: Callable[[str], None],
) -> None:
    output(f"Loaded gantry config: {gantry_path}")
    output("Preflight:")
    output("  - FLB homing is calibration/admin only.")
    output("  - The script writes configured $3/$23 profiles exactly as YAML.")
    output("  - It unlocks an initial GRBL alarm before homing.")
    output("  - It sets FLB G54 WPos to X0 Y0 Z0 and moves to estimated bounds.")
    output("  - The controller is left in the FLB calibration profile after disconnect.")
    output("  - No instrument should be attached.")
    output("")
    output("Required operator confirmation:")
    output("  - FLB homing/limit switches are physically installed.")
    output("  - The deck, rails, fixtures, cables, samples, and path are clear.")
    output("  - E-stop/controller reset is within reach.")
    response = input_reader("Proceed with FLB origin and estimated bound move? [y/N]: ").strip().lower()
    if response not in ("y", "yes"):
        raise RuntimeError("Operator did not confirm calibration preflight.")


def run_calibration(
    gantry_path: Path = GANTRY_PATH,
    *,
    output: Callable[[str], None] = print,
    input_reader: Callable[[str], str] = input,
    gantry_factory: Callable[..., _GantryLike] = Gantry,
) -> DeckOriginCalibrationResult:
    gantry_path = gantry_path.resolve()
    load_gantry_from_yaml(gantry_path)
    raw_config = _load_raw_config(gantry_path)
    runtime_profile = _require_profile(raw_config, "runtime_brt")
    flb_profile = _require_profile(raw_config, "origin_flb")
    _confirm_preflight(gantry_path, input_reader, output)

    runtime_config = copy.deepcopy(raw_config)
    runtime_config.pop("grbl_settings", None)
    gantry = gantry_factory(config=runtime_config)
    connected = False
    committed = False
    live_settings: dict[str, str] = {}

    try:
        output("Connecting to gantry without runtime GRBL validation...")
        gantry.connect()
        connected = True
        _unlock_startup_alarm_if_needed(gantry, output)
        live_settings = _read_rollback_settings(gantry, output)

        flb_zero = _home_flb_and_zero_wpos(gantry, flb_profile, output)
        output("")
        output("Estimating usable positive machine bounds from FLB WPos zero.")
        output("Soft limits stay disabled so stale $130-$132 cannot truncate the move.")
        gantry.set_grbl_setting("$20", 0)
        output("Keeping hard-limit alarms enabled during the bound move ($21=1).")
        gantry.set_grbl_setting("$21", 1)

        bounds = _estimate_bounds(raw_config, live_settings, output)
        _move_to_bounds(gantry, bounds, output)

        output("")
        output("Conservative estimated machine bounds:")
        output(f"  X: 0.000 to {bounds['x']:.3f} mm")
        output(f"  Y: 0.000 to {bounds['y']:.3f} mm")
        output(f"  Z: 0.000 to {bounds['z']:.3f} mm")

        max_travel = _max_travel_from_bounds(bounds)
        _program_travel_spans(gantry, max_travel, output)
        committed = True

        yaml_text = _updated_gantry_yaml_text(
            raw_config,
            measured_coords=bounds,
            max_travel=max_travel,
            runtime_profile=runtime_profile,
        )
        _print_yaml_block(yaml_text, output)
        _maybe_write_gantry_yaml(
            yaml_text,
            gantry_path=gantry_path,
            input_reader=input_reader,
            output=output,
        )

        return DeckOriginCalibrationResult(
            measured_working_volume=_coords_tuple(bounds),
            flb_zero_verification=_coords_tuple(flb_zero),
            grbl_max_travel=(
                max_travel["max_travel_x"],
                max_travel["max_travel_y"],
                max_travel["max_travel_z"],
            ),
        )
    finally:
        if connected:
            if not committed:
                _restore_setting(gantry, live_settings, "$20", output)
                _restore_setting(gantry, live_settings, "$21", output)
                _restore_setting(gantry, live_settings, "$130", output)
                _restore_setting(gantry, live_settings, "$131", output)
                _restore_setting(gantry, live_settings, "$132", output)
            _set_serial_timeout(gantry, 0.05)
            output("Disconnecting...")
            gantry.disconnect()


def main() -> None:
    try:
        run_calibration()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
