"""Hardware validation script for gantry axis repeatability.

This script runs repeated absolute moves between a center point and two
inset corners, then verifies drift when returning to the center.

Usage:
    python tests/hardware/test_axis_repeatability.py \
        --config configs/gantry/genmitsu_3018_PROver_v2.yaml \
        --i-understand-risk
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


def _confirm(prompt: str) -> bool:
    return input(f"{prompt} [y/N]: ").strip().lower() == "y"


def _load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    if not isinstance(config, dict):
        raise ValueError("Gantry config YAML must load as a mapping.")
    return config


def _xyz_tuple(coords: dict[str, float]) -> tuple[float, float, float]:
    return (float(coords["x"]), float(coords["y"]), float(coords["z"]))


def _fmt_xyz(values: tuple[float, float, float]) -> str:
    return f"X={values[0]:.3f}, Y={values[1]:.3f}, Z={values[2]:.3f}"


def _move_and_read(
    gantry: Gantry,
    target: tuple[float, float, float],
    settle_s: float,
) -> tuple[float, float, float]:
    gantry.move_to(*target)
    if settle_s > 0:
        time.sleep(settle_s)
    return _xyz_tuple(gantry.get_coordinates())


def _within_xyz(
    actual: tuple[float, float, float],
    expected: tuple[float, float, float],
    tolerance_mm: float,
) -> bool:
    return all(
        is_within_tolerance(actual[idx], expected[idx], tolerance_mm) for idx in range(3)
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify axis repeatability on CNC hardware.")
    parser.add_argument(
        "--config",
        type=str,
        default=str(project_root / "configs" / "gantry" / "genmitsu_3018_PROver_v2.yaml"),
        help="Path to gantry YAML config.",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=5,
        help="Number of repeatability cycles.",
    )
    parser.add_argument(
        "--edge-margin-mm",
        type=float,
        default=15.0,
        help="Margin from min/max bounds used for corner targets.",
    )
    parser.add_argument(
        "--tolerance-mm",
        type=float,
        default=0.25,
        help="Allowed drift at center point after each cycle.",
    )
    parser.add_argument(
        "--settle-s",
        type=float,
        default=0.2,
        help="Delay after each move before readback.",
    )
    parser.add_argument(
        "--skip-homing",
        action="store_true",
        help="Skip homing and use current machine frame.",
    )
    parser.add_argument(
        "--i-understand-risk",
        action="store_true",
        help="Required acknowledgment before any motion commands.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.i_understand_risk:
        print("Refusing to run without --i-understand-risk")
        return 2

    print("=" * 72)
    print("HARDWARE AXIS REPEATABILITY VERIFICATION")
    print("This script issues real motion commands.")
    print("=" * 72)

    if not _confirm("Confirm machine area is clear and E-stop is reachable"):
        print("Aborted by user.")
        return 3

    config = _load_config(Path(args.config))
    volume = working_volume_from_config(config)
    center = (
        (volume.x_min + volume.x_max) / 2.0,
        (volume.y_min + volume.y_max) / 2.0,
        volume.z_min,
    )
    corners = build_safe_xy_corners(volume, args.edge_margin_mm, z_height=volume.z_min)
    path = [center, corners[0], center, corners[2], center]

    gantry = Gantry(config=config)
    failures: list[str] = []

    try:
        print(f"Connecting using config: {args.config}")
        gantry.connect()
        if not gantry.is_healthy():
            print("Gantry health check failed.")
            return 4

        if not args.skip_homing:
            if _confirm("Run homing now"):
                gantry.home()
            else:
                print("Homing is required for reliable repeatability checks.")
                return 5

        print(f"Moving to start center: {_fmt_xyz(center)}")
        initial = _move_and_read(gantry, center, args.settle_s)
        if not _within_xyz(initial, center, args.tolerance_mm):
            failures.append(
                "Initial center move out of tolerance "
                f"(expected {_fmt_xyz(center)}, got {_fmt_xyz(initial)})"
            )

        for cycle in range(1, args.cycles + 1):
            print(f"\nCycle {cycle}/{args.cycles}")
            for target in path[1:]:
                observed = _move_and_read(gantry, target, args.settle_s)
                print(f"  target {_fmt_xyz(target)} -> observed {_fmt_xyz(observed)}")

            center_readback = _xyz_tuple(gantry.get_coordinates())
            if not _within_xyz(center_readback, center, args.tolerance_mm):
                failures.append(
                    f"Cycle {cycle} center drift beyond tolerance "
                    f"(expected {_fmt_xyz(center)}, got {_fmt_xyz(center_readback)})"
                )

        print("\n" + "=" * 72)
        if failures:
            print("Repeatability check FAILED")
            for failure in failures:
                print(f"  - {failure}")
            print("=" * 72)
            return 1

        print("Repeatability check PASSED")
        print("=" * 72)
        return 0
    finally:
        print("Disconnecting...")
        gantry.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
