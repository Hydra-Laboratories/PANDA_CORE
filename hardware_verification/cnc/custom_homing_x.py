import sys
from pathlib import Path
import time
import re

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.hardware.gantry import Gantry
from src.protocol_engine.config import DeckConfig

# CONFIGURATION
HOMING_DIR_X = -1       # 1 = Right (Positive), -1 = Left (Negative)
HOMING_FEED_FAST = 500 # mm/min for initial seek
HOMING_FEED_SLOW = 50  # mm/min for fine seek
MAX_TRAVEL_X = 320.0   # mm (Safety stop)
BACKOFF_DIST = 2.0     # mm

def main():
    print("--------------------------------------------------")
    print("Custom X-Axis Homing (No Z-Switch Workaround)")
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
            
    cnc = Gantry(config=driver_config)
    try:
        cnc.connect()
        print(">> Connected!")
    except Exception as e:
        print(f">> Failed to connect: {e}")
        return

    mill = cnc._mill # Access internal driver for raw commands

    # 3. Homing Routine
    print(f"\nStarting Homing X... Direction: {'RIGHT' if HOMING_DIR_X > 0 else 'LEFT'}")
    print("Press Ctrl+C to abort immediately.")

    # Enable relative moves for seeking
    mill.execute_command("G91") 
    
    dist_moved = 0.0
    switch_hit = False

    try:
        # Fast Seek
        while dist_moved < MAX_TRAVEL_X:
            # Check Status
            status = mill.current_status()
            # Look for Pn:X (Limit switch triggered)
            # Example status: <Idle|MPos:0.000,0.000,0.000|FS:0,0|Pn:X>
            if "Pn:" in status and "X" in status.split("Pn:")[1].split("|")[0]:
                print(f"Switch Hit! (Status: {status.strip()})")
                switch_hit = True
                break
            
            # Move small step
            step = 1.0 * HOMING_DIR_X
            try:
                mill.execute_command(f"G1 X{step} F{HOMING_FEED_FAST}")
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
                
                if "error:9" in err_msg or "Alarm" in status or "Pn:" in status:
                    print(f"\nHit Switch during move! (Confirmed by: {err_msg if 'error:9' in err_msg else status})")
                    switch_hit = True
                    
                    # 1. Clear Alarm ($X)
                    print("Clearing Alarm ($X)...")
                    try:
                        mill.execute_command("$X")
                    except:
                        pass # Sometimes $X returns ok even if serial buffer weird
                        
                    time.sleep(1)
                    break
                else:
                    # Genuine error
                    raise e
            
            # Rate limit status checks slightly?
            # mill.execute_command waits for 'ok', so pace is controlled by machine buffer
            print(f"Seeking... {dist_moved:.1f}/{MAX_TRAVEL_X}mm", end="\r")

        if not switch_hit:
            print("\nError: Max travel reached without hitting switch.")
            return

        # Back off
        print(f"\nBacking off {BACKOFF_DIST}mm...")
        # Ensure we are in Relative Mode (G91)
        mill.execute_command("G91") 
        mill.execute_command(f"G0 X{-BACKOFF_DIST * HOMING_DIR_X}")
        
        # Fine Seek (Optional: re-approach slowly for accuracy)
        # For now, just back off and set zero.
        
        # Set Zero
        # Switch is at Machine Limit? Usually Machine Zero.
        # But for Work Zero, we usually set X=0 here (Right Side Zero).
        # Or if Left Side Zero, we set X=0.
        
        print("Setting X Zero (G10 L20 P1 X0)...")
        mill.execute_command("G10 L20 P1 X0")
        
        # Reset to Absolute Mode
        mill.execute_command("G90")
        print(">> Homing Complete. X Axis Zeroed.")

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
