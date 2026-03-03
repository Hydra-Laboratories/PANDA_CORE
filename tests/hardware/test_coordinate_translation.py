"""Hardware validation script for coordinate translation verification.

Verifies that the coordinate translation layer correctly maps between
user-space (positive) and machine-space (negative) at the hardware level.
This is the core validation for the gantry-axis-refactor PR.

Usage:
    python tests/hardware/test_coordinate_translation.py \
        --config configs/gantry/genmitsu_3018_PRO_Desktop.yaml \
        --i-understand-risk

    # Dry run:
    python tests/hardware/test_coordinate_translation.py --dry-run
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
SETTLE_S = 0.3

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


def _build_test_points(volume) -> list[tuple[str, tuple[float, float, float]]]:
    """Build test points: center, corners, and axis midpoints."""
    x_mid = (volume.x_min + volume.x_max) / 2.0
    y_mid = (volume.y_min + volume.y_max) / 2.0
    z_mid = (volume.z_min + volume.z_max) / 2.0

    points: list[tuple[str, tuple[float, float, float]]] = [
        ("Center", (x_mid, y_mid, z_mid)),
    ]

    corners = build_safe_xy_corners(volume, EDGE_MARGIN_MM, z_height=volume.z_min)
    corner_labels = ["near-left", "far-left", "far-right", "near-right"]
    for label, corner in zip(corner_labels, corners):
        points.append((f"Corner {label}", corner))

    axis_midpoints = [
        ("X-min midpoint", (volume.x_min + EDGE_MARGIN_MM, y_mid, z_mid)),
        ("X-max midpoint", (volume.x_max - EDGE_MARGIN_MM, y_mid, z_mid)),
        ("Y-min midpoint", (x_mid, volume.y_min + EDGE_MARGIN_MM, z_mid)),
        ("Y-max midpoint", (x_mid, volume.y_max - EDGE_MARGIN_MM, z_mid)),
    ]
    points.extend(axis_midpoints)

    return points


class ResultTracker:
    def __init__(self) -> None:
        self._results: list[tuple[str, bool, str]] = []

    def pass_(self, name: str, detail: str = "") -> None:
        self._results.append((name, True, detail))
        print(f"    [{PASS}] {name}" + (f" - {detail}" if detail else ""))

    def fail(self, name: str, detail: str = "") -> None:
        self._results.append((name, False, detail))
        print(f"    [{FAIL}] {name}" + (f" - {detail}" if detail else ""))

    def summary(self) -> bool:
        passed = sum(1 for _, state, _ in self._results if state is True)
        failed = sum(1 for _, state, _ in self._results if state is False)
        print("\n" + "=" * 72)
        print(f"Coordinate Translation Results: {passed} passed, {failed} failed")
        if failed:
            print("Failures:")
            for name, state, detail in self._results:
                if state is False:
                    print(f"  - {name}" + (f" ({detail})" if detail else ""))
        print("=" * 72)
        return failed == 0


def _run_dry(config: dict) -> int:
    volume = working_volume_from_config(config)
    test_points = _build_test_points(volume)

    print("=" * 72)
    print("COORDINATE TRANSLATION — DRY RUN")
    print("=" * 72)
    print(f"Working volume: X=[{volume.x_min}, {volume.x_max}], "
          f"Y=[{volume.y_min}, {volume.y_max}], Z=[{volume.z_min}, {volume.z_max}]")
    print(f"Translation formula: machine_value = -user_value")
    print()

    for idx, (label, user_xyz) in enumerate(test_points, start=1):
        machine_xyz = to_machine_coordinates(*user_xyz)
        print(f"  [{idx}/{len(test_points)}] {label}")
        print(f"    User target:    {_fmt_xyz(user_xyz)}")
        print(f"    Machine target: {_fmt_xyz(machine_xyz)}")
        print(f"    Verify: raw MPos should equal machine target (negated user)")
        print(f"    Verify: get_coordinates() should match user target (positive)")
        print(f"    Verify: MPos is the negation of get_coordinates()")
        print()

    print(f"Total test points: {len(test_points)}")
    print("Dry run complete — no commands sent.")
    return 0


def _run_live(config: dict) -> int:
    volume = working_volume_from_config(config)
    test_points = _build_test_points(volume)
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

        for idx, (label, user_target) in enumerate(test_points, start=1):
            expected_machine = to_machine_coordinates(*user_target)

            print(f"\n--- [{idx}/{len(test_points)}] {label} ---")
            print(f"  User target:     {_fmt_xyz(user_target)}")
            print(f"  Expected machine: {_fmt_xyz(expected_machine)}")

            gantry.move_to(*user_target)
            time.sleep(SETTLE_S)

            raw_status = gantry._mill.current_status()
            translated_status = gantry.get_status()
            raw_coords = gantry._mill.current_coordinates()
            raw_mpos = (float(raw_coords.x), float(raw_coords.y), float(raw_coords.z))
            user_coords = _position_tuple(gantry.get_coordinates())

            print(f"  Raw status:        {raw_status}")
            print(f"  Translated status: {translated_status}")
            print(f"  Raw MPos:          {_fmt_xyz(raw_mpos)}")
            print(f"  get_coordinates(): {_fmt_xyz(user_coords)}")

            # Check raw MPos matches expected machine-space (negated user target)
            mpos_ok = all(
                is_within_tolerance(raw_mpos[i], expected_machine[i], TOLERANCE_MM)
                for i in range(3)
            )
            mpos_detail = f"expected({_fmt_xyz(expected_machine)}), actual({_fmt_xyz(raw_mpos)})"
            if mpos_ok:
                tracker.pass_("Raw MPos matches expected machine-space", mpos_detail)
            else:
                tracker.fail("Raw MPos matches expected machine-space", mpos_detail)

            # Check get_coordinates() returns positive values matching user target
            coords_ok = all(
                is_within_tolerance(user_coords[i], user_target[i], TOLERANCE_MM)
                for i in range(3)
            )
            detail = f"expected({_fmt_xyz(user_target)}), actual({_fmt_xyz(user_coords)})"
            if coords_ok:
                tracker.pass_("get_coordinates() matches user target", detail)
            else:
                tracker.fail("get_coordinates() matches user target", detail)

            # Check MPos is the negation of user-space coords
            negation_ok = all(
                is_within_tolerance(raw_mpos[i], -user_coords[i], TOLERANCE_MM)
                for i in range(3)
            )
            if negation_ok:
                tracker.pass_("MPos is negation of user-space coords")
            else:
                tracker.fail(
                    "MPos is negation of user-space coords",
                    f"MPos={_fmt_xyz(raw_mpos)}, -user={_fmt_xyz(tuple(-v for v in user_coords))}",
                )

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
        description="Verify coordinate translation between user-space and machine-space."
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
        help="Print planned tests without sending commands.",
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
    print("HARDWARE COORDINATE TRANSLATION VERIFICATION")
    print("This script issues real motion commands.")
    print("=" * 72)

    if not _confirm("Confirm machine area is clear and E-stop is reachable"):
        print("Aborted by user.")
        return 3

    return _run_live(config)


if __name__ == "__main__":
    raise SystemExit(main())
