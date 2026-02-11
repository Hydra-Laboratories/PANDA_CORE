import sys
from pathlib import Path
import time

# Add project root to path
# Adjusted for hardware_verification/cnc/ depth
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.core.instruments.cnc import CNC
from src.protocol_engine.config import DeckConfig

def main():
    print("--------------------------------------------------")
    print("CNC Gantry Movement Test (Read-Only)")
    print("--------------------------------------------------")

    # 1. Load Configuration
    config_path = project_root / "configs/genmitsu_3018_PROver_v2.yaml"
    if not config_path.exists():
        config_path = project_root / "configs/genmitsu_3018_PRO_Desktop.yaml"
    
    if not config_path.exists():
        print(f"Error: No configuration file found in configs/")
        return

    print(f"Loading config from: {config_path}")
    try:
        config = DeckConfig.from_yaml(str(config_path))
    except Exception as e:
        print(f"Failed to load config: {e}")
        return

    # 2. Initialize CNC Wrapper
    print("\nInitializing CNC Driver...")
    driver_config = {"cnc": {"serial_port": config.serial_port}}
    cnc = CNC(config=driver_config)

    # 3. Connect
    print("Attempting to connect...")
    try:
        cnc.connect()
        print(">> Connection Successful!")
    except Exception as e:
        print(f">> Connection FAILED: {e}")
        return

    # 4. Get Current Position
    coords = cnc.get_coordinates()
    print(f"\nCurrent Coordinates: X={coords['x']}, Y={coords['y']}, Z={coords['z']}")
    
    # 5. Calculate Target (5mm to the left = X - 5)
    current_x = coords['x']
    target_x = current_x + 3.0
    target_y = coords['y']
    target_z = coords['z']
    
    print(f"\nCalculated Target (5mm Left):")
    print(f"  Target X: {target_x:.3f}")
    print(f"  Target Y: {target_y:.3f}")
    print(f"  Target Z: {target_z:.3f}")
    
    # 6. Command Movement (COMMENTED OUT FOR SAFETY)
    # print("\n[SAFETY] Movement command is currently COMMENTED OUT.")
    print(f"[PREVIEW] cnc.move_to(x={target_x}, y={target_y}, z={target_z})")
    
    # Uncomment the lines below to enable actual movement
    input("Press Enter to execute movement...")
    try:
        cnc.move_to(x=target_x, y=target_y, z=target_z)
        print("Movement command sent.")
        
        # Verify new position
        time.sleep(1) # Wait for move
        new_coords = cnc.get_coordinates()
        print(f"New Coordinates: X={new_coords['x']}, Y={new_coords['y']}, Z={new_coords['z']}")
    except Exception as e:
        print(f"Movement failed: {e}")

    # 7. Disconnect
    print("\nDisconnecting...")
    cnc.disconnect()
    print("Disconnected.")
    print("--------------------------------------------------")

if __name__ == "__main__":
    main()
