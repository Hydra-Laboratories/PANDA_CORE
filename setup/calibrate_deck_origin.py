"""Interactively calibrate GRBL WPos for the CubOS deck-origin frame.

This is the Phase 2/3 one-instrument calibration path. It does not assume that
the configured or manufacturer working-volume values are physically correct.
Instead, it separates XY origining from Z assignment:

1. Jog one attached reference instrument/TCP as far as appropriate toward the
   physical front-left XY origin and its lowest safe reachable Z, then assign
   only X/Y to 0.
2. If the TCP is touching true deck bottom, assign Z to 0. If it cannot reach
   bottom, measure the deck-to-TCP gap with a ruler and assign Z to that gap.
3. Re-home and read the measured WPos at the homed back-right-top corner.

Usage:

    python setup/calibrate_deck_origin.py --gantry configs/gantry/cub_xl_asmi.yaml
    python setup/calibrate_deck_origin.py --gantry configs/gantry/cub_xl_asmi.yaml --dry-run
"""

from __future__ import annotations

import argparse
import copy
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import yaml

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from board.yaml_schema import BoardYamlSchema  # noqa: E402
from gantry import Gantry, load_gantry_from_yaml  # noqa: E402
from gantry.gantry_driver.exceptions import (  # noqa: E402
    CommandExecutionError,
    MillConnectionError,
    StatusReturnError,
)
from gantry.grbl_settings import normalize_expected_grbl_settings  # noqa: E402
from gantry.origin import (  # noqa: E402
    DeckOriginCalibrationPlan,
    build_deck_origin_calibration_plan,
)
from setup.keyboard_input import flush_stdin, read_keypress_batch  # noqa: E402


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


CONTROLS_LEGEND = """
Jog controls after homing:
  RIGHT / LEFT       +X right / -X left
  UP / DOWN          +Y back-away / -Y front-toward-operator
  X / Z              +Z up / -Z down
  1 / 2 / 3 / 4 / 5  Set jog step to 0.1 / 1 / 5 / 10 / 25 mm
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


def _load_raw_yaml_dict(path: Path, *, label: str) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{label} YAML is empty or invalid: {path}")
    return data


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
    updated.pop("grbl_settings", None)
    return yaml.safe_dump(updated, sort_keys=False)


def _build_board_grbl_settings(
    *,
    board_raw: dict[str, Any],
    gantry_raw: dict[str, Any],
    max_travel: dict[str, float],
) -> dict[str, Any]:
    settings: dict[str, Any] = {}
    gantry_settings = gantry_raw.get("grbl_settings")
    if isinstance(gantry_settings, dict):
        settings.update(gantry_settings)
    board_settings = board_raw.get("grbl_settings")
    if isinstance(board_settings, dict):
        settings.update(board_settings)
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


def _updated_board_yaml_text(
    board_path: Path,
    *,
    gantry_raw: dict[str, Any],
    max_travel: dict[str, float],
) -> str:
    board_raw = _load_raw_yaml_dict(board_path, label="Board")
    updated = copy.deepcopy(board_raw)
    updated["grbl_settings"] = _build_board_grbl_settings(
        board_raw=board_raw,
        gantry_raw=gantry_raw,
        max_travel=max_travel,
    )
    BoardYamlSchema.model_validate(updated)
    return yaml.safe_dump(updated, sort_keys=False)


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


def _maybe_write_board_yaml(
    *,
    yaml_text: str,
    output_path: Path | None,
    write_requested: bool,
    input_reader: Callable[[str], str],
    output: Callable[[str], None],
) -> None:
    if output_path is None and not write_requested:
        return
    if output_path is None:
        raw = input_reader("Output board YAML filename: ").strip()
        if not raw:
            output("No board YAML filename supplied; skipping write.")
            return
        output_path = Path(raw)
    confirm = input_reader(
        f"Write updated board YAML to {output_path}? [y/N]: "
    ).strip().lower()
    if confirm not in ("y", "yes"):
        output("Skipping board YAML write.")
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml_text, encoding="utf-8")
    output(f"Wrote updated board YAML: {output_path}")


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


def _opposite_pull_off_delta(
    delta: dict[str, float],
    pull_off_mm: float,
) -> dict[str, float]:
    pull_off = {"x": 0.0, "y": 0.0, "z": 0.0}
    for axis, value in delta.items():
        if value > 0:
            pull_off[axis] = -pull_off_mm
        elif value < 0:
            pull_off[axis] = pull_off_mm
    return pull_off


def _recover_from_limit_alarm(
    gantry: _GantryLike,
    delta: dict[str, float],
    *,
    pull_off_mm: float,
    feed_rate: float,
    output: Callable[[str], None],
) -> dict[str, float] | None:
    pull_off = _opposite_pull_off_delta(delta, pull_off_mm)
    output(
        "Limit alarm detected. Unlocking GRBL and pulling off the switch "
        f"by {pull_off_mm:g} mm."
    )
    try:
        gantry.jog_cancel()
    except MillConnectionError:
        raise
    except (CommandExecutionError, StatusReturnError) as exc:
        output(f"Jog cancel during recovery failed: {exc}")
        output("Aborting calibration; use E-stop and rerun before continuing.")
        raise

    try:
        gantry.unlock()
    except MillConnectionError:
        raise
    except (CommandExecutionError, StatusReturnError) as exc:
        output(f"Unlock during limit recovery failed: {exc}")
        output("Use the controller/E-stop reset path before continuing.")
        raise

    try:
        gantry.jog(feed_rate=feed_rate, **pull_off)
    except MillConnectionError:
        raise
    except (CommandExecutionError, StatusReturnError) as exc:
        output(f"Automatic pull-off jog failed: {exc}")
        output("Aborting calibration; gantry position is unknown.")
        raise

    try:
        return gantry.get_coordinates()
    except MillConnectionError:
        raise
    except (CommandExecutionError, StatusReturnError) as exc:
        output(f"WPos readback after pull-off failed: {exc}")
        output("Aborting calibration; gantry position is unknown.")
        raise


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
        except MillConnectionError:
            raise
        except (CommandExecutionError, StatusReturnError) as exc:
            if not _looks_like_limit_alarm(exc):
                output(f"Jog command rejected by controller: {exc}")
                output("Aborting calibration; gantry position is unknown.")
                raise
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
    limit_pull_off_mm: float = 2.0,
    tip_gap_mm: float | None = None,
    reference_surface_z_mm: float | None = None,
    z_reference_mode: str = "bottom",
    measure_reachable_z_min: bool | None = False,
    instrument_name: str | None = None,
    board_path: Path | None = None,
    skip_soft_limit_config: bool = False,
    write_board_yaml: bool = False,
    output_board_path: Path | None = None,
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
    board_expected_grbl_settings = None
    if board_path is not None:
        board_path = board_path.resolve()
        board_schema = BoardYamlSchema.model_validate(
            _load_raw_yaml_dict(board_path, label="Board")
        )
        board_expected_grbl_settings = normalize_expected_grbl_settings(
            board_schema.grbl_settings
        )
    if output_board_path is not None:
        output_board_path = output_board_path.resolve()
    if (write_board_yaml or output_board_path is not None) and board_path is None:
        raise ValueError("--board is required when writing updated board YAML.")
    plan = build_deck_origin_calibration_plan(gantry_config)
    if reference_surface_z_mm is not None:
        if tip_gap_mm is not None:
            raise ValueError("Use only one of tip_gap_mm or reference_surface_z_mm.")
        tip_gap_mm = reference_surface_z_mm
    deprecated_known_height_mode = z_reference_mode == "known-height"
    if deprecated_known_height_mode:
        z_reference_mode = "ruler-gap"
    if z_reference_mode not in ("prompt", "bottom", "ruler-gap"):
        raise ValueError("z_reference_mode must be one of: prompt, bottom, ruler-gap")
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
    output("  - GRBL orientation must already be normalized.")
    output("  - $H must home to back-right-top.")
    output("  - +X must jog right, +Y back/away, +Z up.")
    output("  - Attach exactly one reference instrument/TCP for this calibration.")
    output(
        "  - Jog to the front-left XY origin and the lowest safe reachable Z "
        "for that TCP."
    )
    output("  - This will set G54 WPos X=0, Y=0 at that pose.")
    output(
        "  - If the TCP touches deck bottom, Z will be set to 0; otherwise "
        "enter the ruler-measured deck-to-TCP gap."
    )
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
    if board_expected_grbl_settings and hasattr(gantry, "set_expected_grbl_settings"):
        gantry.set_expected_grbl_settings(
            board_expected_grbl_settings,
            source=str(board_path),
        )
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

        _interactive_jog_to_xy_origin(
            gantry,
            key_reader=key_reader,
            output=output,
            feed_rate=jog_feed_rate,
            initial_step_mm=jog_step_mm,
            limit_pull_off_mm=limit_pull_off_mm,
        )

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
        output("")
        output("Measured GRBL max-travel spans for soft limits:")
        output(f"  $130 X max travel: {max_travel['max_travel_x']:.3f} mm")
        output(f"  $131 Y max travel: {max_travel['max_travel_y']:.3f} mm")
        output(f"  $132 Z max travel: {max_travel['max_travel_z']:.3f} mm")

        if skip_soft_limit_config:
            output("Skipping GRBL soft-limit programming by request.")
        else:
            output("Programming GRBL soft limits from measured travel spans...")
            gantry.configure_soft_limits_from_spans(
                max_travel_x=max_travel["max_travel_x"],
                max_travel_y=max_travel["max_travel_y"],
                max_travel_z=max_travel["max_travel_z"],
                tolerance_mm=tolerance_mm,
            )
            output("Re-homing after updating GRBL travel settings...")
            _set_serial_timeout_if_available(gantry, homing_serial_timeout_s)
            gantry.home()
            _set_serial_timeout_if_available(gantry, jog_serial_timeout_s)
            output("Reassigning G54 at homed pose to measured WPos maxima...")
            gantry.activate_work_coordinate_system("G54")
            gantry.set_work_coordinates(
                x=float(measured_coords["x"]),
                y=float(measured_coords["y"]),
                z=float(measured_coords["z"]),
            )
            final_homed_coords = dict(gantry.get_coordinates())
            _assert_near_xyz(
                final_homed_coords,
                expected={
                    "x": float(measured_coords["x"]),
                    "y": float(measured_coords["y"]),
                    "z": float(measured_coords["z"]),
                },
                tolerance_mm=tolerance_mm,
                label="Final homed WPos after soft-limit setup",
            )
            output(
                "Verified final homed WPos: "
                f"X={final_homed_coords['x']:.3f} "
                f"Y={final_homed_coords['y']:.3f} "
                f"Z={final_homed_coords['z']:.3f}"
            )

        _print_config_patch(
            measured_coords,
            z_reference_coords=z_reference_coords,
            z_min_mm=z_min_mm,
            z_reference_mode=z_reference_mode,
            instrument_name=instrument_name,
            output=output,
        )
        _print_yaml_block(
            title="Full gantry YAML to copy/paste:",
            yaml_text=_updated_gantry_yaml_text(
                raw_config,
                measured_coords=measured_coords,
                z_min_mm=z_min_mm,
            ),
            output=output,
        )

        if board_path is not None:
            board_yaml_text = _updated_board_yaml_text(
                board_path,
                gantry_raw=raw_config,
                max_travel=max_travel,
            )
            _print_yaml_block(
                title="Full board YAML to copy/paste:",
                yaml_text=board_yaml_text,
                output=output,
            )
            _maybe_write_board_yaml(
                yaml_text=board_yaml_text,
                output_path=output_board_path,
                write_requested=write_board_yaml,
                input_reader=input_reader,
                output=output,
            )
        else:
            output("")
            output("No --board supplied; skipping full board YAML output.")

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
        _set_serial_timeout_if_available(gantry, 0.05)
        output("Disconnecting...")
        gantry.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Interactively assign X/Y at the front-left origin/lower reach "
            "point, assign Z from bottom contact or a ruler-measured TCP gap, "
            "then measure homed WPos as the real work volume."
        )
    )
    parser.add_argument(
        "--gantry",
        type=Path,
        required=True,
        help="Deck-origin gantry YAML from configs/gantry.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the physical calibration flow without connecting to hardware.",
    )
    parser.add_argument(
        "--tip-gap-mm",
        type=float,
        default=None,
        help=(
            "Ruler-measured vertical gap from deck to TCP when the instrument "
            "cannot reach true deck bottom. Used with --z-reference-mode "
            "ruler-gap."
        ),
    )
    parser.add_argument(
        "--reference-z-mm",
        type=float,
        default=None,
        help=(
            "Deprecated alias for --tip-gap-mm from the old known-height flow."
        ),
    )
    parser.add_argument(
        "--z-reference-mode",
        choices=("prompt", "bottom", "ruler-gap", "known-height"),
        default="prompt",
        help=(
            "How to assign absolute Z. 'prompt' asks after jogging to lower "
            "reach; 'bottom' sets Z=0 at true-bottom contact; 'ruler-gap' "
            "uses --tip-gap-mm or prompts for the measured deck-to-TCP gap. "
            "'known-height' is a deprecated alias for ruler-gap."
        ),
    )
    parser.add_argument(
        "--instrument",
        dest="instrument_name",
        default=None,
        help="Optional instrument/TCP label used in reach-limit output, e.g. asmi.",
    )
    parser.add_argument(
        "--board",
        type=Path,
        default=None,
        help="Board YAML to merge calibrated GRBL settings into for copy/paste output.",
    )
    parser.add_argument(
        "--skip-soft-limit-config",
        action="store_true",
        help="Do not program GRBL soft limits after measuring the working volume.",
    )
    parser.add_argument(
        "--write-board-yaml",
        action="store_true",
        help="Prompt for a filename and write the updated board YAML after confirmation.",
    )
    parser.add_argument(
        "--output-board",
        type=Path,
        default=None,
        help="Write updated board YAML to this path after confirmation.",
    )
    reach_group = parser.add_mutually_exclusive_group()
    reach_group.add_argument(
        "--measure-reachable-z-min",
        dest="measure_reachable_z_min",
        action="store_true",
        help=(
            "Deprecated; lower reach is now recorded from the origin/gap "
            "calibration point."
        ),
    )
    reach_group.add_argument(
        "--skip-reachable-z-min",
        dest="measure_reachable_z_min",
        action="store_false",
        help="Deprecated no-op retained for compatibility.",
    )
    parser.set_defaults(measure_reachable_z_min=None)
    parser.add_argument(
        "--tolerance-mm",
        type=float,
        default=0.25,
        help="Allowed WPos verification error after setting origin.",
    )
    parser.add_argument(
        "--jog-step-mm",
        type=float,
        default=1.0,
        help="Initial jog step size for interactive origin positioning.",
    )
    parser.add_argument(
        "--jog-feed-rate",
        type=float,
        default=2500.0,
        help="Feed rate used for interactive jog moves.",
    )
    parser.add_argument(
        "--limit-pull-off-mm",
        type=float,
        default=2.0,
        help="Distance to pull off in the opposite direction after a limit alarm.",
    )
    parser.add_argument(
        "--homing-serial-timeout-s",
        type=float,
        default=10.0,
        help="Serial read timeout while homing.",
    )
    parser.add_argument(
        "--jog-serial-timeout-s",
        type=float,
        default=1.0,
        help="Serial read timeout while interactively jogging.",
    )
    args = parser.parse_args()

    try:
        run_calibration(
            args.gantry,
            dry_run=args.dry_run,
            tolerance_mm=args.tolerance_mm,
            jog_step_mm=args.jog_step_mm,
            jog_feed_rate=args.jog_feed_rate,
            limit_pull_off_mm=args.limit_pull_off_mm,
            tip_gap_mm=args.tip_gap_mm,
            reference_surface_z_mm=args.reference_z_mm,
            z_reference_mode=args.z_reference_mode,
            measure_reachable_z_min=args.measure_reachable_z_min,
            instrument_name=args.instrument_name,
            board_path=args.board,
            skip_soft_limit_config=args.skip_soft_limit_config,
            write_board_yaml=args.write_board_yaml,
            output_board_path=args.output_board,
            homing_serial_timeout_s=args.homing_serial_timeout_s,
            jog_serial_timeout_s=args.jog_serial_timeout_s,
        )
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
