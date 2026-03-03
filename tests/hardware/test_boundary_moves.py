"""Hardware validation script for gantry boundary moves.

Moves to every edge and corner of the working volume to validate
the full extent of the positive-space coordinate system.

Usage:
    python tests/hardware/test_boundary_moves.py \
        --config configs/gantry/genmitsu_3018_PRO_Desktop.yaml \
        --i-understand-risk

    # Dry run (no hardware):
    python tests/hardware/test_boundary_moves.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import yaml

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.gantry import Gantry
from src.gantry.axis_verification import (
    build_safe_xy_corners,
    is_within_tolerance,
    working_volume_from_config,
)
from src.gantry.coordinate_translator import to_machine_coordinates

DEFAULT_CONFIG = "configs/gantry/genmitsu_3018_PRO_Desktop.yaml"
EDGE_MARGIN_MM = 5.0
TOLERANCE_MM = 0.25
SETTLE_S = 0.2

PASS = "PASS"
FAIL = "FAIL"


def _confirm(prompt: str) -> bool:
    return input(f"{prompt} [y/N]: ").strip().lower() == "y"


def _load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    if not isinstance(config, dict):
        raise ValueError("Gantry config YAML must load as a mapping.")
    return config


def _fmt_xyz(values: tuple[float, float, float]) -> str:
    return f"X={values[0]:.3f}, Y={values[1]:.3f}, Z={values[2]:.3f}"


def _position_tuple(coords: dict[str, float]) -> tuple[float, float, float]:
    return (float(coords["x"]), float(coords["y"]), float(coords["z"]))


class ResultTracker:
    def __init__(self) -> None:
        self._results: list[tuple[str, bool, str]] = []

    def pass_(self, name: str, detail: str = "") -> None:
        self._results.append((name, True, detail))
        print(f"[{PASS}] {name}" + (f" - {detail}" if detail else ""))

    def fail(self, name: str, detail: str = "") -> None:
        self._results.append((name, False, detail))
        print(f"[{FAIL}] {name}" + (f" - {detail}" if detail else ""))

    def summary(self) -> bool:
        passed = sum(1 for _, state, _ in self._results if state is True)
        failed = sum(1 for _, state, _ in self._results if state is False)
        print("\n" + "=" * 72)
        print(f"Boundary Move Results: {passed} passed, {failed} failed")
        if failed:
            print("Failures:")
            for name, state, detail in self._results:
                if state is False:
                    print(f"  - {name}" + (f" ({detail})" if detail else ""))
        print("=" * 72)
        return failed == 0


def _print_translation(label: str, user_xyz: tuple[float, float, float]) -> None:
    machine_xyz = to_machine_coordinates(*user_xyz)
    print(f"  {label}")
    print(f"    User target:    {_fmt_xyz(user_xyz)}")
    print(f"    Machine target: {_fmt_xyz(machine_xyz)}")


def _move_verify_return(
    gantry: Gantry,
    tracker: ResultTracker,
    target: tuple[float, float, float],
    center: tuple[float, float, float],
    label: str,
) -> None:
    _print_translation(f"Moving: {label}", target)
    gantry.move_to(*target)
    time.sleep(SETTLE_S)

    actual = _position_tuple(gantry.get_coordinates())
    status = gantry.get_status()
    print(f"    Status: {status}")
    print(f"    Readback: {_fmt_xyz(actual)}")

    all_ok = all(
        is_within_tolerance(actual[i], target[i], TOLERANCE_MM) for i in range(3)
    )
    detail = f"expected({_fmt_xyz(target)}), actual({_fmt_xyz(actual)})"
    if all_ok:
        tracker.pass_(label, detail)
    else:
        tracker.fail(label, detail)

    gantry.move_to(*center)
    time.sleep(SETTLE_S)
    center_actual = _position_tuple(gantry.get_coordinates())
    center_ok = all(
        is_within_tolerance(center_actual[i], center[i], TOLERANCE_MM) for i in range(3)
    )
    center_detail = f"expected({_fmt_xyz(center)}), actual({_fmt_xyz(center_actual)})"
    if center_ok:
        tracker.pass_(f"Return to center after {label}", center_detail)
    else:
        tracker.fail(f"Return to center after {label}", center_detail)


def _build_test_points(volume, margin: float) -> list[tuple[str, tuple[float, float, float]]]:
    """Build all boundary test points: corners at z_min, corners at z_max, axis midpoints."""
    points: list[tuple[str, tuple[float, float, float]]] = []

    corners_z_min = build_safe_xy_corners(volume, margin, z_height=volume.z_min)
    corner_labels = ["near-left", "far-left", "far-right", "near-right"]
    for label, corner in zip(corner_labels, corners_z_min):
        points.append((f"Corner {label} at Z_min", corner))

    corners_z_max = build_safe_xy_corners(volume, margin, z_height=volume.z_max - margin)
    for label, corner in zip(corner_labels, corners_z_max):
        points.append((f"Corner {label} at Z_max", corner))

    x_mid = (volume.x_min + volume.x_max) / 2.0
    y_mid = (volume.y_min + volume.y_max) / 2.0
    z_low = volume.z_min
    z_high = volume.z_max - margin

    edge_midpoints = [
        ("X_min edge midpoint", (volume.x_min + margin, y_mid, z_low)),
        ("X_max edge midpoint", (volume.x_max - margin, y_mid, z_low)),
        ("Y_min edge midpoint", (x_mid, volume.y_min + margin, z_low)),
        ("Y_max edge midpoint", (x_mid, volume.y_max - margin, z_low)),
        ("Z_min edge midpoint", (x_mid, y_mid, z_low)),
        ("Z_max edge midpoint", (x_mid, y_mid, z_high)),
    ]
    points.extend(edge_midpoints)

    return points


def _run_dry(config: dict) -> int:
    volume = working_volume_from_config(config)
    center = (
        (volume.x_min + volume.x_max) / 2.0,
        (volume.y_min + volume.y_max) / 2.0,
        (volume.z_min + volume.z_max) / 2.0,
    )

    print("=" * 72)
    print("BOUNDARY MOVES — DRY RUN")
    print(f"Working volume: X=[{volume.x_min}, {volume.x_max}], "
          f"Y=[{volume.y_min}, {volume.y_max}], Z=[{volume.z_min}, {volume.z_max}]")
    print(f"Edge margin: {EDGE_MARGIN_MM}mm")
    print("=" * 72)

    _print_translation("Center (baseline)", center)
    print()

    test_points = _build_test_points(volume, EDGE_MARGIN_MM)
    for idx, (label, point) in enumerate(test_points, start=1):
        print(f"  [{idx}/{len(test_points)}] {label}")
        machine = to_machine_coordinates(*point)
        print(f"    User target:    {_fmt_xyz(point)}")
        print(f"    Machine target: {_fmt_xyz(machine)}")

    print(f"\nTotal moves planned: {len(test_points)} targets + center returns")
    print("Dry run complete — no commands sent.")
    return 0


def _run_live(config: dict) -> int:
    volume = working_volume_from_config(config)
    center = (
        (volume.x_min + volume.x_max) / 2.0,
        (volume.y_min + volume.y_max) / 2.0,
        (volume.z_min + volume.z_max) / 2.0,
    )
    tracker = ResultTracker()
    gantry = Gantry(config=config)

    try:
        print("Connecting...")
        gantry.connect()
        if not gantry.is_healthy():
            print("Gantry health check failed.")
            return 4

        current = _position_tuple(gantry.get_coordinates())
        print(f"Current position: {_fmt_xyz(current)}")
        print(f"Current status:   {gantry.get_status()}")

        print(f"\nMoving to center: {_fmt_xyz(center)}")
        gantry.move_to(*center)
        time.sleep(SETTLE_S)

        center_actual = _position_tuple(gantry.get_coordinates())
        center_ok = all(
            is_within_tolerance(center_actual[i], center[i], TOLERANCE_MM) for i in range(3)
        )
        detail = f"expected({_fmt_xyz(center)}), actual({_fmt_xyz(center_actual)})"
        if center_ok:
            tracker.pass_("Center baseline", detail)
        else:
            tracker.fail("Center baseline", detail)

        test_points = _build_test_points(volume, EDGE_MARGIN_MM)
        for label, point in test_points:
            _move_verify_return(gantry, tracker, point, center, label)

        origin = (volume.x_min, volume.y_min, volume.z_min)
        print(f"\nReturning to origin: {_fmt_xyz(origin)}")
        gantry.move_to(*origin)
        time.sleep(SETTLE_S)
        final = _position_tuple(gantry.get_coordinates())
        print(f"Final position: {_fmt_xyz(final)}")

        return 0 if tracker.summary() else 1
    finally:
        print("Disconnecting...")
        gantry.disconnect()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify gantry boundary moves across the full working volume."
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(project_root / DEFAULT_CONFIG),
        help="Path to gantry YAML config.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned moves without sending commands.",
    )
    parser.add_argument(
        "--i-understand-risk",
        action="store_true",
        help="Required acknowledgment before any motion commands.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config = _load_config(Path(args.config))

    if args.dry_run:
        return _run_dry(config)

    if not args.i_understand_risk:
        print("Refusing to run without --i-understand-risk (use --dry-run for safe preview)")
        return 2

    print("=" * 72)
    print("HARDWARE BOUNDARY MOVE VERIFICATION")
    print("This script issues real motion commands.")
    print("=" * 72)

    if not _confirm("Confirm machine area is clear and E-stop is reachable"):
        print("Aborted by user.")
        return 3

    return _run_live(config)


if __name__ == "__main__":
    raise SystemExit(main())
