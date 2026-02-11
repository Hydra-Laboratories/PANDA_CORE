import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.core.instruments.cnc import CNC
from src.protocol_engine.config import DeckConfig

def main():
    print("--------------------------------------------------")
    print("CNC Homing Wrapper")
    print("--------------------------------------------------")

    # 1. Load Config (to replicate how DeckConfig loads it, 
    # ensuring we get the serial port and strategy)
    config_path = project_root / "configs/genmitsu_3018_PROver_v2.yaml"
    
    # Simple direct load or use DeckConfig if preferred
    # Using DeckConfig to be consistent with app usage if possible, 
    # but strictly CNC class takes a dict.
    
    driver_config = {}
    if config_path.exists():
        try:
            cfg = DeckConfig.from_yaml(str(config_path))
            # Construct the config dict expected by CNC
            # CNC expects {'serial_port': '...', 'cnc': {'homing_strategy': '...'}} possibly
            # The CNC class init: self.config = config or {}
            # BaseInstrument loads nothing by default.
            # IN cnc.py: connect() looks at self.config['cnc']['serial_port'] or self.config['serial_port']
            # IN cnc.py: home() looks at self.config['cnc']['homing_strategy']
            
            # DeckConfig structure usually flat? Let's check DeckConfig if needed.
            # For now, let's just manually load the yaml to ensure we structure the dict correctly for CNC class
            import yaml
            with open(config_path, 'r') as f:
                raw_config = yaml.safe_load(f)
            
            driver_config = raw_config 
            print(f"Loaded config from {config_path}")
        except Exception as e:
            print(f"Failed to load config: {e}")
            return
    else:
        print(f"Config not found at {config_path}")
        return

    cnc = CNC(config=driver_config)
    
    try:
        print("Connecting to CNC...")
        cnc.connect()
        if not cnc.health_check():
             print("Warning: Health check failed (possibly alarm state), attempting to proceed with homing anyway...")
        
        print("Starting Homing Sequence...")
        cnc.home()
        print(">> Homing Sequence Complete.")
        
    except KeyboardInterrupt:
        print("\nAborted by user.")
    except Exception as e:
        print(f"\nError during homing: {e}")
    finally:
        print("Disconnecting...")
        cnc.disconnect()

if __name__ == "__main__":
    main()
