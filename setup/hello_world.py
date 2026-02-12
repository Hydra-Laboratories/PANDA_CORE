"""First-run interactive router test.

Welcomes the user, homes the CNC machine, then lets them jog the
router interactively with keyboard keys while displaying position.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.gantry import Gantry
from setup.keyboard_input import read_keypress

MACHINES = {
    "PANDA": {
        "label": "PANDA (XL — 415x300x200mm)",
        "x_min": -415.0, "x_max": 0.0,
        "y_min": -300.0, "y_max": 0.0,
        "z_min": -200.0, "z_max": 0.0,
    },
    "CUB": {
        "label": "CUB (Small — 300x200x80mm)",
        "x_min": -300.0, "x_max": 0.0,
        "y_min": -200.0, "y_max": 0.0,
        "z_min": -80.0,  "z_max": 0.0,
    },
}

STEP = 1.0

CONTROLS_LEGEND = """
Controls:
  Arrow LEFT/RIGHT  — Move X axis (±1mm)
  Arrow UP/DOWN     — Move Y axis (±1mm)
  Z                 — Move Z down (1mm)
  X                 — Move Z up (1mm)
  Q                 — Quit
"""


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def print_position(coords: dict) -> None:
    print(f"  Position -> X: {coords['x']:.1f}  Y: {coords['y']:.1f}  Z: {coords['z']:.1f}")


def select_machine() -> dict:
    print("\nWhich system are you working with?")
    print("  1) PANDA  — the larger XL machine (415x300x200mm)")
    print("  2) CUB    — the smaller machine   (300x200x80mm)")

    while True:
        choice = input("\nEnter 1 or 2: ").strip()
        if choice == "1":
            return MACHINES["PANDA"]
        if choice == "2":
            return MACHINES["CUB"]
        print("Invalid choice. Please enter 1 or 2.")


def main() -> None:
    print("=" * 50)
    print("  PANDA CNC — Hello World")
    print("  First-run interactive jog test")
    print("=" * 50)

    machine = select_machine()
    print(f"\nSelected: {machine['label']}")

    gantry = Gantry()

    print("\nConnecting to gantry...")
    gantry.connect()

    if not gantry.is_healthy():
        print("Error: Gantry is not healthy. Check the connection and try again.")
        gantry.disconnect()
        sys.exit(1)

    print("Connected successfully.")

    input("\nPress ENTER to home the machine...")
    print("Homing... (this may take a moment)")
    gantry.home()
    print("Homing complete.")

    coords = gantry.get_coordinates()
    print_position(coords)
    print(CONTROLS_LEGEND)

    try:
        while True:
            key = read_keypress()

            x, y, z = coords["x"], coords["y"], coords["z"]

            if key == "LEFT":
                x = clamp(x - STEP, machine["x_min"], machine["x_max"])
            elif key == "RIGHT":
                x = clamp(x + STEP, machine["x_min"], machine["x_max"])
            elif key == "UP":
                y = clamp(y + STEP, machine["y_min"], machine["y_max"])
            elif key == "DOWN":
                y = clamp(y - STEP, machine["y_min"], machine["y_max"])
            elif key == "Z":
                z = clamp(z - STEP, machine["z_min"], machine["z_max"])
            elif key == "X":
                z = clamp(z + STEP, machine["z_min"], machine["z_max"])
            elif key == "Q":
                print("\nExiting...")
                break
            else:
                continue

            gantry.move_to(x, y, z)
            coords = gantry.get_coordinates()
            print_position(coords)

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        print("Disconnecting...")
        gantry.disconnect()
        print("Done.")


if __name__ == "__main__":
    main()
