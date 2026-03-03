"""Software validation script for out-of-bounds coordinate detection.

Verifies that WorkingVolume.contains() correctly rejects coordinates
outside the configured working volume. No hardware connection required.

Usage:
    python tests/hardware/test_out_of_bounds.py \
        --config configs/gantry/genmitsu_3018_PRO_Desktop.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.gantry.axis_verification import working_volume_from_config
from src.gantry.coordinate_translator import to_machine_coordinates

DEFAULT_CONFIG = "configs/gantry/genmitsu_3018_PRO_Desktop.yaml"
OOB_OFFSET_MM = 5.0

PASS = "PASS"
FAIL = "FAIL"


def _load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    if not isinstance(config, dict):
        raise ValueError("Gantry config YAML must load as a mapping.")
    return config


def _fmt_xyz(values: tuple[float, float, float]) -> str:
    return f"X={values[0]:.3f}, Y={values[1]:.3f}, Z={values[2]:.3f}"


def _build_oob_cases(volume, offset: float) -> list[tuple[str, tuple[float, float, float], str]]:
    """Build out-of-bounds test cases with labels and violated bound descriptions."""
    x_mid = (volume.x_min + volume.x_max) / 2.0
    y_mid = (volume.y_min + volume.y_max) / 2.0
    z_mid = (volume.z_min + volume.z_max) / 2.0

    return [
        (
            "X beyond x_max",
            (volume.x_max + offset, y_mid, z_mid),
            f"x={volume.x_max + offset} > x_max={volume.x_max}",
        ),
        (
            "Y beyond y_max",
            (x_mid, volume.y_max + offset, z_mid),
            f"y={volume.y_max + offset} > y_max={volume.y_max}",
        ),
        (
            "Z beyond z_max",
            (x_mid, y_mid, volume.z_max + offset),
            f"z={volume.z_max + offset} > z_max={volume.z_max}",
        ),
        (
            "X below x_min",
            (volume.x_min - offset, y_mid, z_mid),
            f"x={volume.x_min - offset} < x_min={volume.x_min}",
        ),
        (
            "Y below y_min",
            (x_mid, volume.y_min - offset, z_mid),
            f"y={volume.y_min - offset} < y_min={volume.y_min}",
        ),
        (
            "Z below z_min",
            (x_mid, y_mid, volume.z_min - offset),
            f"z={volume.z_min - offset} < z_min={volume.z_min}",
        ),
    ]


def _build_in_bounds_cases(volume) -> list[tuple[str, tuple[float, float, float]]]:
    """Build in-bounds sanity check cases."""
    x_mid = (volume.x_min + volume.x_max) / 2.0
    y_mid = (volume.y_min + volume.y_max) / 2.0
    z_mid = (volume.z_min + volume.z_max) / 2.0

    return [
        ("Center", (x_mid, y_mid, z_mid)),
        ("Origin", (volume.x_min, volume.y_min, volume.z_min)),
        ("Max corner", (volume.x_max, volume.y_max, volume.z_max)),
        ("X-min edge", (volume.x_min, y_mid, z_mid)),
        ("X-max edge", (volume.x_max, y_mid, z_mid)),
    ]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate software bounds checking for out-of-bounds coordinates."
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(project_root / DEFAULT_CONFIG),
        help="Path to gantry YAML config.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config = _load_config(Path(args.config))
    volume = working_volume_from_config(config)

    print("=" * 72)
    print("OUT-OF-BOUNDS SOFTWARE VALIDATION")
    print("No hardware connection required — software-only test.")
    print("=" * 72)
    print(f"Working volume: X=[{volume.x_min}, {volume.x_max}], "
          f"Y=[{volume.y_min}, {volume.y_max}], Z=[{volume.z_min}, {volume.z_max}]")
    print()

    passed = 0
    failed = 0

    print("--- Out-of-bounds coordinates (should be rejected) ---")
    oob_cases = _build_oob_cases(volume, OOB_OFFSET_MM)
    for label, coord, violation in oob_cases:
        machine = to_machine_coordinates(*coord)
        is_contained = volume.contains(*coord)
        correctly_rejected = not is_contained

        print(f"\n  {label}:")
        print(f"    User coord:    {_fmt_xyz(coord)}")
        print(f"    Machine coord: {_fmt_xyz(machine)}")
        print(f"    Violation:     {violation}")
        print(f"    contains():    {is_contained}")

        if correctly_rejected:
            print(f"    [{PASS}] Correctly identified as out-of-bounds")
            passed += 1
        else:
            print(f"    [{FAIL}] Should have been rejected but was accepted")
            failed += 1

    print("\n--- In-bounds coordinates (sanity check — should be accepted) ---")
    in_bounds_cases = _build_in_bounds_cases(volume)
    for label, coord in in_bounds_cases:
        is_contained = volume.contains(*coord)
        machine = to_machine_coordinates(*coord)

        print(f"\n  {label}:")
        print(f"    User coord:    {_fmt_xyz(coord)}")
        print(f"    Machine coord: {_fmt_xyz(machine)}")
        print(f"    contains():    {is_contained}")

        if is_contained:
            print(f"    [{PASS}] Correctly accepted as in-bounds")
            passed += 1
        else:
            print(f"    [{FAIL}] Should have been accepted but was rejected")
            failed += 1

    print("\n" + "=" * 72)
    total = passed + failed
    print(f"Out-of-Bounds Validation: {passed}/{total} passed, {failed} failed")

    if failed == 0:
        print("All bounds checks are correct.")
        print("\nNote: Gantry.move_to() does NOT currently enforce bounds checking.")
        print("WorkingVolume.contains() can be used to add enforcement if needed.")
    else:
        print("Some bounds checks failed — review WorkingVolume.contains() logic.")

    print("=" * 72)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
