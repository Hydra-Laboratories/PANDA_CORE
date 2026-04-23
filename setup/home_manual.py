"""Manual origin homing script for the Genmitsu Desktop CNC.

Loads the standard Cub gantry config, overrides the homing strategy to
``manual_origin``, then runs interactive keyboard jogging to set work zero.
"""

import logging
import sys
import time
from dataclasses import replace
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from gantry import Gantry, HomingStrategy, load_gantry_from_yaml_safe

BASE_CONFIG = project_root / "configs" / "gantry" / "cub.yaml"


def main() -> None:
    print("=" * 50)
    print("  CUB — Manual Origin Homing")
    print("=" * 50)

    gantry_config = replace(
        load_gantry_from_yaml_safe(BASE_CONFIG),
        homing_strategy=HomingStrategy.MANUAL_ORIGIN,
    )

    with open(BASE_CONFIG) as f:
        raw_config = yaml.safe_load(f)
    raw_config["cnc"]["homing_strategy"] = "manual_origin"

    gantry = Gantry(config=raw_config)

    t0 = time.monotonic()
    print("\nConnecting to gantry...")
    gantry.connect()
    print(f"Connected in {time.monotonic() - t0:.1f}s")

    if not gantry.is_healthy():
        print("Error: Gantry is not healthy. Check the connection and try again.")
        gantry.disconnect()
        sys.exit(1)

    try:
        gantry.home()
        vol = gantry_config.working_volume
        print(f"\nWorking volume from origin:")
        print(f"  X: {vol.x_min} to {vol.x_max} mm")
        print(f"  Y: {vol.y_min} to {vol.y_max} mm")
        print(f"  Z: {vol.z_min} to {vol.z_max} mm")
        print("\nHoming complete. Ready for operations.")
    except KeyboardInterrupt:
        print("\nInterrupted — stopping motion...")
        gantry.stop()
    finally:
        print("Disconnecting...")
        gantry.disconnect()
        print("Done.")


if __name__ == "__main__":
    main()
