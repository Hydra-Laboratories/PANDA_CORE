"""Safe user entrypoint for gantry calibration.

Examples:

    python setup/calibrate_gantry.py \
      --seed configs/gantry/seeds/cub_xl_asmi.yaml \
      --output-gantry configs/gantry/cub_xl_asmi.yaml

    python setup/calibrate_gantry.py \
      --seed configs/gantry/seeds/cub_xl_sterling_3_instrument.yaml \
      --output-gantry configs/gantry/cub_xl_sterling_3_instrument.yaml

The script reads the seed YAML, counts mounted instruments, and chooses the
single- or multi-instrument calibration flow.
"""

from __future__ import annotations

import argparse
import copy
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

import yaml

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from gantry import Gantry, load_gantry_from_yaml  # noqa: E402
from gantry.gantry_driver.exceptions import (  # noqa: E402
    CommandExecutionError,
    MillConnectionError,
    StatusReturnError,
)
from gantry.origin import (  # noqa: E402
    DeckOriginCalibrationPlan,
    build_deck_origin_calibration_plan,
    validate_deck_origin_minima,
)
from setup.keyboard_input import flush_stdin, read_keypress_batch  # noqa: E402


# ---------------------------------------------------------------------------
# Single- and multi-instrument calibration implementation.
# Kept in this user-facing file intentionally: setup/calibrate_gantry.py is the
# only calibration entrypoint and chooses the flow from the seed YAML.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DeckOriginCalibrationResult:
    """Result of one-instrument deck-origin calibration."""

    measured_working_volume: tuple[float, float, float]
    xy_origin_verification: tuple[float, float, float]
    z_reference_verification: tuple[float, float, float]
    z_min_mm: float
    z_reference_mode: str
    reachable_z_min_mm: float | None
    grbl_max_travel: tuple[float, float, float] | None
    instrument_name: str | None
    plan: DeckOriginCalibrationPlan

    @property
    def reference_verification(self) -> tuple[float, float, float]:
        """Backward-compatible alias for the final Z-reference verification."""
        return self.z_reference_verification

    @property
    def reference_surface_z_mm(self) -> float:
        """Deprecated alias for the one-instrument lower Z assignment."""
        return self.z_min_mm


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
    def get_status(self) -> str: ...
    def jog(
        self,
        x: float = 0,
        y: float = 0,
        z: float = 0,
        feed_rate: float = 2000,
    ) -> None: ...
    def jog_cancel(self) -> None: ...
    def stop(self) -> None: ...
    def unlock(self) -> None: ...
    def reset_and_unlock(self) -> None: ...
    def configure_soft_limits_from_spans(
        self,
        *,
        max_travel_x: float,
        max_travel_y: float,
        max_travel_z: float,
        tolerance_mm: float = 0.001,
    ) -> None: ...


KeyReader = Callable[[], tuple[str, int]]


CONTROLS_LEGEND = """
Jog controls after homing:
  RIGHT / LEFT       +X right / -X left
  UP / DOWN          +Y back-away / -Y front-toward-operator
  X / Z              +Z up / -Z down
  1 / 2 / 3 / 4 / 5 / 6 / 7
                      Set jog step to 0.1 / 1 / 5 / 10 / 25 / 50 / 100 mm
  SPACE              Cancel any active jog
  ENTER              Confirm the current calibration step
  Q                  Abort calibration
"""


def _load_raw_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Gantry config is empty or invalid: {path}")
    return config


def _coords_tuple(coords: dict[str, float]) -> tuple[float, float, float]:
    return (float(coords["x"]), float(coords["y"]), float(coords["z"]))


def _round_mm(value: float) -> float:
    return round(float(value), 3)


def _calculate_grbl_max_travel(
    measured_coords: dict[str, float],
    *,
    z_min_mm: float,
    tolerance_mm: float,
) -> dict[str, float]:
    x_span = _round_mm(float(measured_coords["x"]))
    y_span = _round_mm(float(measured_coords["y"]))
    z_span = _round_mm(float(measured_coords["z"]) - float(z_min_mm))
    spans = {
        "max_travel_x": x_span,
        "max_travel_y": y_span,
        "max_travel_z": z_span,
    }
    invalid = [f"{key}={value}" for key, value in spans.items() if value <= tolerance_mm]
    if invalid:
        raise RuntimeError(
            "Measured travel span is not positive enough for GRBL soft limits: "
            + ", ".join(invalid)
        )
    return spans


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


def _updated_gantry_yaml_text(
    raw_config: dict[str, Any],
    *,
    measured_coords: dict[str, float],
    z_min_mm: float,
    max_travel: dict[str, float] | None = None,
) -> str:
    updated = copy.deepcopy(raw_config)
    updated.setdefault("cnc", {})["total_z_height"] = _round_mm(measured_coords["z"])
    updated["working_volume"] = {
        "x_min": 0.0,
        "x_max": _round_mm(measured_coords["x"]),
        "y_min": 0.0,
        "y_max": _round_mm(measured_coords["y"]),
        "z_min": _round_mm(z_min_mm),
        "z_max": _round_mm(measured_coords["z"]),
    }
    if max_travel is not None:
        updated["grbl_settings"] = _build_gantry_grbl_settings(
            gantry_raw=raw_config,
            max_travel=max_travel,
        )
    return yaml.safe_dump(updated, sort_keys=False)


def _build_gantry_grbl_settings(
    *,
    gantry_raw: dict[str, Any],
    max_travel: dict[str, float],
) -> dict[str, Any]:
    settings = dict(gantry_raw.get("grbl_settings") or {})
    settings.update(
        {
            "status_report": 0,
            "soft_limits": True,
            "homing_enable": True,
            "max_travel_x": max_travel["max_travel_x"],
            "max_travel_y": max_travel["max_travel_y"],
            "max_travel_z": max_travel["max_travel_z"],
        }
    )
    return settings


def _print_yaml_block(
    *,
    title: str,
    yaml_text: str,
    output: Callable[[str], None],
) -> None:
    output("")
    output(title)
    output("```yaml")
    for line in yaml_text.rstrip().splitlines():
        output(line)
    output("```")


def _maybe_write_gantry_yaml(
    *,
    yaml_text: str,
    output_path: Path | None,
    write_requested: bool,
    input_reader: Callable[[str], str],
    output: Callable[[str], None],
) -> None:
    if output_path is None and not write_requested:
        return
    explicit_output_path = output_path is not None
    if output_path is None:
        raw = input_reader("Output gantry YAML filename: ").strip()
        if not raw:
            output("No gantry YAML filename supplied; skipping write.")
            return
        output_path = Path(raw)
    if not explicit_output_path:
        confirm = input_reader(
            f"Write updated gantry YAML to {output_path}? [y/N]: "
        ).strip().lower()
        if confirm not in ("y", "yes"):
            output("Skipping gantry YAML write.")
            return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml_text, encoding="utf-8")
    output(f"Wrote updated gantry YAML: {output_path}")


def _assert_near_xy_origin(
    coords: dict[str, float],
    *,
    tolerance_mm: float,
) -> None:
    expected = {
        "x": 0.0,
        "y": 0.0,
    }
    misses = [
        f"{axis}: got {float(coords[axis]):.4f}, expected {expected[axis]:.4f}"
        for axis in ("x", "y")
        if abs(float(coords[axis]) - expected[axis]) > tolerance_mm
    ]
    if misses:
        raise RuntimeError(
            "Deck-origin XY reference did not verify within "
            f"{tolerance_mm} mm: " + "; ".join(misses)
        )


def _assert_near_z_reference(
    coords: dict[str, float],
    *,
    z_min_mm: float,
    tolerance_mm: float,
) -> None:
    expected = {"z": z_min_mm}
    misses = [
        f"{axis}: got {float(coords[axis]):.4f}, expected {expected[axis]:.4f}"
        for axis in ("z",)
        if abs(float(coords[axis]) - expected[axis]) > tolerance_mm
    ]
    if misses:
        raise RuntimeError(
            "Deck-origin Z reference did not verify within "
            f"{tolerance_mm} mm: " + "; ".join(misses)
        )


def _assert_positive_measured_volume(
    coords: dict[str, float],
    *,
    tolerance_mm: float,
) -> None:
    misses = [
        f"{axis}: got {float(coords[axis]):.4f}"
        for axis in ("x", "y", "z")
        if float(coords[axis]) <= tolerance_mm
    ]
    if misses:
        raise RuntimeError(
            "Measured homed WPos did not look like positive working-volume "
            "maxima: " + "; ".join(misses)
        )


def _print_config_patch(
    coords: dict[str, float],
    *,
    z_reference_coords: dict[str, float],
    z_min_mm: float,
    z_reference_mode: str,
    instrument_name: str | None,
    output: Callable[[str], None],
) -> None:
    x_max, y_max, z_max = _coords_tuple(coords)
    output("")
    output("Measured physical working volume from calibrated origin:")
    output(f"  X: 0.000 to {x_max:.3f} mm")
    output(f"  Y: 0.000 to {y_max:.3f} mm")
    output(f"  Z: {z_min_mm:.3f} to {z_max:.3f} mm")
    output("")
    output("Update the gantry YAML working_volume to:")
    output("  working_volume:")
    output("    x_min: 0.0")
    output(f"    x_max: {x_max:.3f}")
    output("    y_min: 0.0")
    output(f"    y_max: {y_max:.3f}")
    output(f"    z_min: {z_min_mm:.3f}")
    output(f"    z_max: {z_max:.3f}")
    output("")
    output("Also set cnc.total_z_height to:")
    output(f"  total_z_height: {z_max:.3f}")
    output("")
    output("Z reference point after XY origining:")
    output(
        "  WPos "
        f"X={z_reference_coords['x']:.3f} "
        f"Y={z_reference_coords['y']:.3f} "
        f"Z={z_reference_coords['z']:.3f}"
    )
    output(f"  mode: {z_reference_mode}")
    if z_min_mm > 0:
        reach_name = instrument_name or "reference_tcp"
        output("")
        output(
            "This one-instrument config starts above physical deck bottom "
            "because the TCP cannot reach Z=0."
        )
        output(f"  {reach_name}_reachable_z_min: {z_min_mm:.3f} mm")
        output(
            "For a future multi-instrument config, keep one shared deck frame "
            "and encode this as a per-instrument lower-reach limit instead of "
            "using one global z_min for every tool."
        )


def _print_dry_run(
    gantry_path: Path,
    plan: DeckOriginCalibrationPlan,
    *,
    tip_gap_mm: float | None,
    z_reference_mode: str,
    instrument_name: str | None,
    output: Callable[[str], None],
) -> None:
    output(f"Loaded deck-origin gantry config: {gantry_path}")
    if instrument_name:
        output(f"Instrument/TCP: {instrument_name}")
    output(f"Z reference mode: {z_reference_mode}")
    output("Dry run only. Physical calibration flow:")
    commands = _commands_for_z_min(
        plan,
        tip_gap_mm,
        z_reference_mode=z_reference_mode,
    )
    for command in commands:
        output(f"  {command}")
    output("")
    output("No configured max travel values will be trusted as measured volume.")


def _commands_for_z_min(
    plan: DeckOriginCalibrationPlan,
    tip_gap_mm: float | None,
    *,
    z_reference_mode: str = "ruler-gap",
) -> tuple[str, ...]:
    z_value = (
        "0"
        if z_reference_mode == "bottom"
        else ("<tip_gap_mm>" if tip_gap_mm is None else f"{tip_gap_mm:g}")
    )
    confirmation = "<confirm true deck-bottom contact>"
    if z_reference_mode in ("prompt", "ruler-gap", "known-height"):
        confirmation = "<confirm bottom contact or enter ruler-measured TCP gap>"
    return tuple(
        command.replace("<z_min_mm>", z_value).replace(
            "<confirm deck-bottom contact or enter ruler-measured TCP gap>",
            confirmation,
        )
        for command in plan.commands
    )


def _prompt_tip_gap_mm(
    *,
    input_reader: Callable[[str], str],
    output: Callable[[str], None],
) -> float:
    output("")
    output(
        "This TCP is not touching true deck bottom at its lower reach point."
    )
    output(
        "Measure the vertical gap from the deck surface to the TCP with a "
        "ruler, then enter that gap in millimeters."
    )
    while True:
        raw = input_reader("Deck-to-TCP gap in mm: ").strip()
        try:
            value = float(raw)
        except ValueError:
            output("Enter a numeric gap in millimeters.")
            continue
        if value <= 0:
            output("Deck-to-TCP gap must be > 0 mm. Use bottom mode for Z=0.")
            continue
        return value


def _prompt_block_height_mm(
    *,
    input_reader: Callable[[str], str],
    output: Callable[[str], None],
) -> float:
    output("")
    output("Z reference: use a calibration block. The instrument should touch the block top.")
    while True:
        raw = input_reader("Calibration block height in mm: ").strip()
        try:
            value = float(raw)
        except ValueError:
            output("Enter a numeric block height in millimeters.")
            continue
        if value <= 0:
            output("Calibration block height must be > 0 mm.")
            continue
        return value


def _prompt_z_reference_mode(
    *,
    input_reader: Callable[[str], str],
    output: Callable[[str], None],
) -> str:
    output("")
    output("Z grounding mode:")
    output("  y = this TCP is touching true deck bottom, so set Z=0 here")
    output("  n = no/unsure; measure the deck-to-TCP gap with a ruler")
    while True:
        raw = input_reader(
            "Is the TCP touching true deck bottom at the current pose? [y/N]: "
        ).strip().lower()
        if raw in ("", "n", "no", "u", "unsure"):
            return "ruler-gap"
        if raw in ("y", "yes"):
            return "bottom"
        output("Enter y for true-bottom contact, or n/Enter for ruler-gap mode.")


def _set_serial_timeout_if_available(
    gantry: _GantryLike,
    timeout_s: float,
) -> None:
    setter = getattr(gantry, "set_serial_timeout", None)
    if callable(setter):
        setter(timeout_s)


def _looks_like_limit_alarm(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        token in message
        for token in (
            "alarm",
            "check limits",
            "hard limit",
            "limit",
            "pn:",
            "error:9",
        )
    )


def _looks_like_soft_limit_jog_rejection(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        token in message
        for token in (
            "error:15",
            "travel exceeded",
            "jog target exceeds machine travel",
        )
    )


def _soft_limits_enabled_from_settings(settings: object) -> bool | None:
    if not isinstance(settings, dict):
        return None
    value = settings.get("$20")
    if value is None:
        value = settings.get("20")
    if value is None:
        return None
    try:
        return float(value) != 0.0
    except (TypeError, ValueError):
        return None


def _read_soft_limits_enabled_if_available(
    gantry: _GantryLike,
    *,
    output: Callable[[str], None],
) -> bool | None:
    reader = getattr(gantry, "read_grbl_settings", None)
    if not callable(reader):
        return None
    try:
        return _soft_limits_enabled_from_settings(reader())
    except MillConnectionError:
        raise
    except (CommandExecutionError, StatusReturnError, ValueError) as exc:
        output(f"Could not read GRBL soft-limit state before jogging: {exc}")
        output("Continuing; any GRBL error:15 jog rejection will be handled in-place.")
        return None


def _set_soft_limits_enabled_if_available(
    gantry: _GantryLike,
    enabled: bool,
) -> bool:
    setter = getattr(gantry, "set_grbl_setting", None)
    if not callable(setter):
        return False
    setter("$20", 1 if enabled else 0)
    return True


def _temporarily_disable_soft_limits_for_origin_jog(
    gantry: _GantryLike,
    *,
    output: Callable[[str], None],
) -> bool:
    enabled = _read_soft_limits_enabled_if_available(gantry, output=output)
    if enabled is not True:
        return False
    output(
        "Temporarily disabling GRBL soft limits ($20=0) for the interactive "
        "origin jog so stale travel settings cannot block calibration."
    )
    output("Jog cautiously; this does not change the hard-limit setting.")
    if not _set_soft_limits_enabled_if_available(gantry, False):
        output("No GRBL setting writer is available; leaving soft limits unchanged.")
        return False
    return True


def _restore_soft_limits_after_origin_jog(
    gantry: _GantryLike,
    *,
    output: Callable[[str], None],
) -> None:
    output("Restoring GRBL soft limits ($20=1) after interactive origin jog.")
    if not _set_soft_limits_enabled_if_available(gantry, True):
        raise MillConnectionError(
            "Cannot restore GRBL soft limits because this gantry object has no "
            "setting writer."
        )


def _opposite_pull_off_delta(
    delta: dict[str, float],
    pull_off_mm: float,
) -> dict[str, float]:
    pull_off = {"x": 0.0, "y": 0.0, "z": 0.0}
    for axis, value in delta.items():
        if value == 0:
            continue
        if value > 0:
            pull_off[axis] = -pull_off_mm
        else:
            pull_off[axis] = pull_off_mm
    return pull_off


def _soft_reset_and_unlock_after_limit_alarm(
    gantry: _GantryLike,
    *,
    output: Callable[[str], None],
) -> None:
    reset_and_unlock = getattr(gantry, "reset_and_unlock", None)
    if not callable(reset_and_unlock):
        raise CommandExecutionError(
            "Limit recovery requires gantry.reset_and_unlock() so GRBL gets "
            "a soft reset (Ctrl-X) before $X unlock."
        )
    try:
        output("Soft-resetting GRBL, then unlocking before pull-off.")
        reset_and_unlock()
    except MillConnectionError:
        raise
    except (CommandExecutionError, StatusReturnError) as exc:
        output(f"Soft reset/unlock during limit recovery failed: {exc}")
        output("Use the controller/E-stop reset path before continuing.")
        raise


def _raise_if_limit_status(status: str) -> None:
    lower_status = status.lower()
    if "alarm" in lower_status:
        raise StatusReturnError(f"Alarm in status: {status}")
    # GRBL reports active limit pins as Pn:X, Pn:Y, Pn:Z (possibly combined).
    # Treat that as a limit condition during manual calibration so the operator
    # gets an immediate pull-off instead of discovering it on the next jog.
    if "pn:" in lower_status:
        pin_text = lower_status.split("pn:", 1)[1].split("|", 1)[0].split(">", 1)[0]
        if any(axis in pin_text for axis in ("x", "y", "z")):
            raise StatusReturnError(f"Limit pin active in status: {status}")


def _probe_for_limit_status_after_jog(gantry: _GantryLike) -> None:
    get_status = getattr(gantry, "get_status", None)
    if not callable(get_status):
        return
    time.sleep(0.05)
    _raise_if_limit_status(str(get_status()))


def _read_limit_recovery_status(gantry: _GantryLike) -> str | None:
    get_status = getattr(gantry, "get_status", None)
    if not callable(get_status):
        return None
    try:
        return str(get_status())
    except Exception:
        return None


def _needs_another_limit_pull_off(status: str | None) -> bool:
    if status is None:
        return False
    lower = status.lower()
    return any(
        token in lower
        for token in (
            "alarm",
            "reset to continue",
            "hard limit",
            "limit",
            "pn:",
            "statusqueryfailed",
            "failed",
        )
    )


def _recover_from_limit_alarm(
    gantry: _GantryLike,
    delta: dict[str, float],
    *,
    pull_off_mm: float,
    feed_rate: float,
    output: Callable[[str], None],
) -> dict[str, float] | None:
    effective_pull_off_mm = max(5.0, float(pull_off_mm))
    pull_off = _opposite_pull_off_delta(delta, effective_pull_off_mm)
    failed_direction = ", ".join(
        f"{axis.upper()}{value:+g} mm" for axis, value in delta.items() if value
    ) or "unknown direction"
    pull_off_direction = ", ".join(
        f"{axis.upper()}{value:+g} mm" for axis, value in pull_off.items() if value
    ) or "unknown direction"
    output(
        "Limit alarm detected while jogging "
        f"{failed_direction}. Soft-resetting/unlocking GRBL and pulling off "
        f"{pull_off_direction} at {feed_rate:g} mm/min."
    )
    try:
        gantry.jog_cancel()
    except MillConnectionError:
        raise
    except (CommandExecutionError, StatusReturnError) as exc:
        output(f"Jog cancel during recovery failed: {exc}")
        output("Aborting calibration; use E-stop and rerun before continuing.")
        raise

    max_pull_off_attempts = 5
    output(
        f"Attempting limit pull-off up to {max_pull_off_attempts} times; "
        "soft-resetting/unlocking between attempts."
    )
    for attempt in range(1, max_pull_off_attempts + 1):
        _soft_reset_and_unlock_after_limit_alarm(gantry, output=output)
        try:
            gantry.jog(feed_rate=feed_rate, **pull_off)
        except MillConnectionError:
            raise
        except (CommandExecutionError, StatusReturnError) as exc:
            if attempt >= max_pull_off_attempts:
                output(f"Limit pull-off failed after {max_pull_off_attempts} attempts: {exc}")
                output("Aborting calibration; gantry position is unknown.")
                raise
            output(
                f"Limit pull-off attempt {attempt}/{max_pull_off_attempts} did not clear; retrying."
            )
            continue

        status = _read_limit_recovery_status(gantry)
        if not _needs_another_limit_pull_off(status):
            break
        if attempt >= max_pull_off_attempts:
            output(
                "Pull-off jog still left the controller in a limit/alarm state "
                f"after {max_pull_off_attempts} attempts. Use E-stop/power reset "
                "and manually clear the switch before continuing."
            )
            raise StatusReturnError(
                "Limit pull-off did not clear the alarm after repeated attempts."
            )
        output(
            f"Limit pull-off attempt {attempt}/{max_pull_off_attempts} did not clear; retrying."
        )
    output(
        "Pulled off the limit switch. Skipping immediate WPos readback because "
        "GRBL may not report coordinates reliably right after a limit reset; "
        "position readback will resume on the next operator confirmation."
    )
    return None


def _interactive_jog_to_reference(
    gantry: _GantryLike,
    *,
    target_description: str,
    confirmation_description: str,
    key_reader: KeyReader,
    output: Callable[[str], None],
    feed_rate: float,
    initial_step_mm: float,
    limit_pull_off_mm: float,
) -> dict[str, float]:
    step_mm = initial_step_mm
    output(CONTROLS_LEGEND)
    output(target_description)
    output(confirmation_description)

    while True:
        key, count = key_reader()
        key = key.upper()
        count = max(1, int(count))
        distance = step_mm * count

        if key == "Q":
            raise KeyboardInterrupt
        if key in ("\r", "\n", "ENTER"):
            coords = gantry.get_coordinates()
            output(
                "Confirming current reported WPos "
                f"X={coords['x']:.3f} Y={coords['y']:.3f} Z={coords['z']:.3f}"
            )
            return coords
        if key == " ":
            gantry.jog_cancel()
            output("Jog canceled.")
            continue
        if key == "1":
            step_mm = 0.1
            output("Jog step set to 0.1 mm.")
            continue
        if key == "2":
            step_mm = 1.0
            output("Jog step set to 1.0 mm.")
            continue
        if key == "3":
            step_mm = 5.0
            output("Jog step set to 5.0 mm.")
            continue
        if key == "4":
            step_mm = 10.0
            output("Jog step set to 10.0 mm.")
            continue
        if key == "5":
            step_mm = 25.0
            output("Jog step set to 25.0 mm.")
            continue
        if key == "6":
            step_mm = 50.0
            output("Jog step set to 50.0 mm.")
            continue
        if key == "7":
            step_mm = 100.0
            output("Jog step set to 100.0 mm.")
            continue

        delta = {"x": 0.0, "y": 0.0, "z": 0.0}
        if key == "LEFT":
            delta["x"] = -distance
        elif key == "RIGHT":
            delta["x"] = distance
        elif key == "DOWN":
            delta["y"] = -distance
        elif key == "UP":
            delta["y"] = distance
        elif key == "Z":
            delta["z"] = -distance
        elif key == "X":
            delta["z"] = distance
        else:
            continue

        coords = None
        try:
            gantry.jog(feed_rate=feed_rate, **delta)
            coords = gantry.get_coordinates()
            _probe_for_limit_status_after_jog(gantry)
        except MillConnectionError:
            raise
        except (CommandExecutionError, StatusReturnError) as exc:
            if _looks_like_soft_limit_jog_rejection(exc):
                output(
                    "GRBL rejected that jog because the target exceeds the "
                    "current soft-limit travel. The jog was ignored; reduce "
                    "the step, choose another direction, or press ENTER if "
                    "this is the intended safe origin point."
                )
                try:
                    coords = gantry.get_coordinates()
                except MillConnectionError:
                    raise
                except (CommandExecutionError, StatusReturnError) as read_exc:
                    output(f"WPos readback after rejected jog failed: {read_exc}")
                    output("Aborting calibration; gantry position is unknown.")
                    raise
            elif not _looks_like_limit_alarm(exc):
                output(f"Jog command rejected by controller: {exc}")
                output("Aborting calibration; gantry position is unknown.")
                raise
            else:
                coords = _recover_from_limit_alarm(
                    gantry,
                    delta,
                    pull_off_mm=limit_pull_off_mm,
                    feed_rate=feed_rate,
                    output=output,
                )
        if coords is None:
            continue
        output(
            "WPos "
            f"X={coords['x']:.3f} Y={coords['y']:.3f} Z={coords['z']:.3f} "
            f"(step {step_mm:g} mm)"
        )


def _interactive_jog_to_xy_origin(
    gantry: _GantryLike,
    *,
    key_reader: KeyReader,
    output: Callable[[str], None],
    feed_rate: float,
    initial_step_mm: float,
    limit_pull_off_mm: float,
) -> dict[str, float]:
    return _interactive_jog_to_reference(
        gantry,
        target_description=(
            "Step 1/1: jog the one reference TCP as far as appropriate toward "
            "the physical front-left XY origin and its lowest safe reachable Z."
        ),
        confirmation_description=(
            "Press ENTER only when the current X/Y should become WPos X=0, "
            "Y=0. After confirmation, the script will set Z from either true "
            "deck-bottom contact or a ruler-measured deck-to-TCP gap."
        ),
        key_reader=key_reader,
        output=output,
        feed_rate=feed_rate,
        initial_step_mm=initial_step_mm,
        limit_pull_off_mm=limit_pull_off_mm,
    )


def run_calibration(
    gantry_path: Path,
    *,
    dry_run: bool = False,
    tolerance_mm: float = 0.25,
    jog_step_mm: float = 1.0,
    jog_feed_rate: float = 2500.0,
    limit_pull_off_mm: float = 5.0,
    tip_gap_mm: float | None = None,
    reference_surface_z_mm: float | None = None,
    z_reference_mode: str = "bottom",
    measure_reachable_z_min: bool | None = False,
    instrument_name: str | None = None,
    skip_soft_limit_config: bool = False,
    write_gantry_yaml: bool = False,
    output_gantry_path: Path | None = None,
    homing_serial_timeout_s: float = 10.0,
    jog_serial_timeout_s: float = 1.0,
    output: Callable[[str], None] = print,
    input_reader: Callable[[str], str] = input,
    gantry_factory: Callable[..., _GantryLike] = Gantry,
    key_reader: KeyReader = read_keypress_batch,
    stdin_flusher: Callable[[], None] = flush_stdin,
) -> DeckOriginCalibrationResult | DeckOriginCalibrationPlan:
    """Calibrate one reference TCP to the CubOS physical deck origin."""
    gantry_path = gantry_path.resolve()
    gantry_config = load_gantry_from_yaml(gantry_path)
    raw_config = _load_raw_config(gantry_path)
    if output_gantry_path is not None:
        output_gantry_path = output_gantry_path.resolve()
    plan = build_deck_origin_calibration_plan(gantry_config)
    if reference_surface_z_mm is not None:
        if tip_gap_mm is not None:
            raise ValueError("Use only one of tip_gap_mm or reference_surface_z_mm.")
        tip_gap_mm = reference_surface_z_mm
    deprecated_known_height_mode = z_reference_mode == "known-height"
    if deprecated_known_height_mode:
        z_reference_mode = "ruler-gap"
    if z_reference_mode not in ("prompt", "bottom", "ruler-gap", "block"):
        raise ValueError("z_reference_mode must be one of: prompt, bottom, ruler-gap, block")
    if deprecated_known_height_mode:
        output(
            "Deprecated z_reference_mode=known-height received; treating "
            "the supplied height as a ruler-measured deck-to-TCP gap."
        )

    if dry_run:
        _print_dry_run(
            gantry_path,
            plan,
            tip_gap_mm=tip_gap_mm,
            z_reference_mode=z_reference_mode,
            instrument_name=instrument_name,
            output=output,
        )
        return plan

    output(f"Loaded deck-origin gantry config: {gantry_path}")
    output("Preflight:")
    output("  - Attach exactly one reference instrument/TCP for this calibration.")
    output("  - Place a calibration block at the front-left origin point.")
    output("  - Jog the instrument tip/probe to touch the block top at that point.")
    output("  - This will set X=0, Y=0, and Z to the calibration block height at the same pose.")
    if measure_reachable_z_min is True:
        output(
            "  - --measure-reachable-z-min is deprecated; the lower reach is "
            "now recorded from the origin/gap calibration point."
        )
    if instrument_name:
        output(f"  - Instrument/TCP label for reach output: {instrument_name}")
    output("")

    gantry_runtime_config = copy.deepcopy(raw_config)
    gantry_runtime_config.pop("grbl_settings", None)
    gantry = gantry_factory(config=gantry_runtime_config)
    restore_soft_limits_after_origin_jog = False
    try:
        output("Connecting to gantry...")
        gantry.connect()

        output("Homing to normalized back-right-top corner...")
        _set_serial_timeout_if_available(gantry, homing_serial_timeout_s)
        gantry.home()
        _set_serial_timeout_if_available(gantry, jog_serial_timeout_s)
        output("Forcing GRBL WPos status reporting ($10=0) and G90...")
        gantry.enforce_work_position_reporting()
        output("Activating G54 work coordinate system...")
        gantry.activate_work_coordinate_system("G54")
        output("Clearing transient G92 offsets before origin calibration...")
        gantry.clear_g92_offsets()
        stdin_flusher()

        restore_soft_limits_after_origin_jog = (
            _temporarily_disable_soft_limits_for_origin_jog(
                gantry,
                output=output,
            )
        )
        try:
            _interactive_jog_to_xy_origin(
                gantry,
                key_reader=key_reader,
                output=output,
                feed_rate=jog_feed_rate,
                initial_step_mm=jog_step_mm,
                limit_pull_off_mm=limit_pull_off_mm,
            )
        finally:
            if restore_soft_limits_after_origin_jog:
                restore_soft_limits_after_origin_jog = False
                _restore_soft_limits_after_origin_jog(gantry, output=output)

        output("Setting current physical pose to WPos X=0, Y=0...")
        gantry.set_work_coordinates(x=0.0, y=0.0)
        xy_origin_coords = dict(gantry.get_coordinates())
        _assert_near_xy_origin(
            xy_origin_coords,
            tolerance_mm=tolerance_mm,
        )
        output(
            "Verified XY origin WPos: "
            f"X={xy_origin_coords['x']:.3f} "
            f"Y={xy_origin_coords['y']:.3f} "
            f"Z={xy_origin_coords['z']:.3f}"
        )

        if z_reference_mode == "prompt":
            z_reference_mode = _prompt_z_reference_mode(
                input_reader=input_reader,
                output=output,
            )
        if z_reference_mode == "bottom":
            if tip_gap_mm is not None and tip_gap_mm != 0:
                raise ValueError("Bottom Z mode cannot use a non-zero tip gap.")
            z_min_mm = 0.0
        elif z_reference_mode == "block":
            if tip_gap_mm is None:
                tip_gap_mm = _prompt_block_height_mm(
                    input_reader=input_reader,
                    output=output,
                )
            if tip_gap_mm <= 0:
                raise ValueError("block height must be > 0 in block mode.")
            z_min_mm = float(tip_gap_mm)
        else:
            if tip_gap_mm is None:
                tip_gap_mm = _prompt_tip_gap_mm(
                    input_reader=input_reader,
                    output=output,
                )
            if tip_gap_mm <= 0:
                raise ValueError("tip_gap_mm must be > 0 in ruler-gap mode.")
            z_min_mm = float(tip_gap_mm)

        output(f"Setting current physical pose to WPos Z={z_min_mm:g}...")
        gantry.set_work_coordinates(z=z_min_mm)
        z_reference_coords = dict(gantry.get_coordinates())
        _assert_near_z_reference(
            z_reference_coords,
            z_min_mm=z_min_mm,
            tolerance_mm=tolerance_mm,
        )
        output(
            "Verified Z reference WPos: "
            f"X={z_reference_coords['x']:.3f} "
            f"Y={z_reference_coords['y']:.3f} "
            f"Z={z_reference_coords['z']:.3f}"
        )

        reachable_z_min_mm = z_min_mm

        output("Re-homing to measure physical working-volume maxima...")
        _set_serial_timeout_if_available(gantry, homing_serial_timeout_s)
        gantry.home()
        _set_serial_timeout_if_available(gantry, jog_serial_timeout_s)
        measured_coords = gantry.get_coordinates()
        _assert_positive_measured_volume(
            measured_coords,
            tolerance_mm=tolerance_mm,
        )
        max_travel = _calculate_grbl_max_travel(
            measured_coords,
            z_min_mm=z_min_mm,
            tolerance_mm=tolerance_mm,
        )
        if skip_soft_limit_config:
            output("Skipping GRBL soft-limit programming by request.")
        else:
            gantry.configure_soft_limits_from_spans(
                max_travel_x=max_travel["max_travel_x"],
                max_travel_y=max_travel["max_travel_y"],
                max_travel_z=max_travel["max_travel_z"],
                tolerance_mm=tolerance_mm,
            )

        _print_config_patch(
            measured_coords,
            z_reference_coords=z_reference_coords,
            z_min_mm=z_min_mm,
            z_reference_mode=z_reference_mode,
            instrument_name=instrument_name,
            output=output,
        )
        gantry_yaml_text = _updated_gantry_yaml_text(
            raw_config,
            measured_coords=measured_coords,
            z_min_mm=z_min_mm,
            max_travel=max_travel,
        )
        _print_yaml_block(
            title="Full gantry YAML to copy/paste:",
            yaml_text=gantry_yaml_text,
            output=output,
        )
        _maybe_write_gantry_yaml(
            yaml_text=gantry_yaml_text,
            output_path=output_gantry_path,
            write_requested=write_gantry_yaml,
            input_reader=input_reader,
            output=output,
        )

        return DeckOriginCalibrationResult(
            measured_working_volume=_coords_tuple(measured_coords),
            xy_origin_verification=_coords_tuple(xy_origin_coords),
            z_reference_verification=_coords_tuple(z_reference_coords),
            z_min_mm=z_min_mm,
            z_reference_mode=z_reference_mode,
            reachable_z_min_mm=reachable_z_min_mm,
            grbl_max_travel=(
                max_travel["max_travel_x"],
                max_travel["max_travel_y"],
                max_travel["max_travel_z"],
            ),
            instrument_name=instrument_name,
            plan=plan,
        )
    finally:
        try:
            if restore_soft_limits_after_origin_jog:
                restore_soft_limits_after_origin_jog = False
                _restore_soft_limits_after_origin_jog(gantry, output=output)
        finally:
            _set_serial_timeout_if_available(gantry, 0.05)
            output("Disconnecting...")
            gantry.disconnect()


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
    def jog_cancel(self) -> None: ...
    def stop(self) -> None: ...
    def unlock(self) -> None: ...
    def configure_soft_limits_from_spans(
        self,
        *,
        max_travel_x: float,
        max_travel_y: float,
        max_travel_z: float,
        tolerance_mm: float = 0.001,
    ) -> None: ...


KeyReader = Callable[[], tuple[str, int]]


@dataclass(frozen=True)
class MultiInstrumentCalibrationResult:
    """Result of a multi-instrument board calibration run."""

    measured_working_volume: tuple[float, float, float]
    xy_bounds_after_origin: tuple[float, float, float]
    xy_origin_verification: tuple[float, float, float]
    z_origin_verification: tuple[float, float, float]
    instrument_calibrations: dict[str, dict[str, float]]
    grbl_max_travel: tuple[float, float, float]
    reference_instrument: str
    lowest_instrument: str
    block_reference_coordinates: dict[str, tuple[float, float, float]]


def _coords_tuple(coords: dict[str, float]) -> tuple[float, float, float]:
    return (float(coords["x"]), float(coords["y"]), float(coords["z"]))


def _assert_near_xy_origin(
    coords: dict[str, float],
    *,
    tolerance_mm: float,
) -> None:
    misses = [
        f"{axis}: got {float(coords[axis]):.4f}, expected 0.0000"
        for axis in ("x", "y")
        if abs(float(coords[axis])) > tolerance_mm
    ]
    if misses:
        raise RuntimeError(
            "Deck-origin XY reference did not verify within "
            f"{tolerance_mm} mm: " + "; ".join(misses)
        )


def compute_relative_instrument_calibrations(
    *,
    block_coordinates: dict[str, dict[str, float]],
    reference_instrument: str,
    lowest_instrument: str,
) -> dict[str, dict[str, float]]:
    """Compute offsets/depths from one shared, arbitrary block point.

    The block does not need known deck-frame X/Y/Z coordinates. The reference
    instrument defines zero XY offset, and the lowest instrument defines zero
    depth after the Z-reference step. For every other instrument, touching the
    same physical block point gives the relative WPos deltas needed by
    Board.move() semantics:
        offset_i = offset_ref + gantry_ref - gantry_i
        depth_i = depth_lowest + gantry_i_z - gantry_lowest_z
    with offset_ref=(0, 0) and depth_lowest=0 in this calibration flow.
    """
    missing = [
        name
        for name in (reference_instrument, lowest_instrument)
        if name not in block_coordinates
    ]
    if missing:
        raise ValueError(
            "Missing block coordinate(s) for required baseline instrument(s): "
            + ", ".join(missing)
        )
    reference_coords = block_coordinates[reference_instrument]
    lowest_coords = block_coordinates[lowest_instrument]
    calibrations: dict[str, dict[str, float]] = {}
    for instrument, coords in block_coordinates.items():
        calibrations[instrument] = {
            "offset_x": _round_mm(
                float(reference_coords["x"]) - float(coords["x"])
            ),
            "offset_y": _round_mm(
                float(reference_coords["y"]) - float(coords["y"])
            ),
            "depth": _round_mm(float(coords["z"]) - float(lowest_coords["z"])),
        }
    return calibrations


def _build_grbl_settings(
    raw_config: dict[str, Any],
    max_travel: dict[str, float],
) -> dict[str, Any]:
    return {
        "status_report": 0,
        "soft_limits": True,
        "homing_enable": True,
        "max_travel_x": max_travel["max_travel_x"],
        "max_travel_y": max_travel["max_travel_y"],
        "max_travel_z": max_travel["max_travel_z"],
    }


def _updated_yaml_text(
    raw_config: dict[str, Any],
    *,
    measured_coords: dict[str, float],
    instrument_calibrations: dict[str, dict[str, float]],
    max_travel: dict[str, float],
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
    updated["grbl_settings"] = _build_grbl_settings(raw_config, max_travel)

    instruments = updated.setdefault("instruments", {})
    for name, calibration in instrument_calibrations.items():
        entry = instruments.setdefault(name, {})
        entry.update(calibration)

    return yaml.safe_dump(updated, sort_keys=False)


def _validate_instrument_names(
    raw_config: dict[str, Any],
    names: Sequence[str],
) -> None:
    instruments = raw_config.get("instruments")
    if not isinstance(instruments, dict) or not instruments:
        raise ValueError("Gantry YAML must define top-level instruments to calibrate.")
    missing = [name for name in names if name not in instruments]
    if missing:
        available = ", ".join(sorted(instruments.keys()))
        raise ValueError(
            "Unknown instrument(s): "
            + ", ".join(missing)
            + f". Available instruments: {available}"
        )


def _instrument_names(raw_config: dict[str, Any]) -> tuple[str, ...]:
    instruments = raw_config.get("instruments")
    if not isinstance(instruments, dict) or not instruments:
        raise ValueError("Gantry YAML must define top-level instruments to calibrate.")
    return tuple(instruments.keys())


def _unique_instrument_sequence(names: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name not in seen:
            ordered.append(name)
            seen.add(name)
    return tuple(ordered)


def _prompt_z_reference_height_mm(
    *,
    input_reader: Callable[[str], str],
    output: Callable[[str], None],
) -> float:
    output("")
    output("Z reference: use a calibration block. The lowest instrument should touch the block top.")
    while True:
        raw = input_reader("Calibration block height in mm: ").strip()
        try:
            value = float(raw)
        except ValueError:
            output("Enter a numeric block height in millimeters.")
            continue
        if value <= 0:
            output("Calibration block height must be > 0 mm.")
            continue
        return value


def _looks_like_serial_device_not_configured(exc: Exception) -> bool:
    message = str(exc).lower()
    return "device not configured" in message


def _home_with_serial_reconnect(
    gantry: _GantryLike,
    *,
    output: Callable[[str], None],
) -> None:
    try:
        gantry.home()
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        if not _looks_like_serial_device_not_configured(exc):
            raise
        output(
            "Serial device disappeared during homing ('Device not configured'). "
            "Reconnecting once, then retrying $H."
        )
        gantry.disconnect()
        gantry.connect()
        gantry.home()


def _move_to_xy_center(
    gantry: _GantryLike,
    bounds_coords: dict[str, float],
    *,
    output: Callable[[str], None],
    label: str,
) -> dict[str, float]:
    center_x = _round_mm(float(bounds_coords["x"]) / 2.0)
    center_y = _round_mm(float(bounds_coords["y"]) / 2.0)
    z = float(bounds_coords["z"])
    output(
        f"Moving to deck XY center before {label}: "
        f"X={center_x:.3f} Y={center_y:.3f} while keeping Z={z:.3f}."
    )
    gantry.move_to(center_x, center_y, z)
    return dict(gantry.get_coordinates())


def _wait_until_idle_if_available(
    gantry: _GantryLike,
    *,
    timeout_s: float = 10.0,
    poll_interval_s: float = 0.1,
) -> None:
    status_reader = getattr(gantry, "get_status", None)
    if not callable(status_reader):
        return

    deadline = time.monotonic() + timeout_s
    last_status = ""
    while time.monotonic() < deadline:
        last_status = str(status_reader())
        if "idle" in last_status.lower():
            return
        time.sleep(poll_interval_s)

    raise RuntimeError(
        "Timed out waiting for gantry to become idle after jog; "
        f"last status: {last_status}"
    )


def _retract_up_after_contact(
    gantry: _GantryLike,
    *,
    retract_z_mm: float,
    feed_rate: float,
    output: Callable[[str], None],
) -> None:
    if retract_z_mm <= 0:
        return
    output(
        f"Raising Z by {retract_z_mm:g} mm before moving to the next tool/reference step."
    )
    gantry.jog(z=retract_z_mm, feed_rate=feed_rate)
    _wait_until_idle_if_available(gantry)


def run_multi_instrument_calibration(
    gantry_path: Path,
    *,
    reference_instrument: str | None = None,
    lowest_instrument: str | None = None,
    artifact_xyz: tuple[float, float, float] | None = None,
    instruments_to_calibrate: Sequence[str] | None = None,
    dry_run: bool = False,
    tolerance_mm: float = 0.25,
    jog_step_mm: float = 1.0,
    jog_feed_rate: float = 2000.0,
    post_contact_retract_z_mm: float = 15.0,
    skip_soft_limit_config: bool = False,
    write_gantry_yaml: bool = False,
    output_gantry_path: Path | None = None,
    homing_serial_timeout_s: float = 10.0,
    jog_serial_timeout_s: float = 1.0,
    output: Callable[[str], None] = print,
    input_reader: Callable[[str], str] = input,
    gantry_factory: Callable[..., _GantryLike] = Gantry,
    key_reader: KeyReader = read_keypress_batch,
    stdin_flusher: Callable[[], None] = flush_stdin,
) -> MultiInstrumentCalibrationResult | None:
    """Run the guided multi-instrument calibration flow."""
    gantry_path = gantry_path.resolve()
    gantry_config = load_gantry_from_yaml(gantry_path)
    validate_deck_origin_minima(gantry_config)
    raw_config = _load_raw_config(gantry_path)
    if output_gantry_path is not None:
        output_gantry_path = output_gantry_path.resolve()
    available_instruments = _instrument_names(raw_config)
    output(f"Loaded deck-origin gantry config: {gantry_path}")
    output("Calibration overview:")
    output("  This guided routine creates the shared CubOS deck frame for the whole instrument board.")
    output("  Step 1 sets the system origin: place the origin block/artifact in the front-left")
    output("  corner, then jog the first/left-most tool's active tip/probe point over the X mark.")
    output("  The script sets only G54 WPos X=0 and Y=0 there; Z is set later after the full")
    output("  instrument board is attached and the lowest mounted tool touches the reference point.")
    output("")
    reference_instrument = reference_instrument or _prompt_instrument_name(
        "Pick the number for the first/left-most tool for front-left origin",
        available_instruments,
        raw_config=raw_config,
        input_reader=input_reader,
        output=output,
    )
    if artifact_xyz is not None:
        output(
            "Ignoring deprecated artifact_xyz/--artifact-* input: the block point "
            "no longer needs known deck-frame coordinates."
        )
    instruments = tuple(instruments_to_calibrate or available_instruments)
    names_to_validate = [reference_instrument, *instruments]
    if lowest_instrument is not None:
        names_to_validate.append(lowest_instrument)
    _validate_instrument_names(raw_config, names_to_validate)
    if dry_run:
        output(f"Loaded deck-origin gantry config: {gantry_path}")
        output("Dry run only. Physical calibration flow:")
        output("  $H")
        output("  temporarily disable stale GRBL soft limits during calibration jogs")
        output("  attach the first/left-most tool at the homed pose")
        output("  place an origin block/artifact at the front-left corner")
        output("  jog that tool's active tip/probe point over the X mark as closely as possible")
        output("  G10 L20 P1 X0 Y0  # XY only, do not set Z here")
        output("  $H and read X/Y bounds")
        output("  move to measured X/Y center for calibration-block work")
        output("  attach all instruments and jog lowest instrument to the shared Z/block point")
        output("  enter the calibration block height")
        output("  G10 L20 P1 Z<block_height>")
        output("  record the lowest instrument's X/Y/Z block coordinate immediately")
        output("  jog each remaining instrument to that same block point and compute offsets/depths")
        output("  $H and read final working-volume maxima")
        return None

    output("Preflight:")
    output("  - Keep E-stop reachable; calibration can move mounted tools and changes G54 WPos.")
    output(f"  - First/left-most tool for front-left origin: {reference_instrument}")
    if lowest_instrument is None:
        output("  - The lowest mounted tool will be selected later, after the full board is attached/verified.")
    else:
        output(f"  - Lowest mounted tool for Z/reference point: {lowest_instrument}")
    output(
        "  - Calibration block/reference point: place it near the deck center where every "
        "instrument can reach the same physical point. The lowest instrument will "
        "define Z and be recorded there first; its X/Y/Z coordinates will not be "
        "requested a second time."
    )
    output("")

    gantry_runtime_config = copy.deepcopy(raw_config)
    gantry_runtime_config.pop("grbl_settings", None)
    gantry = gantry_factory(config=gantry_runtime_config)
    restore_soft_limits_after_calibration = False
    try:
        output("Connecting to gantry...")
        gantry.connect()

        output("Homing to normalized BRT corner...")
        _set_serial_timeout_if_available(gantry, homing_serial_timeout_s)
        _home_with_serial_reconnect(gantry, output=output)
        _set_serial_timeout_if_available(gantry, jog_serial_timeout_s)
        output("Forcing GRBL WPos status reporting ($10=0), G90, G54, and clearing G92...")
        gantry.enforce_work_position_reporting()
        gantry.activate_work_coordinate_system("G54")
        gantry.clear_g92_offsets()
        restore_soft_limits_after_calibration = (
            _temporarily_disable_soft_limits_for_origin_jog(
                gantry,
                output=output,
            )
        )
        stdin_flusher()

        output(
            f"Attach {reference_instrument!r} at the homed BRT pose before jogging. "
            "Place the front-left origin block/artifact in the front-left corner. "
            "No automatic center move will be made."
        )
        _interactive_jog_to_reference(
            gantry,
            target_description=(
                f"Step 1: attach {reference_instrument!r} at the homed pose. "
                "Place the origin block/artifact in the front-left corner, then "
                "jog the tool's active tip/probe point (tool center point) directly "
                "over the X mark as closely as possible. Do not use this step to define Z."
            ),
            confirmation_description=(
                "Press ENTER when current X/Y should become WPos X=0, Y=0. "
                "The script will not change WPos Z in this step."
            ),
            key_reader=key_reader,
            output=output,
            feed_rate=jog_feed_rate,
            initial_step_mm=jog_step_mm,
            limit_pull_off_mm=5.0,
        )
        output("Setting current physical pose to WPos X=0, Y=0 only...")
        gantry.set_work_coordinates(x=0.0, y=0.0)
        xy_origin_coords = dict(gantry.get_coordinates())
        _assert_near_xy_origin(xy_origin_coords, tolerance_mm=tolerance_mm)

        output("Re-homing after XY origining to measure machine-derived X/Y bounds...")
        _set_serial_timeout_if_available(gantry, homing_serial_timeout_s)
        _home_with_serial_reconnect(gantry, output=output)
        _set_serial_timeout_if_available(gantry, jog_serial_timeout_s)
        xy_bounds_coords = dict(gantry.get_coordinates())

        center_before_z_coords = _move_to_xy_center(
            gantry,
            xy_bounds_coords,
            output=output,
            label="lowest-instrument Z calibration",
        )
        output(
            "Attach/verify the full instrument board at the deck XY center before setting Z."
        )
        if lowest_instrument is None:
            lowest_instrument = _prompt_instrument_name(
                "Pick the number for the lowest mounted tool / first Z-reference touch",
                available_instruments,
                raw_config=raw_config,
                input_reader=input_reader,
                output=output,
            )
            _validate_instrument_names(raw_config, (lowest_instrument,))
        _interactive_jog_to_reference(
            gantry,
            target_description=(
                f"Step 2: from the deck XY center "
                f"(X={center_before_z_coords['x']:.3f}, "
                f"Y={center_before_z_coords['y']:.3f}), jog the lowest instrument "
                f"({lowest_instrument!r}) to the shared calibration block/reference point. "
                "This one touch records its X/Y/Z and defines Z."
            ),
            confirmation_description=(
                "Press ENTER when this lowest instrument is touching the shared point. "
                "X/Y will not be changed when assigning the Z work coordinate, and this "
                "instrument will not be requested again in the per-instrument pass."
            ),
            key_reader=key_reader,
            output=output,
            feed_rate=jog_feed_rate,
            initial_step_mm=jog_step_mm,
            limit_pull_off_mm=5.0,
        )
        z_reference_height_mm = _prompt_z_reference_height_mm(
            input_reader=input_reader,
            output=output,
        )
        output(
            f"Setting current physical pose to WPos Z={z_reference_height_mm:g} only..."
        )
        gantry.set_work_coordinates(z=z_reference_height_mm)
        z_origin_coords = dict(gantry.get_coordinates())
        _assert_near_xyz(
            z_origin_coords,
            expected={
                "x": z_origin_coords["x"],
                "y": z_origin_coords["y"],
                "z": z_reference_height_mm,
            },
            tolerance_mm=tolerance_mm,
            label="Lowest-instrument Z reference",
        )

        block_coordinates: dict[str, dict[str, float]] = {
            lowest_instrument: dict(z_origin_coords)
        }
        output(
            f"Recorded block WPos for lowest instrument {lowest_instrument}: "
            f"X={block_coordinates[lowest_instrument]['x']:.3f}, "
            f"Y={block_coordinates[lowest_instrument]['y']:.3f}, "
            f"Z={block_coordinates[lowest_instrument]['z']:.3f}"
        )
        _retract_up_after_contact(
            gantry,
            retract_z_mm=post_contact_retract_z_mm,
            feed_rate=jog_feed_rate,
            output=output,
        )
        output(
            "Now calibrate each remaining instrument against that same physical point. "
            "Do not move the block/reference point between instruments."
        )
        calibration_sequence = tuple(
            instrument
            for instrument in _unique_instrument_sequence(
                (reference_instrument, *instruments)
            )
            if instrument != lowest_instrument
        )
        for instrument in calibration_sequence:
            _interactive_jog_to_reference(
                gantry,
                target_description=(
                    f"Step 3: calibrate {instrument!r}. Jog this tool's active tip/probe point "
                    "(tool center point) to the same physical point used by the lowest instrument. The block's "
                    "deck-frame X/Y/Z coordinates do not need to be known."
                ),
                confirmation_description=(
                    "Press ENTER when this instrument is touching the same block point "
                    "used for the other instruments. Do not move the block between "
                    "instruments."
                ),
                key_reader=key_reader,
                output=output,
                feed_rate=jog_feed_rate,
                initial_step_mm=jog_step_mm,
                limit_pull_off_mm=5.0,
            )
            block_coordinates[instrument] = dict(gantry.get_coordinates())
            output(
                f"Recorded block WPos for {instrument}: "
                f"X={block_coordinates[instrument]['x']:.3f}, "
                f"Y={block_coordinates[instrument]['y']:.3f}, "
                f"Z={block_coordinates[instrument]['z']:.3f}"
            )
            _retract_up_after_contact(
                gantry,
                retract_z_mm=post_contact_retract_z_mm,
                feed_rate=jog_feed_rate,
                output=output,
            )

        output("Re-homing after instrument calibration to measure final working-volume maxima...")
        _set_serial_timeout_if_available(gantry, homing_serial_timeout_s)
        _home_with_serial_reconnect(gantry, output=output)
        _set_serial_timeout_if_available(gantry, jog_serial_timeout_s)
        measured_coords = dict(gantry.get_coordinates())
        max_travel = _calculate_grbl_max_travel(
            measured_coords,
            z_min_mm=0.0,
            tolerance_mm=tolerance_mm,
        )
        if skip_soft_limit_config:
            output("Skipping GRBL soft-limit programming by request.")
        else:
            gantry.configure_soft_limits_from_spans(
                max_travel_x=max_travel["max_travel_x"],
                max_travel_y=max_travel["max_travel_y"],
                max_travel_z=max_travel["max_travel_z"],
                tolerance_mm=tolerance_mm,
            )
            restore_soft_limits_after_calibration = False

        all_calibrations = compute_relative_instrument_calibrations(
            block_coordinates=block_coordinates,
            reference_instrument=reference_instrument,
            lowest_instrument=lowest_instrument,
        )
        instrument_calibrations = {
            instrument: all_calibrations[instrument]
            for instrument in instruments
        }
        for instrument, calibration in instrument_calibrations.items():
            output(
                f"Computed {instrument}: "
                f"offset_x={calibration['offset_x']:.3f}, "
                f"offset_y={calibration['offset_y']:.3f}, "
                f"depth={calibration['depth']:.3f}"
            )

        yaml_text = _updated_yaml_text(
            raw_config,
            measured_coords=measured_coords,
            instrument_calibrations=instrument_calibrations,
            max_travel=max_travel,
        )
        _print_yaml_block(
            title="Full calibrated multi-instrument gantry YAML to copy/paste:",
            yaml_text=yaml_text,
            output=output,
        )
        _maybe_write_gantry_yaml(
            yaml_text=yaml_text,
            output_path=output_gantry_path,
            write_requested=write_gantry_yaml,
            input_reader=input_reader,
            output=output,
        )

        return MultiInstrumentCalibrationResult(
            measured_working_volume=_coords_tuple(measured_coords),
            xy_bounds_after_origin=_coords_tuple(xy_bounds_coords),
            xy_origin_verification=_coords_tuple(xy_origin_coords),
            z_origin_verification=_coords_tuple(z_origin_coords),
            instrument_calibrations=instrument_calibrations,
            grbl_max_travel=(
                max_travel["max_travel_x"],
                max_travel["max_travel_y"],
                max_travel["max_travel_z"],
            ),
            reference_instrument=reference_instrument,
            lowest_instrument=lowest_instrument,
            block_reference_coordinates={
                name: _coords_tuple(coords)
                for name, coords in block_coordinates.items()
            },
        )
    finally:
        try:
            if restore_soft_limits_after_calibration:
                restore_soft_limits_after_calibration = False
                _restore_soft_limits_after_origin_jog(gantry, output=output)
        finally:
            _set_serial_timeout_if_available(gantry, 0.05)
            output("Disconnecting...")
            gantry.disconnect()


def _prompt_instrument_name(
    label: str,
    available: Sequence[str],
    *,
    raw_config: dict[str, Any] | None = None,
    input_reader: Callable[[str], str],
    output: Callable[[str], None],
) -> str:
    instruments = raw_config.get("instruments", {}) if isinstance(raw_config, dict) else {}
    output("Available instruments:")
    for index, name in enumerate(available, start=1):
        instrument_config = instruments.get(name, {}) if isinstance(instruments, dict) else {}
        instrument_type = instrument_config.get("type") if isinstance(instrument_config, dict) else None
        suffix = f" ({instrument_type})" if instrument_type else ""
        output(f"  {index}. {name}{suffix}")
    while True:
        raw = input_reader(f"{label}: ").strip()
        if not raw:
            output(f"Pick which numbered tool to use: enter 1 to {len(available)}.")
            continue
        try:
            selected_index = int(raw)
        except ValueError:
            output(f"Enter a number from 1 to {len(available)}.")
            continue
        if not 1 <= selected_index <= len(available):
            output(f"Enter a number from 1 to {len(available)}.")
            continue
        selected = available[selected_index - 1]
        confirm = input_reader(f"You selected #{selected_index} {selected}. Continue? [y/N]: ").strip().lower()
        if confirm in {"y", "yes"}:
            return selected
        output("Selection cancelled; pick the numbered tool again.")


def _prompt_float(
    prompt: str,
    *,
    input_reader: Callable[[str], str],
    output: Callable[[str], None],
) -> float:
    while True:
        raw = input_reader(prompt).strip()
        try:
            return float(raw)
        except ValueError:
            output("Enter a numeric value in millimeters.")


def _prompt_artifact_xyz(
    *,
    input_reader: Callable[[str], str],
    output: Callable[[str], None],
) -> tuple[float, float, float]:
    output("Enter the known deck-frame artifact/block point in millimeters.")
    return (
        _prompt_float("Artifact X mm: ", input_reader=input_reader, output=output),
        _prompt_float("Artifact Y mm: ", input_reader=input_reader, output=output),
        _prompt_float("Artifact Z mm: ", input_reader=input_reader, output=output),
    )


def _artifact_xyz_from_args(args: argparse.Namespace) -> tuple[float, float, float] | None:
    supplied = [args.artifact_x is not None, args.artifact_y is not None, args.artifact_z is not None]
    if not any(supplied):
        return None
    if not all(supplied):
        raise ValueError("Supply all of --artifact-x, --artifact-y, and --artifact-z, or none.")
    return (float(args.artifact_x), float(args.artifact_y), float(args.artifact_z))


InstrumentInfo = tuple[str, str | None]


def _load_seed_config(seed_path: Path) -> dict[str, Any]:
    if not seed_path.exists():
        raise ValueError(f"Seed gantry YAML does not exist: {seed_path}")
    with seed_path.open(encoding="utf-8") as handle:
        raw: Any = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError(f"Seed gantry YAML is empty or invalid: {seed_path}")
    return raw


def _instrument_info(raw_config: dict[str, Any]) -> tuple[InstrumentInfo, ...]:
    instruments = raw_config.get("instruments")
    if not isinstance(instruments, dict) or not instruments:
        raise ValueError("Seed gantry YAML must define at least one mounted instrument.")
    info: list[InstrumentInfo] = []
    for name, config in instruments.items():
        instrument_type = config.get("type") if isinstance(config, dict) else None
        info.append((str(name), str(instrument_type) if instrument_type else None))
    return tuple(info)


def _validate_seed_config(raw_config: dict[str, Any], *, seed_path: Path, output_path: Path) -> None:
    missing = [key for key in ("serial_port", "cnc", "working_volume", "instruments") if key not in raw_config]
    if missing:
        raise ValueError("Seed gantry YAML is missing required section(s): " + ", ".join(missing))

    if seed_path.resolve() == output_path.resolve():
        raise ValueError(
            "Refusing to overwrite the input seed. Use a different --output-gantry path."
        )

    working_volume = raw_config.get("working_volume")
    if not isinstance(working_volume, dict):
        raise ValueError("Seed gantry YAML must contain a working_volume mapping.")
    for key in ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max"):
        if key not in working_volume:
            raise ValueError(f"Seed gantry YAML working_volume is missing {key}.")
    for low, high in (("x_min", "x_max"), ("y_min", "y_max"), ("z_min", "z_max")):
        if float(working_volume[high]) <= float(working_volume[low]):
            raise ValueError(f"Seed gantry YAML has invalid working_volume {low}/{high}.")

    output_parent = output_path.resolve().parent
    if not output_parent.exists():
        raise ValueError(f"Output directory does not exist: {output_parent}")
    if not output_parent.is_dir():
        raise ValueError(f"Output parent is not a directory: {output_parent}")


def _format_instruments(instruments: tuple[InstrumentInfo, ...]) -> list[str]:
    lines: list[str] = []
    for index, (name, instrument_type) in enumerate(instruments, start=1):
        suffix = f" ({instrument_type})" if instrument_type else ""
        lines.append(f"  {index}. {name}{suffix}")
    return lines


def _confirm(prompt: str, *, input_reader: Callable[[str], str]) -> bool:
    return input_reader(prompt).strip().lower() in {"y", "yes"}


def _preflight(
    *,
    seed_path: Path,
    output_path: Path,
    instruments: tuple[InstrumentInfo, ...],
    flow_name: str,
    input_reader: Callable[[str], str],
    output: Callable[[str], None],
) -> None:
    output("")
    output("Calibration preflight")
    output("=====================")
    output(f"Input seed:              {seed_path}")
    output(f"Output calibrated YAML:  {output_path}")
    output(f"Detected instruments:    {len(instruments)}")
    for line in _format_instruments(instruments):
        output(line)
    output(f"Chosen flow:             {flow_name}")
    output("")
    output("Before continuing:")
    output("  - Keep E-stop reachable.")
    output("  - Clear the deck and mounted tools' travel path.")
    output("  - Use slow, careful jogs near fixtures, samples, and limits.")
    output("  - Do not run protocols from the output YAML until validation passes.")
    output("")

    seed_parts = seed_path.resolve().parts
    if "seeds" not in seed_parts:
        if not _confirm(
            "Input path does not look like configs/gantry/seeds/*.yaml. Continue? [y/N]: ",
            input_reader=input_reader,
        ):
            raise RuntimeError("Calibration cancelled before hardware connection.")
    if output_path.exists():
        if not _confirm(
            f"Output file already exists and will be overwritten: {output_path}. Continue? [y/N]: ",
            input_reader=input_reader,
        ):
            raise RuntimeError("Calibration cancelled before hardware connection.")

    if input_reader("Press ENTER to connect to hardware and start calibration, or Ctrl-C to abort: ") != "":
        output("Starting calibration...")


def _print_end_summary(
    result: Any,
    *,
    output_path: Path,
    output: Callable[[str], None],
) -> None:
    output("")
    output("Calibration complete")
    output("====================")
    output(f"Calibrated YAML written to: {output_path}")

    if isinstance(result, DeckOriginCalibrationResult):
        x_max, y_max, z_max = result.measured_working_volume
        output(f"Measured working volume: X 0..{x_max:.3f}, Y 0..{y_max:.3f}, Z {result.z_min_mm:.3f}..{z_max:.3f} mm")
        if result.grbl_max_travel is not None:
            gx, gy, gz = result.grbl_max_travel
            output(f"Calibration-managed GRBL max travel: X={gx:.3f}, Y={gy:.3f}, Z={gz:.3f} mm")
        if result.instrument_name:
            output(f"Calibrated instrument: {result.instrument_name}")

    elif isinstance(result, MultiInstrumentCalibrationResult):
        x_max, y_max, z_max = result.measured_working_volume
        output(f"Measured working volume: X 0..{x_max:.3f}, Y 0..{y_max:.3f}, Z 0..{z_max:.3f} mm")
        gx, gy, gz = result.grbl_max_travel
        output(f"Calibration-managed GRBL max travel: X={gx:.3f}, Y={gy:.3f}, Z={gz:.3f} mm")
        output(f"Reference/left-most instrument: {result.reference_instrument}")
        output(f"Lowest instrument: {result.lowest_instrument}")
        output("Instrument calibration values:")
        for name, values in result.instrument_calibrations.items():
            output(
                f"  {name}: offset_x={values['offset_x']:.3f}, "
                f"offset_y={values['offset_y']:.3f}, depth={values['depth']:.3f}"
            )

    output("")
    output("Next offline validation:")
    output("  python setup/validate_setup.py <calibrated-gantry.yaml> <deck.yaml> <protocol.yaml>")
    output("Do not run protocols until validation passes and hardware motion is sanity-checked.")


def run_auto_calibration(
    seed_path: Path,
    *,
    output_gantry_path: Path,
    output: Callable[[str], None] = print,
    input_reader: Callable[[str], str] = input,
):
    """Run calibration from a seed YAML and write a calibrated gantry YAML."""
    seed_path = seed_path.resolve()
    output_gantry_path = output_gantry_path.resolve()
    raw_config = _load_seed_config(seed_path)
    instruments = _instrument_info(raw_config)
    _validate_seed_config(raw_config, seed_path=seed_path, output_path=output_gantry_path)

    flow_name = (
        "single-instrument deck-origin calibration"
        if len(instruments) == 1
        else "multi-instrument board calibration"
    )
    _preflight(
        seed_path=seed_path,
        output_path=output_gantry_path,
        instruments=instruments,
        flow_name=flow_name,
        input_reader=input_reader,
        output=output,
    )

    if len(instruments) == 1:
        instrument_name = instruments[0][0]
        output(f"Using single-instrument flow for {instrument_name!r}.")
        result = run_calibration(
            seed_path,
            instrument_name=instrument_name,
            z_reference_mode="block",
            write_gantry_yaml=True,
            output_gantry_path=output_gantry_path,
            output=output,
            input_reader=input_reader,
        )
    else:
        output(f"Using multi-instrument flow for {len(instruments)} mounted instruments.")
        result = run_multi_instrument_calibration(
            seed_path,
            write_gantry_yaml=True,
            output_gantry_path=output_gantry_path,
            output=output,
            input_reader=input_reader,
        )

    _print_end_summary(result, output_path=output_gantry_path, output=output)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calibrate a gantry from a seed YAML and write a calibrated gantry YAML.",
        epilog=(
            "Examples:\n"
            "  PYTHONPATH=src python setup/calibrate_gantry.py "
            "--seed configs/gantry/seeds/cub_xl_asmi.yaml "
            "--output-gantry configs/gantry/cub_xl_asmi.yaml\n"
            "  PYTHONPATH=src python setup/calibrate_gantry.py "
            "--seed configs/gantry/seeds/cub_xl_sterling_3_instrument.yaml "
            "--output-gantry configs/gantry/cub_xl_sterling_3_instrument.yaml"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--seed", type=Path, required=True, help="Input seed gantry YAML.")
    parser.add_argument(
        "--output-gantry",
        type=Path,
        required=True,
        help="Output path for calibrated gantry YAML. Must differ from --seed.",
    )
    args = parser.parse_args()

    try:
        run_auto_calibration(args.seed, output_gantry_path=args.output_gantry)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
