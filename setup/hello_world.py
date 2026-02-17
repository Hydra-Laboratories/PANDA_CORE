"""First-run interactive router test.

Welcomes the user, homes the CNC gantry, then lets them jog the
router interactively with keyboard keys while displaying position.
"""

import logging
import sys
import time
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from gantry import Gantry
from setup.keyboard_input import read_keypress_batch, flush_stdin

CONFIGS_DIR = project_root / "configs"

GANTRIES = {
    "PANDA": {
        "label": "PANDA (XL — 415x300x200mm)",
        "config_file": CONFIGS_DIR / "gantries" / "genmitsu_3018_PROver_v2.yaml",
    },
    "CUB": {
        "label": "CUB (Small — 300x200x80mm)",
        "config_file": CONFIGS_DIR / "gantries" / "genmitsu_3018_PRO_Desktop.yaml",
    },
}

STEP = 1.0
MAX_STEP = 10.0

CONTROLS_LEGEND = """
Controls:
  Arrow LEFT/RIGHT  — Move X axis (±1mm)
  Arrow UP/DOWN     — Move Y axis (±1mm)
  Z                 — Move Z down (1mm)
  X                 — Move Z up (1mm)
  Q                 — Quit
"""


def print_position(coords: dict) -> None:
    print(f"  Position -> X: {coords['x']:.1f}  Y: {coords['y']:.1f}  Z: {coords['z']:.1f}")


def load_gantry_config(config_file: Path) -> dict:
    with open(config_file) as f:
        return yaml.safe_load(f)


def select_gantry() -> tuple:
    """Returns (gantry_entry, loaded_config)."""
    print("\nWhich system are you working with?")
    print("  1) PANDA  — the larger XL gantry (415x300x200mm)")
    print("  2) CUB    — the smaller gantry   (300x200x80mm)")

    while True:
        choice = input("\nEnter 1 or 2: ").strip()
        if choice in ("1", "2"):
            key = "PANDA" if choice == "1" else "CUB"
            gantry_entry = GANTRIES[key]
            config = load_gantry_config(gantry_entry["config_file"])
            return gantry_entry, config
        print("Invalid choice. Please enter 1 or 2.")


def main() -> None:
    print("=" * 50)
    print("  PANDA CNC — Hello World")
    print("  First-run interactive jog test")
    print("=" * 50)

    gantry_entry, config = select_gantry()
    print(f"\nSelected: {gantry_entry['label']}")

    gantry = Gantry(config=config)

    t0 = time.monotonic()
    print("\nConnecting to gantry...")
    gantry.connect()
    print(f"Connected in {time.monotonic() - t0:.1f}s")

    if not gantry.is_healthy():
        print("Error: Gantry is not healthy. Check the connection and try again.")
        gantry.disconnect()
        sys.exit(1)

    print("Connected successfully.")

    try:
        input("\nPress ENTER to home the gantry...")
        print("Homing... (this may take a moment)")
        gantry.home()
        print("Homing complete.")

        coords = gantry.get_coordinates()
        print_position(coords)
        print(CONTROLS_LEGEND)

        while True:
            key, count = read_keypress_batch()
            step = min(STEP * count, MAX_STEP)

            x, y, z = coords["x"], coords["y"], coords["z"]

            if key == "LEFT":
                x -= step
            elif key == "RIGHT":
                x += step
            elif key == "UP":
                y += step
            elif key == "DOWN":
                y -= step
            elif key == "Z":
                z -= step
            elif key == "X":
                z += step
            elif key == "Q":
                print("\nExiting...")
                break
            else:
                continue

            gantry.move_to(x, y, z)
            flush_stdin()
            coords = gantry.get_coordinates()
            print_position(coords)

    except KeyboardInterrupt:
        print("\nInterrupted — stopping motion...")
        gantry.stop()
    finally:
        print("Disconnecting...")
        gantry.disconnect()
        print("Done.")


if __name__ == "__main__":
    main()
