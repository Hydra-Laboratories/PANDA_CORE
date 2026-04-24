"""First-run interactive router test.

Welcomes the user, homes the CNC gantry, then lets them jog the
router interactively with keyboard keys while displaying position.

Legacy note: this script predates the deck-origin calibration scheme. Use
setup/calibrate_deck_origin.py before trusting deck-origin configs, and replace
this jog UI before relying on it for +Z-up hardware bring-up.
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
from setup.keyboard_input import read_keypress

CONFIGS_DIR = project_root / "configs"

GANTRIES = {
    "CUB_XL": {
        "label": "Cub-XL (415x300x200mm)",
        "config_file": CONFIGS_DIR / "gantry" / "cub_xl.yaml",
    },
    "CUB": {
        "label": "Cub (300x200x80mm)",
        "config_file": CONFIGS_DIR / "gantry" / "cub.yaml",
    },
}

STEP = 1.0

CONTROLS_LEGEND = """
Controls:
  Arrow LEFT/RIGHT  — Move X axis (±1mm)
  Arrow UP/DOWN     — Move Y axis (-/+1mm)
  Z                 — Move Z down (+1mm)
  X                 — Move Z up (-1mm)
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
    print("  1) Cub-XL — the larger gantry  (415x300x200mm)")
    print("  2) Cub    — the smaller gantry (300x200x80mm)")

    while True:
        choice = input("\nEnter 1 or 2: ").strip()
        if choice in ("1", "2"):
            key = "CUB_XL" if choice == "1" else "CUB"
            gantry_entry = GANTRIES[key]
            config = load_gantry_config(gantry_entry["config_file"])
            return gantry_entry, config
        print("Invalid choice. Please enter 1 or 2.")


def main() -> None:
    print("=" * 50)
    print("  CubOS — Hello World")
    print("  First-run interactive jog test")
    print("=" * 50)

    gantry_entry, config = select_gantry()
    print(f"\nSelected: {gantry_entry['label']}")

    gantry = Gantry(config=config)
    volume = config["working_volume"]

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
            key = read_keypress()

            if key == "LEFT":
                gantry.jog(x=-STEP)
            elif key == "RIGHT":
                gantry.jog(x=STEP)
            elif key == "UP":
                gantry.jog(y=-STEP)
            elif key == "DOWN":
                gantry.jog(y=STEP)
            elif key == "Z":
                gantry.jog(z=STEP)
            elif key == "X":
                gantry.jog(z=-STEP)
            elif key == "Q":
                print("\nExiting...")
                break
            else:
                continue

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
