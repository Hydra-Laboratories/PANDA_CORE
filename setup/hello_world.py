"""First-run interactive router test.

Welcomes the user, homes the CNC machine, then lets them jog the
router interactively with keyboard keys while displaying position.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.hardware.gantry import Gantry
from setup.keyboard_input import read_keypress

# Working volume limits (machine uses negative coordinates)
X_MIN, X_MAX = -300.0, 0.0
Y_MIN, Y_MAX = -200.0, 0.0
Z_MIN, Z_MAX = -80.0, 0.0

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


def main() -> None:
    print("=" * 50)
    print("  PANDA CNC — Hello World")
    print("  First-run interactive jog test")
    print("=" * 50)

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
                x = clamp(x - STEP, X_MIN, X_MAX)
            elif key == "RIGHT":
                x = clamp(x + STEP, X_MIN, X_MAX)
            elif key == "UP":
                y = clamp(y + STEP, Y_MIN, Y_MAX)
            elif key == "DOWN":
                y = clamp(y - STEP, Y_MIN, Y_MAX)
            elif key == "Z":
                z = clamp(z - STEP, Z_MIN, Z_MAX)
            elif key == "X":
                z = clamp(z + STEP, Z_MIN, Z_MAX)
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
