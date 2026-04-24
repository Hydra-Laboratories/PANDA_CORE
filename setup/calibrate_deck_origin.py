"""Interactively calibrate GRBL WPos for the CubOS deck-origin frame.

This is the Phase 2/3 one-instrument calibration path. It does not assume that
the configured or manufacturer working-volume values are physically correct.
Instead, it separates XY origining from Z grounding:

1. Jog one attached reference instrument/TCP as far as appropriate toward the
   physical front-left XY origin/lower reach point, then assign only X/Y to 0.
2. Jog that TCP to a known-height labware/artifact reference surface, such as
   well plate A1, then assign only Z to that surface height.
3. Re-home and read the measured WPos at the homed back-right-top corner.

Usage:

    python setup/calibrate_deck_origin.py --gantry configs_new/gantry/cub_xl_asmi_deck_origin.yaml
    python setup/calibrate_deck_origin.py --gantry configs_new/gantry/cub_xl_asmi_deck_origin.yaml --dry-run
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

import yaml

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from gantry import Gantry, load_gantry_from_yaml  # noqa: E402
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
    reference_surface_z_mm: float
    z_reference_mode: str
    reachable_z_min_mm: float | None
    instrument_name: str | None
    plan: DeckOriginCalibrationPlan

    @property
    def reference_verification(self) -> tuple[float, float, float]:
        """Backward-compatible alias for the final Z-reference verification."""
        return self.z_reference_verification


class _GantryLike(Protocol):
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def home(self) -> None: ...
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


KeyReader = Callable[[], tuple[str, int]]


CONTROLS_LEGEND = """
Jog controls after homing:
  RIGHT / LEFT       +X right / -X left
  UP / DOWN          +Y back-away / -Y front-toward-operator
  X / Z              +Z up / -Z down
  1 / 2 / 3          Set jog step to 0.1 / 1.0 / 5.0 mm
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
    reference_surface_z_mm: float,
    tolerance_mm: float,
) -> None:
    expected = {"z": reference_surface_z_mm}
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
    reference_surface_z_mm: float,
    z_reference_mode: str,
    reachable_z_min_mm: float | None,
    instrument_name: str | None,
    output: Callable[[str], None],
) -> None:
    x_max, y_max, z_max = _coords_tuple(coords)
    output("")
    output("Measured physical working volume from calibrated origin:")
    output(f"  X: 0.000 to {x_max:.3f} mm")
    output(f"  Y: 0.000 to {y_max:.3f} mm")
    output(f"  Z: 0.000 to {z_max:.3f} mm")
    output("")
    output("Update the gantry YAML working_volume to:")
    output("  working_volume:")
    output("    x_min: 0.0")
    output(f"    x_max: {x_max:.3f}")
    output("    y_min: 0.0")
    output(f"    y_max: {y_max:.3f}")
    output("    z_min: 0.0")
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
    output(
        "If that reference was plate A1, use these X/Y/Z values as the "
        "deck calibration point for A1."
    )

    if reachable_z_min_mm is not None:
        reach_name = instrument_name or "reference_tcp"
        output("")
        output("Measured one-instrument reachable lower Z:")
        output(f"  {reach_name}_reachable_z_min: {reachable_z_min_mm:.3f} mm")
        output("")
        output("Suggested per-instrument reach note:")
        output("  instrument_reach:")
        output(f"    {reach_name}:")
        output(f"      z_min_reachable: {reachable_z_min_mm:.3f}")
        output(
            "This is a per-instrument reach note. The deck bottom remains "
            "absolute Z=0, but this TCP should not be commanded below the "
            "recorded reachable Z until per-instrument reach limits are modeled."
        )
    elif reference_surface_z_mm > 0:
        output("")
        output(
            "Reference surface was above deck Z=0. This grounds the absolute "
            "Z transform, but does not prove this TCP can physically reach "
            "deck Z=0."
        )
        output(
            "Run again with --measure-reachable-z-min if you want the script "
            "to record the lowest safe reachable Z for this one-instrument setup."
        )


def _print_dry_run(
    gantry_path: Path,
    plan: DeckOriginCalibrationPlan,
    *,
    reference_surface_z_mm: float | None,
    z_reference_mode: str,
    measure_reachable_z_min: bool,
    instrument_name: str | None,
    output: Callable[[str], None],
) -> None:
    output(f"Loaded deck-origin gantry config: {gantry_path}")
    if instrument_name:
        output(f"Instrument/TCP: {instrument_name}")
    output(f"Z reference mode: {z_reference_mode}")
    output("Dry run only. Physical calibration flow:")
    commands = _commands_for_reference_height(
        plan,
        reference_surface_z_mm,
        z_reference_mode=z_reference_mode,
    )
    pre_measure_commands = commands[:-2] if measure_reachable_z_min else commands
    post_measure_commands = commands[-2:] if measure_reachable_z_min else ()
    for command in pre_measure_commands:
        output(f"  {command}")
    if measure_reachable_z_min:
        output("  <optional jog to lowest safe reachable Z for this TCP>")
        for command in post_measure_commands:
            output(f"  {command}")
        output("")
        output("The optional reachable-Z step records a per-instrument lower bound.")
    output("")
    output("No configured max travel values will be trusted as measured volume.")


def _commands_for_reference_height(
    plan: DeckOriginCalibrationPlan,
    reference_surface_z_mm: float | None,
    *,
    z_reference_mode: str = "known-height",
) -> tuple[str, ...]:
    z_value = (
        "<reference_surface_z_mm>"
        if reference_surface_z_mm is None
        else f"{reference_surface_z_mm:g}"
    )
    z_reference_jog = (
        "<interactive jog to true deck-bottom Z contact>"
        if z_reference_mode == "bottom"
        else "<interactive jog to labware/artifact Z reference surface>"
    )
    return tuple(
        command.replace("<reference_surface_z_mm>", z_value).replace(
            "<interactive jog to labware/artifact Z reference surface>",
            z_reference_jog,
        )
        for command in plan.commands
    )


def _prompt_reference_surface_z_mm(
    *,
    input_reader: Callable[[str], str],
    output: Callable[[str], None],
) -> float:
    output("")
    output(
        "Reference surface Z height is the known labware/artifact surface "
        "height above true deck/bottom Z=0."
    )
    output(
        "Use 0 only if this second Z-reference surface is the true bottom "
        "plane."
    )
    while True:
        raw = input_reader("Reference surface Z height in mm: ").strip()
        try:
            value = float(raw)
        except ValueError:
            output("Enter a numeric height in millimeters.")
            continue
        if value < 0:
            output("Reference surface height must be >= 0 mm.")
            continue
        return value


def _prompt_z_reference_mode(
    *,
    input_reader: Callable[[str], str],
    output: Callable[[str], None],
) -> str:
    output("")
    output("Z grounding mode:")
    output("  y = this TCP can safely touch true deck bottom, so set Z=0 there")
    output("  n = no/unsure; use a known-height labware/artifact surface, e.g. A1")
    while True:
        raw = input_reader(
            "Can this instrument safely touch true deck bottom? [y/N]: "
        ).strip().lower()
        if raw in ("", "n", "no", "u", "unsure"):
            return "known-height"
        if raw in ("y", "yes"):
            return "bottom"
        output("Enter y for true-bottom contact, or n/Enter for known-height reference.")


def _prompt_measure_reachable_z_min(
    *,
    input_reader: Callable[[str], str],
    output: Callable[[str], None],
    instrument_name: str | None,
) -> bool:
    recommended = (
        (instrument_name or "").strip().lower() in {"asmi", "indentation", "force"}
    )
    default = "Y" if recommended else "n"
    output("")
    output(
        "Lowest reachable Z is separate from absolute Z grounding. It records "
        "how low this one TCP can safely go after WPos is calibrated."
    )
    if recommended:
        output("Recommended for ASMI/indentation because motion can go below A1.")
    while True:
        raw = input_reader(
            f"Measure lowest reachable Z for this instrument? [{default}]: "
        ).strip().lower()
        if raw == "":
            return recommended
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        output("Enter y or n.")


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
    except Exception as exc:
        output(f"Jog cancel during recovery did not complete: {exc}")

    try:
        gantry.unlock()
    except Exception as exc:
        output(f"Unlock during limit recovery failed: {exc}")
        output("Use the controller/E-stop reset path before continuing.")
        return None

    try:
        gantry.jog(feed_rate=feed_rate, **pull_off)
    except Exception as exc:
        output(f"Automatic pull-off jog did not complete: {exc}")
        output("Try a small jog in the opposite direction, or press Q to abort.")
        return None

    try:
        return gantry.get_coordinates()
    except Exception as exc:
        output(f"Pull-off sent, but WPos readback is not available yet: {exc}")
        output("Continue with small opposite-direction jogs, or press Q to abort.")
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
        except Exception as exc:
            if not _looks_like_limit_alarm(exc):
                output(f"WPos readback after jog failed: {exc}")
                output("Continuing; press Q to abort if the machine state is unclear.")
                continue
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
            "Step 1/2: jog the one reference TCP as far as appropriate toward "
            "the physical front-left XY origin/lower reach point."
        ),
        confirmation_description=(
            "Press ENTER only when the current X/Y should become WPos X=0, "
            "Y=0. Z will not be assigned in this step."
        ),
        key_reader=key_reader,
        output=output,
        feed_rate=feed_rate,
        initial_step_mm=initial_step_mm,
        limit_pull_off_mm=limit_pull_off_mm,
    )


def _interactive_jog_to_z_reference(
    gantry: _GantryLike,
    *,
    reference_surface_z_mm: float,
    z_reference_mode: str,
    key_reader: KeyReader,
    output: Callable[[str], None],
    feed_rate: float,
    initial_step_mm: float,
    limit_pull_off_mm: float,
) -> dict[str, float]:
    if z_reference_mode == "bottom":
        target_description = (
            "Step 2/2: jog the same reference TCP to true deck-bottom contact."
        )
        confirmation_description = (
            "Press ENTER only when the current Z should become WPos Z=0. "
            "X/Y will not be reassigned."
        )
    else:
        target_description = (
            "Step 2/2: jog the same reference TCP to the known-height "
            "labware/artifact surface, for example plate A1."
        )
        confirmation_description = (
            "Press ENTER only when the current Z should become "
            f"WPos Z={reference_surface_z_mm:g}. X/Y will not be reassigned."
        )
    return _interactive_jog_to_reference(
        gantry,
        target_description=target_description,
        confirmation_description=confirmation_description,
        key_reader=key_reader,
        output=output,
        feed_rate=feed_rate,
        initial_step_mm=initial_step_mm,
        limit_pull_off_mm=limit_pull_off_mm,
    )


def _interactive_jog_to_reachable_z_min(
    gantry: _GantryLike,
    *,
    key_reader: KeyReader,
    output: Callable[[str], None],
    feed_rate: float,
    initial_step_mm: float,
    limit_pull_off_mm: float,
) -> dict[str, float]:
    output("")
    output("Optional reachable-Z measurement:")
    output("Jog only as low as this one reference TCP can safely reach.")
    output("This records a lower reach bound; it does not reset WPos.")
    return _interactive_jog_to_reference(
        gantry,
        target_description=(
            "Jog to the lowest safe reachable Z for this reference TCP. "
            "Keep X/Y at a safe location."
        ),
        confirmation_description=(
            "Press ENTER when the current WPos Z is the lowest safe reachable "
            "Z you want to record for this one-instrument setup."
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
    jog_feed_rate: float = 800.0,
    limit_pull_off_mm: float = 2.0,
    reference_surface_z_mm: float | None = 0.0,
    z_reference_mode: str = "known-height",
    measure_reachable_z_min: bool | None = False,
    instrument_name: str | None = None,
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
    plan = build_deck_origin_calibration_plan(gantry_config)

    if dry_run:
        dry_run_reference_z_mm = reference_surface_z_mm
        if z_reference_mode == "bottom":
            dry_run_reference_z_mm = 0.0
        _print_dry_run(
            gantry_path,
            plan,
            reference_surface_z_mm=dry_run_reference_z_mm,
            z_reference_mode=z_reference_mode,
            measure_reachable_z_min=bool(measure_reachable_z_min),
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
    output("  - Step 1 sets only X/Y at the front-left origin/lower reach point.")
    output("  - Step 2 sets only Z at true bottom or a known-height surface.")
    output("  - For ASMI, the second point can be well plate A1.")
    output("  - This will set G54 WPos X=0, Y=0, then the chosen Z reference.")
    if measure_reachable_z_min is True:
        output("  - After WPos is set, this will record the TCP's lowest reachable Z.")
    if instrument_name:
        output(f"  - Instrument/TCP label for reach output: {instrument_name}")
    output("")

    gantry = gantry_factory(config=raw_config)
    try:
        output("Connecting to gantry...")
        gantry.connect()

        output("Homing to normalized back-right-top corner...")
        _set_serial_timeout_if_available(gantry, homing_serial_timeout_s)
        gantry.home()
        _set_serial_timeout_if_available(gantry, jog_serial_timeout_s)
        output("Clearing transient G92 offsets before origin calibration...")
        gantry.clear_g92_offsets()
        stdin_flusher()

        if z_reference_mode not in ("prompt", "bottom", "known-height"):
            raise ValueError(
                "z_reference_mode must be one of: prompt, bottom, known-height"
            )
        if z_reference_mode == "prompt":
            z_reference_mode = _prompt_z_reference_mode(
                input_reader=input_reader,
                output=output,
            )
        if z_reference_mode == "bottom":
            if reference_surface_z_mm not in (None, 0.0):
                raise ValueError(
                    "Bottom Z reference mode must use reference_surface_z_mm=0."
                )
            reference_surface_z_mm = 0.0
        elif reference_surface_z_mm is None:
            reference_surface_z_mm = _prompt_reference_surface_z_mm(
                input_reader=input_reader,
                output=output,
            )
        if reference_surface_z_mm < 0:
            raise ValueError("reference_surface_z_mm must be >= 0")
        if z_reference_mode == "known-height" and reference_surface_z_mm == 0:
            output(
                "Reference height is 0 in known-height mode. That is allowed, "
                "but only if the second Z-reference point is true deck bottom."
            )
        output(
            "Known Z reference surface will be assigned as "
            f"WPos Z={reference_surface_z_mm:g} mm."
        )

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

        _interactive_jog_to_z_reference(
            gantry,
            reference_surface_z_mm=reference_surface_z_mm,
            z_reference_mode=z_reference_mode,
            key_reader=key_reader,
            output=output,
            feed_rate=jog_feed_rate,
            initial_step_mm=jog_step_mm,
            limit_pull_off_mm=limit_pull_off_mm,
        )

        output("Setting current physical pose to reference WPos Z...")
        gantry.set_work_coordinates(z=reference_surface_z_mm)
        z_reference_coords = dict(gantry.get_coordinates())
        _assert_near_z_reference(
            z_reference_coords,
            reference_surface_z_mm=reference_surface_z_mm,
            tolerance_mm=tolerance_mm,
        )
        output(
            "Verified Z reference WPos: "
            f"X={z_reference_coords['x']:.3f} "
            f"Y={z_reference_coords['y']:.3f} "
            f"Z={z_reference_coords['z']:.3f}"
        )

        if measure_reachable_z_min is None:
            measure_reachable_z_min = _prompt_measure_reachable_z_min(
                input_reader=input_reader,
                output=output,
                instrument_name=instrument_name,
            )
        reachable_z_min_mm = None
        if measure_reachable_z_min:
            reachable_coords = _interactive_jog_to_reachable_z_min(
                gantry,
                key_reader=key_reader,
                output=output,
                feed_rate=jog_feed_rate,
                initial_step_mm=jog_step_mm,
                limit_pull_off_mm=limit_pull_off_mm,
            )
            reachable_z_min_mm = float(reachable_coords["z"])
            output(
                "Recorded reference TCP reachable lower Z: "
                f"{reachable_z_min_mm:.3f} mm"
            )

        output("Re-homing to measure physical working-volume maxima...")
        _set_serial_timeout_if_available(gantry, homing_serial_timeout_s)
        gantry.home()
        _set_serial_timeout_if_available(gantry, jog_serial_timeout_s)
        measured_coords = gantry.get_coordinates()
        _assert_positive_measured_volume(
            measured_coords,
            tolerance_mm=tolerance_mm,
        )
        _print_config_patch(
            measured_coords,
            z_reference_coords=z_reference_coords,
            reference_surface_z_mm=reference_surface_z_mm,
            z_reference_mode=z_reference_mode,
            reachable_z_min_mm=reachable_z_min_mm,
            instrument_name=instrument_name,
            output=output,
        )

        return DeckOriginCalibrationResult(
            measured_working_volume=_coords_tuple(measured_coords),
            xy_origin_verification=_coords_tuple(xy_origin_coords),
            z_reference_verification=_coords_tuple(z_reference_coords),
            reference_surface_z_mm=reference_surface_z_mm,
            z_reference_mode=z_reference_mode,
            reachable_z_min_mm=reachable_z_min_mm,
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
            "Interactively assign X/Y at the front-left origin, assign Z at a "
            "known-height labware/artifact surface, then measure homed WPos as "
            "the real work volume."
        )
    )
    parser.add_argument(
        "--gantry",
        type=Path,
        required=True,
        help="Deck-origin gantry YAML from configs_new/gantry.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the physical calibration flow without connecting to hardware.",
    )
    parser.add_argument(
        "--reference-z-mm",
        type=float,
        default=None,
        help=(
            "Known labware/artifact Z reference height above true deck/bottom "
            "Z=0. If omitted, the script prompts after homing. Use 0 only when "
            "the second Z-reference point is true-bottom contact."
        ),
    )
    parser.add_argument(
        "--z-reference-mode",
        choices=("prompt", "bottom", "known-height"),
        default="prompt",
        help=(
            "How to ground absolute Z. 'prompt' asks after homing; 'bottom' "
            "sets Z=0 at true-bottom contact; 'known-height' uses "
            "--reference-z-mm or prompts for an A1/artifact height."
        ),
    )
    parser.add_argument(
        "--instrument",
        dest="instrument_name",
        default=None,
        help="Optional instrument/TCP label used in reach-limit output, e.g. asmi.",
    )
    reach_group = parser.add_mutually_exclusive_group()
    reach_group.add_argument(
        "--measure-reachable-z-min",
        dest="measure_reachable_z_min",
        action="store_true",
        help=(
            "After setting WPos, jog to the lowest safe reachable Z for the "
            "one reference TCP and print that reach note."
        ),
    )
    reach_group.add_argument(
        "--skip-reachable-z-min",
        dest="measure_reachable_z_min",
        action="store_false",
        help="Do not prompt for the one-instrument lowest reachable Z note.",
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
        default=800.0,
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
            reference_surface_z_mm=args.reference_z_mm,
            z_reference_mode=args.z_reference_mode,
            measure_reachable_z_min=args.measure_reachable_z_min,
            instrument_name=args.instrument_name,
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
