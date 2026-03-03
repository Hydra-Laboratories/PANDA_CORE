"""Hardware validation script for user-specified gantry positions.

Move to a user-specified coordinate and verify the machine reaches it
accurately, with optional repeat cycles for consistency checks.

Usage:
    python tests/hardware/test_custom_position.py \
        --config configs/gantry/genmitsu_3018_PRO_Desktop.yaml \
        --x 150 --y 100 --z 10 \
        --i-understand-risk

    # Dry run:
    python tests/hardware/test_custom_position.py --x 150 --y 100 --z 10 --dry-run

    # Repeat 5 times:
    python tests/hardware/test_custom_position.py --x 150 --y 100 --z 10 \
        --repeat 5 --i-understand-risk
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
from src.gantry.axis_verification import is_within_tolerance, working_volume_from_config
from src.gantry.coordinate_translator import to_machine_coordinates

DEFAULT_CONFIG = "configs/gantry/genmitsu_3018_PRO_Desktop.yaml"
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


def _run_dry(config: dict, target: tuple[float, float, float], tolerance: float) -> int:
    volume = working_volume_from_config(config)
    machine = to_machine_coordinates(*target)
    in_bounds = volume.contains(*target)

    print("=" * 72)
    print("CUSTOM POSITION — DRY RUN")
    print("=" * 72)
    print(f"Working volume: X=[{volume.x_min}, {volume.x_max}], "
          f"Y=[{volume.y_min}, {volume.y_max}], Z=[{volume.z_min}, {volume.z_max}]")
    print()
    print(f"  User target:    {_fmt_xyz(target)}")
    print(f"  Machine target: {_fmt_xyz(machine)}")
    print(f"  Within bounds:  {'YES' if in_bounds else 'NO — OUT OF BOUNDS'}")
    print(f"  Tolerance:      {tolerance}mm")

    if not in_bounds:
        print()
        if target[0] < volume.x_min or target[0] > volume.x_max:
            print(f"  X={target[0]} outside [{volume.x_min}, {volume.x_max}]")
        if target[1] < volume.y_min or target[1] > volume.y_max:
            print(f"  Y={target[1]} outside [{volume.y_min}, {volume.y_max}]")
        if target[2] < volume.z_min or target[2] > volume.z_max:
            print(f"  Z={target[2]} outside [{volume.z_min}, {volume.z_max}]")

    print("\nDry run complete — no commands sent.")
    return 0


def _run_live(
    config: dict,
    target: tuple[float, float, float],
    tolerance: float,
    repeat: int,
    force: bool,
) -> int:
    volume = working_volume_from_config(config)
    in_bounds = volume.contains(*target)

    if not in_bounds and not force:
        print(f"Target {_fmt_xyz(target)} is OUT OF BOUNDS.")
        print("Use --force to override this check.")
        return 5

    if not in_bounds:
        print(f"WARNING: Target {_fmt_xyz(target)} is OUT OF BOUNDS (--force enabled).")

    gantry = Gantry(config=config)
    passed = 0
    failed = 0

    try:
        print("Connecting...")
        gantry.connect()
        if not gantry.is_healthy():
            print("Gantry health check failed.")
            return 4

        current = _position_tuple(gantry.get_coordinates())
        print(f"Current position: {_fmt_xyz(current)}")
        print(f"Current status:   {gantry.get_status()}")

        for cycle in range(1, repeat + 1):
            if repeat > 1:
                print(f"\n--- Cycle {cycle}/{repeat} ---")

            machine = to_machine_coordinates(*target)
            print(f"  User target:    {_fmt_xyz(target)}")
            print(f"  Machine target: {_fmt_xyz(machine)}")

            gantry.move_to(*target)
            time.sleep(SETTLE_S)

            actual = _position_tuple(gantry.get_coordinates())
            status = gantry.get_status()
            print(f"  Status:   {status}")
            print(f"  Readback: {_fmt_xyz(actual)}")

            all_ok = all(
                is_within_tolerance(actual[i], target[i], tolerance) for i in range(3)
            )

            errors = []
            for i, axis in enumerate(("X", "Y", "Z")):
                err = abs(actual[i] - target[i])
                errors.append(f"{axis}={err:.4f}mm")

            error_str = ", ".join(errors)
            if all_ok:
                print(f"  [{PASS}] Error: {error_str}")
                passed += 1
            else:
                print(f"  [{FAIL}] Error: {error_str}")
                failed += 1

        origin = (volume.x_min, volume.y_min, volume.z_min)
        print(f"\nReturning to origin: {_fmt_xyz(origin)}")
        gantry.move_to(*origin)
        time.sleep(SETTLE_S)
        final = _position_tuple(gantry.get_coordinates())
        print(f"Final position: {_fmt_xyz(final)}")

        print("\n" + "=" * 72)
        print(f"Custom Position Results: {passed} passed, {failed} failed out of {repeat} cycles")
        print("=" * 72)
        return 0 if failed == 0 else 1
    finally:
        print("Disconnecting...")
        gantry.disconnect()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Move to a user-specified position and verify accuracy."
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(project_root / DEFAULT_CONFIG),
        help="Path to gantry YAML config.",
    )
    parser.add_argument("--x", type=float, required=True, help="Target X coordinate (user-space).")
    parser.add_argument("--y", type=float, required=True, help="Target Y coordinate (user-space).")
    parser.add_argument("--z", type=float, required=True, help="Target Z coordinate (user-space).")
    parser.add_argument(
        "--tolerance-mm",
        type=float,
        default=0.25,
        help="Acceptable position error (default 0.25mm).",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of times to move and verify (default 1).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow out-of-bounds targets (use with caution).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned move without sending commands.",
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
    target = (args.x, args.y, args.z)

    if args.dry_run:
        return _run_dry(config, target, args.tolerance_mm)

    if not args.i_understand_risk:
        print("Refusing to run without --i-understand-risk (use --dry-run for safe preview)")
        return 2

    print("=" * 72)
    print("HARDWARE CUSTOM POSITION VERIFICATION")
    print("This script issues real motion commands.")
    print("=" * 72)

    if not _confirm("Confirm machine area is clear and E-stop is reachable"):
        print("Aborted by user.")
        return 3

    return _run_live(config, target, args.tolerance_mm, args.repeat, args.force)


if __name__ == "__main__":
    raise SystemExit(main())
