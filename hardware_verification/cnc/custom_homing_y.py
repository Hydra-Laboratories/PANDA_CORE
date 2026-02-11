import sys
from pathlib import Path
import time
import re

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.core.instruments.cnc import CNC
from src.protocol_engine.config import DeckConfig

# CONFIGURATION
# Standard Y Homing is towards BACK (Positive)
# If your switch is at the FRONT, set this to -1
HOMING_DIR_Y = 1       # 1 = Back (Positive), -1 = Front (Negative)
HOMING_FEED_FAST = 500 # mm/min for initial seek
MAX_TRAVEL_Y = 320.0   # mm (Safety stop)
BACKOFF_DIST = 2.0     # mm

def main():
    print("--------------------------------------------------")
    print("Custom Y-Axis Homing (No Z-Switch Workaround)")
    print("--------------------------------------------------")

    # 1. Load Config
    config_path = project_root / "configs/genmitsu_3018_PROver_v2.yaml"
    if not config_path.exists():
        config_path = project_root / "configs/genmitsu_3018_PRO_Desktop.yaml"
    
    # 2. Connect
    print("Connecting...")
    driver_config = {}
    if config_path.exists():
        try:
            cfg = DeckConfig.from_yaml(str(config_path))
            driver_config = {"cnc": {"serial_port": cfg.serial_port}}
        except:
            pass
            
    cnc = CNC(config=driver_config)
    try:
        cnc.connect()
        print(">> Connected!")
    except Exception as e:
        print(f">> Failed to connect: {e}")
        return

    mill = cnc._mill # Access internal driver for raw commands

    # 3. Homing Routine
    print(f"\nStarting Homing Y... Direction: {'BACK (Positive)' if HOMING_DIR_Y > 0 else 'FRONT (Negative)'}")
    print("Press Ctrl+C to abort immediately.")

    # Enable relative moves for seeking
    mill.execute_command("G91") 
    
    dist_moved = 0.0
    switch_hit = False

    try:
        # Fast Seek
        while dist_moved < MAX_TRAVEL_Y:
            # Move small step
            step = 5.0 * HOMING_DIR_Y
            try:
                mill.execute_command(f"G1 Y{step} F{HOMING_FEED_FAST}")
                dist_moved += abs(step)
            except Exception as e:
                # If we hit a hard limit during motion, GRBL will alarm and return error:9 or similar
                # Check if the error message itself contains the specific code
                err_msg = str(e)
                status = ""
                try:
                    status = mill.current_status()
                except:
                    pass
                
                # Check for error:9 (Hard Limit) or Pn:Y trigger
                is_hit = "error:9" in err_msg or "Alarm" in status
                if "Pn:" in status and "Y" in status.split("Pn:")[1].split("|")[0]:
                    is_hit = True
                
                if is_hit:
                    print(f"\nHit Switch during move! (Confirmed by: {err_msg if 'error:9' in err_msg else status})")
                    switch_hit = True
                    
                    # 1. Clear Alarm ($X)
                    print("Clearing Alarm ($X)...")
                    try:
                        mill.execute_command("$X")
                    except:
                        pass 
                        
                    time.sleep(1)
                    break
                else:
                    # Genuine error
                    raise e
            
            print(f"Seeking... {dist_moved:.1f}/{MAX_TRAVEL_Y}mm", end="\r")

        if not switch_hit:
            print("\nError: Max travel reached without hitting switch.")
            return

        # Back off
        print(f"\nBacking off {BACKOFF_DIST}mm...")
        # Ensure we are in Relative Mode (G91)
        mill.execute_command("G91") 
        # Move opposite direction
        mill.execute_command(f"G0 Y{-BACKOFF_DIST * HOMING_DIR_Y}")
        
        # Set Zero
        print("Setting Y Zero (G10 L20 P1 Y0)...")
        mill.execute_command("G10 L20 P1 Y0")
        
        # Reset to Absolute Mode
        mill.execute_command("G90")
        print(">> Homing Complete. Y Axis Zeroed.")

    except KeyboardInterrupt:
        print("\nAborted by user.")
        mill.soft_reset()
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        cnc.disconnect()
        print("Disconnected.")

if __name__ == "__main__":
    main()
