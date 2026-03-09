"""Manual origin homing script for the Genmitsu Desktop CNC.

Connects to the CNC, runs the manual_origin homing strategy (interactive
keyboard jogging), then prints the confirmed working volume bounds.
"""

import logging
import sys
import time
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from gantry import Gantry, load_gantry_from_yaml_safe

DESKTOP_CONFIG = (
    project_root / "configs" / "gantry" / "genmitsu_3018_PRO_Desktop.yaml"
)


def main() -> None:
    print("=" * 50)
    print("  CUB — Manual Origin Homing")
    print("=" * 50)

    gantry_config = load_gantry_from_yaml_safe(DESKTOP_CONFIG)

    with open(DESKTOP_CONFIG) as f:
        raw_config = yaml.safe_load(f)

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
