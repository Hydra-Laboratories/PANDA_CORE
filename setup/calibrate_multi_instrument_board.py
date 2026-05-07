"""Interactively calibrate a multi-instrument CubOS gantry config.

This guided path separates deck-frame XY origining from Z origining:

1. Home to the normalized back-right-top corner, then jog from that known homed
   pose with the left-most/reference instrument to the front-left XY artifact
   and assign only G54 WPos X=0, Y=0.
2. Re-home to measure machine-derived X/Y bounds after XY origining.
3. Attach all instruments, jog the lowest instrument to the deck/reference Z
   point, and assign G54 WPos Z=0.
4. Re-home to measure final Z max, then jog each instrument to a known artifact
   point and compute its CubOS offset/depth fields.

Usage example:

    python setup/calibrate_multi_instrument_board.py \
        --gantry configs/gantry/cub_xl_multi.yaml

The script prompts for the reference instrument, lowest instrument, and artifact
coordinates. It prints the calibrated YAML; optional flags can pre-fill values
or write the YAML for scripted runs/tests.
"""

from __future__ import annotations

import argparse
import copy
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

import yaml

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from gantry import Gantry, load_gantry_from_yaml  # noqa: E402
from gantry.origin import validate_deck_origin_minima  # noqa: E402
from setup.calibrate_deck_origin import (  # noqa: E402
    _assert_near_xyz,
    _calculate_grbl_max_travel,
    _interactive_jog_to_reference,
    _load_raw_config,
    _maybe_write_gantry_yaml,
    _print_yaml_block,
    _round_mm,
    _set_serial_timeout_if_available,
)
from setup.keyboard_input import flush_stdin, read_keypress_batch  # noqa: E402


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
    artifact_xyz: tuple[float, float, float]


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


def compute_instrument_calibration(
    *,
    gantry_coords: dict[str, float],
    artifact_xyz: tuple[float, float, float],
) -> dict[str, float]:
    """Compute CubOS instrument offset/depth from a known artifact point.

    Board.move() uses:
        gantry_x = target_x - offset_x
        gantry_y = target_y - offset_y
        gantry_z = target_z + depth

    Therefore, when an instrument is jogged so its TCP is at a known artifact
    point, the inverse is:
        offset_x = artifact_x - gantry_x
        offset_y = artifact_y - gantry_y
        depth = gantry_z - artifact_z
    """
    artifact_x, artifact_y, artifact_z = artifact_xyz
    return {
        "offset_x": _round_mm(artifact_x - float(gantry_coords["x"])),
        "offset_y": _round_mm(artifact_y - float(gantry_coords["y"])),
        "depth": _round_mm(float(gantry_coords["z"]) - artifact_z),
    }


def _build_grbl_settings(
    raw_config: dict[str, Any],
    max_travel: dict[str, float],
) -> dict[str, Any]:
    settings: dict[str, Any] = {}
    existing = raw_config.get("grbl_settings")
    if isinstance(existing, dict):
        settings.update(existing)
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


def _updated_yaml_text(
    raw_config: dict[str, Any],
    *,
    measured_coords: dict[str, float],
    instrument_calibrations: dict[str, dict[str, float]],
    max_travel: dict[str, float],
) -> str:
    updated = copy.deepcopy(raw_config)
    updated.setdefault("cnc", {})["total_z_range"] = _round_mm(measured_coords["z"])
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
    jog_feed_rate: float = 2500.0,
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
    reference_instrument = reference_instrument or _prompt_instrument_name(
        "Reference/left-most instrument",
        available_instruments,
        default=available_instruments[0],
        input_reader=input_reader,
        output=output,
    )
    lowest_instrument = lowest_instrument or _prompt_instrument_name(
        "Lowest instrument for WPos Z=0",
        available_instruments,
        default=reference_instrument,
        input_reader=input_reader,
        output=output,
    )
    artifact_xyz = artifact_xyz or _prompt_artifact_xyz(
        input_reader=input_reader,
        output=output,
    )
    instruments = tuple(instruments_to_calibrate or available_instruments)
    _validate_instrument_names(
        raw_config,
        (reference_instrument, lowest_instrument, *instruments),
    )
    if dry_run:
        output(f"Loaded deck-origin gantry config: {gantry_path}")
        output("Dry run only. Physical calibration flow:")
        output("  $H")
        output("  attach reference/left-most instrument at the homed pose")
        output("  jog reference/left-most instrument from home to FLB XY artifact")
        output("  G10 L20 P1 X0 Y0  # XY only, do not set Z here")
        output("  $H and read X/Y bounds")
        output("  attach all instruments and jog lowest instrument to Z reference")
        output("  G10 L20 P1 Z0")
        output("  $H and read final Z bound")
        output("  jog each instrument to the known artifact point and compute offsets/depths")
        return None

    output(f"Loaded deck-origin gantry config: {gantry_path}")
    output("Preflight:")
    output("  - GRBL $3 axis directions and $23 homing corner must be normalized.")
    output("  - $H must home to back-right-top (BRT).")
    output("  - Positive jogs must move from FLB toward +X right, +Y back, +Z up.")
    output("  - Initial origining sets only WPos X/Y; Z is set later by the lowest instrument.")
    output(f"  - Reference/left-most instrument: {reference_instrument}")
    output(f"  - Lowest Z instrument: {lowest_instrument}")
    output(
        "  - Calibration artifact point: "
        f"X={artifact_xyz[0]:.3f} Y={artifact_xyz[1]:.3f} Z={artifact_xyz[2]:.3f}"
    )
    output("")

    gantry_runtime_config = copy.deepcopy(raw_config)
    gantry_runtime_config.pop("grbl_settings", None)
    gantry = gantry_factory(config=gantry_runtime_config)
    try:
        output("Connecting to gantry...")
        gantry.connect()

        output("Homing to normalized BRT corner...")
        _set_serial_timeout_if_available(gantry, homing_serial_timeout_s)
        gantry.home()
        _set_serial_timeout_if_available(gantry, jog_serial_timeout_s)
        output("Forcing GRBL WPos status reporting ($10=0), G90, G54, and clearing G92...")
        gantry.enforce_work_position_reporting()
        gantry.activate_work_coordinate_system("G54")
        gantry.clear_g92_offsets()
        stdin_flusher()

        output(
            f"Attach {reference_instrument!r} at the homed BRT pose before jogging. "
            "No automatic center move will be made."
        )
        _interactive_jog_to_reference(
            gantry,
            target_description=(
                f"Step 1: attach {reference_instrument!r} at the homed pose and "
                "jog its TCP to the front-left XY artifact/origin. Do not use "
                "this step to define Z."
            ),
            confirmation_description=(
                "Press ENTER when current X/Y should become WPos X=0, Y=0. "
                "The script will not change WPos Z in this step."
            ),
            key_reader=key_reader,
            output=output,
            feed_rate=jog_feed_rate,
            initial_step_mm=jog_step_mm,
            limit_pull_off_mm=2.0,
        )
        output("Setting current physical pose to WPos X=0, Y=0 only...")
        gantry.set_work_coordinates(x=0.0, y=0.0)
        xy_origin_coords = dict(gantry.get_coordinates())
        _assert_near_xy_origin(xy_origin_coords, tolerance_mm=tolerance_mm)

        output("Re-homing after XY origining to measure machine-derived X/Y bounds...")
        _set_serial_timeout_if_available(gantry, homing_serial_timeout_s)
        gantry.home()
        _set_serial_timeout_if_available(gantry, jog_serial_timeout_s)
        xy_bounds_coords = dict(gantry.get_coordinates())

        output(
            "Attach/verify all instruments at the homed BRT pose before setting Z. "
            "No automatic center move will be made."
        )
        _interactive_jog_to_reference(
            gantry,
            target_description=(
                f"Step 2: from the homed pose, jog the lowest instrument "
                f"({lowest_instrument!r}) to the deck/reference Z=0 point."
            ),
            confirmation_description=(
                "Press ENTER when this lowest instrument defines WPos Z=0. "
                "X/Y will not be changed in this step."
            ),
            key_reader=key_reader,
            output=output,
            feed_rate=jog_feed_rate,
            initial_step_mm=jog_step_mm,
            limit_pull_off_mm=2.0,
        )
        output("Setting current physical pose to WPos Z=0 only...")
        gantry.set_work_coordinates(z=0.0)
        z_origin_coords = dict(gantry.get_coordinates())
        _assert_near_xyz(
            z_origin_coords,
            expected={
                "x": z_origin_coords["x"],
                "y": z_origin_coords["y"],
                "z": 0.0,
            },
            tolerance_mm=tolerance_mm,
            label="Lowest-instrument Z origin",
        )

        output("Re-homing after Z origining to measure final working-volume maxima...")
        _set_serial_timeout_if_available(gantry, homing_serial_timeout_s)
        gantry.home()
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
            output("Programming GRBL soft limits from measured travel spans...")
            gantry.configure_soft_limits_from_spans(
                max_travel_x=max_travel["max_travel_x"],
                max_travel_y=max_travel["max_travel_y"],
                max_travel_z=max_travel["max_travel_z"],
                tolerance_mm=tolerance_mm,
            )

        output(
            "Instrument artifact calibration starts from the final homed BRT pose. "
            "No automatic center move will be made."
        )
        instrument_calibrations: dict[str, dict[str, float]] = {}
        for instrument in instruments:
            _interactive_jog_to_reference(
                gantry,
                target_description=(
                    f"Step 3: calibrate {instrument!r}. Place the homing block/artifact "
                    "and jog this instrument TCP to the known artifact point."
                ),
                confirmation_description=(
                    "Press ENTER when the instrument is positioned at the artifact "
                    f"point X={artifact_xyz[0]:.3f} Y={artifact_xyz[1]:.3f} "
                    f"Z={artifact_xyz[2]:.3f}."
                ),
                key_reader=key_reader,
                output=output,
                feed_rate=jog_feed_rate,
                initial_step_mm=jog_step_mm,
                limit_pull_off_mm=2.0,
            )
            coords = dict(gantry.get_coordinates())
            instrument_calibrations[instrument] = compute_instrument_calibration(
                gantry_coords=coords,
                artifact_xyz=artifact_xyz,
            )
            output(
                f"Recorded {instrument}: "
                f"offset_x={instrument_calibrations[instrument]['offset_x']:.3f}, "
                f"offset_y={instrument_calibrations[instrument]['offset_y']:.3f}, "
                f"depth={instrument_calibrations[instrument]['depth']:.3f}"
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
            artifact_xyz=artifact_xyz,
        )
    finally:
        _set_serial_timeout_if_available(gantry, 0.05)
        output("Disconnecting...")
        gantry.disconnect()


def _prompt_instrument_name(
    label: str,
    available: Sequence[str],
    *,
    default: str,
    input_reader: Callable[[str], str],
    output: Callable[[str], None],
) -> str:
    output(f"Available instruments: {', '.join(available)}")
    while True:
        raw = input_reader(f"{label} [{default}]: ").strip()
        value = raw or default
        if value in available:
            return value
        output(f"Unknown instrument {value!r}. Choose one of: {', '.join(available)}")


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Interactively calibrate a multi-instrument gantry config by "
            "setting XY origin first, Z origin from the lowest instrument, "
            "then per-instrument offsets/depths from a known artifact."
        )
    )
    parser.add_argument("--gantry", type=Path, required=True)
    parser.add_argument("--reference-instrument", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--lowest-instrument", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--artifact-x", type=float, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--artifact-y", type=float, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--artifact-z", type=float, default=None, help=argparse.SUPPRESS)
    parser.add_argument(
        "--instrument",
        dest="instruments",
        action="append",
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-soft-limit-config", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--write-gantry-yaml", action="store_true")
    parser.add_argument("--output-gantry", type=Path, default=None)
    parser.add_argument("--tolerance-mm", type=float, default=0.25, help=argparse.SUPPRESS)
    parser.add_argument("--jog-step-mm", type=float, default=1.0, help=argparse.SUPPRESS)
    parser.add_argument("--jog-feed-rate", type=float, default=2500.0, help=argparse.SUPPRESS)
    parser.add_argument("--homing-serial-timeout-s", type=float, default=10.0, help=argparse.SUPPRESS)
    parser.add_argument("--jog-serial-timeout-s", type=float, default=1.0, help=argparse.SUPPRESS)
    args = parser.parse_args()

    try:
        run_multi_instrument_calibration(
            args.gantry,
            reference_instrument=args.reference_instrument,
            lowest_instrument=args.lowest_instrument,
            artifact_xyz=_artifact_xyz_from_args(args),
            instruments_to_calibrate=tuple(args.instruments) if args.instruments else None,
            dry_run=args.dry_run,
            tolerance_mm=args.tolerance_mm,
            jog_step_mm=args.jog_step_mm,
            jog_feed_rate=args.jog_feed_rate,
            skip_soft_limit_config=args.skip_soft_limit_config,
            write_gantry_yaml=args.write_gantry_yaml,
            output_gantry_path=args.output_gantry,
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
