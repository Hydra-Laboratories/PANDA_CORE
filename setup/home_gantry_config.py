"""One-shot gantry homing from a gantry YAML file.

Loads a gantry config (default ``configs/gantry/cub.yaml``), connects, runs the
configured homing strategy (e.g. ``standard`` → GRBL ``$H``), optionally sets
work zero with ``G92 X0 Y0 Z0`` (same as the protocol ``home`` command), then
disconnects.

Usage::

    python setup/home_gantry_config.py
    python setup/home_gantry_config.py --gantry configs/gantry/cub_xl.yaml
    python setup/home_gantry_config.py --skip-zero
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from gantry import Gantry  # noqa: E402


def run_homing(gantry_path: Path, *, skip_zero: bool = False) -> None:
    """Home the gantry and optionally zero work coordinates at the current pose.

    Args:
        gantry_path: Path to a validated gantry YAML file.
        skip_zero: If True, do not send ``G92 X0 Y0 Z0`` after homing.
    """
    with gantry_path.open() as f:
        config = yaml.safe_load(f)
    if not config:
        raise ValueError(f"Gantry config is empty: {gantry_path}")

    gantry = Gantry(config=config)
    try:
        gantry.connect()
        gantry.home()
        if not skip_zero:
            gantry.zero_coordinates()
    finally:
        gantry.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Connect, run configured homing, optionally zero work coordinates (G92), disconnect."
        )
    )
    parser.add_argument(
        "--gantry",
        type=Path,
        default=Path("configs/gantry/cub.yaml"),
        help="Path to gantry YAML (default: configs/gantry/cub.yaml)",
    )
    parser.add_argument(
        "--skip-zero",
        action="store_true",
        help="Skip G92 X0 Y0 Z0 after homing",
    )
    args = parser.parse_args()

    gantry_path = args.gantry.resolve()
    if not gantry_path.is_file():
        print(f"ERROR: Gantry config not found: {gantry_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading: {gantry_path}")
    try:
        run_homing(gantry_path, skip_zero=args.skip_zero)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    main()
