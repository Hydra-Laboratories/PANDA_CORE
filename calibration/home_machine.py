import sys
from pathlib import Path

import yaml

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.gantry import Gantry


def main():
    print("--------------------------------------------------")
    print("CNC Homing Wrapper")
    print("--------------------------------------------------")

    config_path = project_root / "configs/genmitsu_3018_PROver_v2.yaml"
    if not config_path.exists():
        print(f"Config not found at {config_path}")
        return

    try:
        with open(config_path) as f:
            driver_config = yaml.safe_load(f)
        print(f"Loaded config from {config_path}")
    except Exception as e:
        print(f"Failed to load config: {e}")
        return

    gantry = Gantry(config=driver_config)
    
    try:
        print("Connecting to CNC...")
        gantry.connect()
        if not gantry.is_healthy():
            print("Warning: Health check failed (possibly alarm state), attempting to proceed with homing anyway...")

        print("Starting homing sequence (XY hard limits)...")
        gantry.home()
        print(">> Homing complete.")
    except KeyboardInterrupt:
        print("\nAborted by user.")
    except Exception as e:
        print(f"\nError during homing: {e}")
    finally:
        print("Disconnecting...")
        gantry.disconnect()

if __name__ == "__main__":
    main()
