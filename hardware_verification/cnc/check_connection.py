import sys
from pathlib import Path
import time

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.hardware.gantry import Gantry
from src.protocol_engine.config import DeckConfig

def main():
    print("--------------------------------------------------")
    print("CNC Hardware Connection Test")
    print("--------------------------------------------------")

    # 1. Load Configuration
    config_path = project_root / "configs/genmitsu_3018_PROver_v2.yaml"
    if not config_path.exists():
        # Fallback to desktop config if pro version not found
        config_path = project_root / "configs/genmitsu_3018_PRO_Desktop.yaml"
    
    if not config_path.exists():
        print(f"Error: No configuration file found in configs/")
        return

    print(f"Loading config from: {config_path}")
    try:
        config = DeckConfig.from_yaml(str(config_path))
        print(f"Config loaded. Serial Port: {config.serial_port}")
    except Exception as e:
        print(f"Failed to load config: {e}")
        return

    # 2. Initialize CNC Wrapper
    print("\nInitializing CNC Driver...")
    # Inject config in the format CNC expects
    driver_config = {"cnc": {"serial_port": config.serial_port}}
    cnc = Gantry(config=driver_config)

    # 3. Connect
    print("Attempting to connect...")
    try:
        cnc.connect()
        print(">> Connection Successful!")
    except Exception as e:
        print(f">> Connection FAILED: {e}")
        return

    # 4. Check Health & Status
    print("\nChecking Instrument Health...")
    is_healthy = cnc.is_healthy()
    print(f"Health Check: {'PASSED' if is_healthy else 'FAILED'}")

    if is_healthy:
        try:
            # Access internal mill for detailed status if needed, 
            # or rely on what CNC exposes (currently only basic methods)
            # Let's inspect the internal status string for more info
            status = cnc.get_status()
            print(f"Current Status: {status}")
            
            coords = cnc.get_coordinates()
            print(f"Current Coordinates: X={coords['x']}, Y={coords['y']}, Z={coords['z']}")
            
        except Exception as e:
            print(f"Error reading status: {e}")

    # 5. Check G-code State
    print("\nChecking G-code Parser State ($G)...")
    try:
        # We need to access the serial directly or use a command method if available
        # The CNC class doesn't expose a direct 'send_command_and_read' easily for arbitrary commands
        # But we can use the _mill.execute_command if we are careful, or better, just use the internal serial
        # We can use the _mill.execute_command if we are careful
        responses = cnc._mill.execute_command("$G")
        print(f"G-code State: {responses}")
        
        if "G90" in str(responses):
            print(">> Mode: Absolute (G90)")
        elif "G91" in str(responses):
            print(">> Mode: Relative (G91)")
        else:
            print(">> Mode: Unknown")
            
    except Exception as e:
        print(f"Failed to get G-code state: {e}")

    # 6. Disconnect
    print("\nDisconnecting...")
    cnc.disconnect()
    print("Disconnected.")
    print("--------------------------------------------------")

if __name__ == "__main__":
    main()
