"""Hardware validation script for gantry axis positioning.

This script verifies user-space axis positioning after the positive-space
gantry refactor. It checks:
1) Absolute move readback at known XY checkpoints
2) Per-axis direction and orthogonal-axis stability
3) Return-to-start accuracy

Usage:
    python tests/hardware/test_axis_positioning.py \
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
    choose_axis_target,
    is_within_tolerance,
    working_volume_from_config,
)

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


def _confirm(prompt: str) -> bool:
    return input(f"{prompt} [y/N]: ").strip().lower() == "y"


def _load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    if not isinstance(config, dict):
        raise ValueError("Gantry config YAML must load as a mapping.")
    return config


def _position_tuple(coords: dict[str, float]) -> tuple[float, float, float]:
    return (float(coords["x"]), float(coords["y"]), float(coords["z"]))


def _fmt_xyz(values: tuple[float, float, float]) -> str:
    return f"X={values[0]:.3f}, Y={values[1]:.3f}, Z={values[2]:.3f}"


class ResultTracker:
    def __init__(self) -> None:
        self._results: list[tuple[str, bool | None, str]] = []

    def pass_(self, name: str, detail: str = "") -> None:
        self._results.append((name, True, detail))
        print(f"[{PASS}] {name}" + (f" - {detail}" if detail else ""))

    def fail(self, name: str, detail: str = "") -> None:
        self._results.append((name, False, detail))
        print(f"[{FAIL}] {name}" + (f" - {detail}" if detail else ""))

    def skip(self, name: str, detail: str = "") -> None:
        self._results.append((name, None, detail))
        print(f"[{SKIP}] {name}" + (f" - {detail}" if detail else ""))

    def summary(self) -> bool:
        passed = sum(1 for _, state, _ in self._results if state is True)
        failed = sum(1 for _, state, _ in self._results if state is False)
        skipped = sum(1 for _, state, _ in self._results if state is None)
        print("\n" + "=" * 72)
        print(f"Axis Positioning Results: {passed} passed, {failed} failed, {skipped} skipped")
        if failed:
            print("Failures:")
            for name, state, detail in self._results:
                if state is False:
                    print(f"  - {name}" + (f" ({detail})" if detail else ""))
        print("=" * 72)
        return failed == 0


def _verify_target(
    tracker: ResultTracker,
    expected: tuple[float, float, float],
    actual: tuple[float, float, float],
    tolerance_mm: float,
    label: str,
) -> bool:
    x_ok = is_within_tolerance(actual[0], expected[0], tolerance_mm)
    y_ok = is_within_tolerance(actual[1], expected[1], tolerance_mm)
    z_ok = is_within_tolerance(actual[2], expected[2], tolerance_mm)
    all_ok = x_ok and y_ok and z_ok

    detail = f"expected({_fmt_xyz(expected)}), actual({_fmt_xyz(actual)})"
    if all_ok:
        tracker.pass_(label, detail)
    else:
        tracker.fail(label, detail)
    return all_ok


def _move_and_read(
    gantry: Gantry,
    target: tuple[float, float, float],
    settle_s: float,
) -> tuple[float, float, float]:
    gantry.move_to(*target)
    if settle_s > 0:
        time.sleep(settle_s)
    return _position_tuple(gantry.get_coordinates())


def _run_axis_direction_test(
    gantry: Gantry,
    tracker: ResultTracker,
    axis: str,
    base: tuple[float, float, float],
    step_mm: float,
    edge_margin_mm: float,
    tolerance_mm: float,
    settle_s: float,
    config: dict,
) -> None:
    volume = working_volume_from_config(config)
    before = _position_tuple(gantry.get_coordinates())
    target = choose_axis_target(before, axis, step_mm, volume, edge_margin_mm)

    after = _move_and_read(gantry, target, settle_s)
    if _verify_target(
        tracker,
        expected=target,
        actual=after,
        tolerance_mm=tolerance_mm,
        label=f"{axis.upper()} move reaches commanded target",
    ):
        moved_index = {"x": 0, "y": 1, "z": 2}[axis]
        for idx, name in enumerate(("x", "y", "z")):
            if idx == moved_index:
                continue
            stable = is_within_tolerance(after[idx], before[idx], tolerance_mm)
            if stable:
                tracker.pass_(
                    f"{axis.upper()} move keeps {name.upper()} stable",
                    f"before={before[idx]:.3f}, after={after[idx]:.3f}",
                )
            else:
                tracker.fail(
                    f"{axis.upper()} move keeps {name.upper()} stable",
                    f"before={before[idx]:.3f}, after={after[idx]:.3f}",
                )

    restored = _move_and_read(gantry, base, settle_s)
    _verify_target(
        tracker,
        expected=base,
        actual=restored,
        tolerance_mm=tolerance_mm,
        label=f"{axis.upper()} move returns to base position",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify axis positioning on CNC hardware.")
    parser.add_argument(
        "--config",
        type=str,
        default=str(project_root / "configs" / "gantry" / "genmitsu_3018_PROver_v2.yaml"),
        help="Path to gantry YAML config.",
    )
    parser.add_argument(
        "--step-mm",
        type=float,
        default=5.0,
        help="Step size for X/Y axis direction checks.",
    )
    parser.add_argument(
        "--z-step-mm",
        type=float,
        default=1.0,
        help="Step size for Z axis direction checks.",
    )
    parser.add_argument(
        "--edge-margin-mm",
        type=float,
        default=10.0,
        help="Margin from min/max bounds used for checkpoint generation.",
    )
    parser.add_argument(
        "--tolerance-mm",
        type=float,
        default=0.25,
        help="Acceptable absolute position error for each axis.",
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
    print("HARDWARE AXIS POSITIONING VERIFICATION")
    print("This script issues real motion commands.")
    print("=" * 72)

    if not _confirm("Confirm machine area is clear and E-stop is reachable"):
        print("Aborted by user.")
        return 3

    config_path = Path(args.config)
    config = _load_config(config_path)
    volume = working_volume_from_config(config)
    tracker = ResultTracker()
    gantry = Gantry(config=config)

    try:
        print(f"Connecting using config: {config_path}")
        gantry.connect()

        if not gantry.is_healthy():
            print("Gantry health check failed.")
            return 4

        if args.skip_homing:
            tracker.skip("Homing", "skipped via --skip-homing")
        else:
            if _confirm("Run homing now"):
                gantry.home()
                tracker.pass_("Homing completed")
            else:
                tracker.fail("Homing completed", "user declined homing")
                return 5

        base = (
            (volume.x_min + volume.x_max) / 2.0,
            (volume.y_min + volume.y_max) / 2.0,
            volume.z_min,
        )

        if not _confirm(f"Move to base point ({_fmt_xyz(base)})"):
            tracker.fail("Move to base point", "user declined base move")
            return 6

        actual_base = _move_and_read(gantry, base, args.settle_s)
        _verify_target(
            tracker,
            expected=base,
            actual=actual_base,
            tolerance_mm=args.tolerance_mm,
            label="Base point readback",
        )

        corners = build_safe_xy_corners(volume, args.edge_margin_mm, z_height=volume.z_min)
        for idx, point in enumerate(corners, start=1):
            actual = _move_and_read(gantry, point, args.settle_s)
            _verify_target(
                tracker,
                expected=point,
                actual=actual,
                tolerance_mm=args.tolerance_mm,
                label=f"Absolute checkpoint {idx}/4",
            )

        restored = _move_and_read(gantry, base, args.settle_s)
        _verify_target(
            tracker,
            expected=base,
            actual=restored,
            tolerance_mm=args.tolerance_mm,
            label="Return to base after checkpoint sweep",
        )

        _run_axis_direction_test(
            gantry=gantry,
            tracker=tracker,
            axis="x",
            base=base,
            step_mm=args.step_mm,
            edge_margin_mm=args.edge_margin_mm,
            tolerance_mm=args.tolerance_mm,
            settle_s=args.settle_s,
            config=config,
        )
        _run_axis_direction_test(
            gantry=gantry,
            tracker=tracker,
            axis="y",
            base=base,
            step_mm=args.step_mm,
            edge_margin_mm=args.edge_margin_mm,
            tolerance_mm=args.tolerance_mm,
            settle_s=args.settle_s,
            config=config,
        )
        _run_axis_direction_test(
            gantry=gantry,
            tracker=tracker,
            axis="z",
            base=base,
            step_mm=args.z_step_mm,
            edge_margin_mm=0.0,
            tolerance_mm=args.tolerance_mm,
            settle_s=args.settle_s,
            config=config,
        )

        return 0 if tracker.summary() else 1
    finally:
        print("Disconnecting...")
        gantry.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
