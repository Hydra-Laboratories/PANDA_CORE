import time
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from src.cnc_control.driver import Mill
from src.protocol_engine.config import DeckConfig
from src.protocol_engine.schema import ExperimentSequence, MoveAction, ImageAction
from src.protocol_engine.compiler import Compiler
from src.protocol_engine.executor import ProtocolExecutor
from src.protocol_engine.camera import Camera

def main():
    print("Initializing Experiment Engine Verification...")
    
    # 1. Load Config
    config_path = Path("configs/genmitsu_3018_deck_config.yaml")
    if not config_path.exists():
        print(f"Error: Config file not found at {config_path}")
        return
        
    config = DeckConfig.from_yaml(str(config_path))
    print("Deck Config loaded.")
    
    # 2. Define Experiment Sequence (Load from YAML)
    experiment_path = Path("experiments/simple_imaging_protocol.yaml")
    if len(sys.argv) > 1:
        experiment_path = Path(sys.argv[1])
        
    if not experiment_path.exists():
         print(f"Error: Experiment file not found at {experiment_path}")
         return

    try:
        sequence = ExperimentSequence.from_yaml(str(experiment_path))
    except Exception as e:
        print(f"Error validating experiment sequence: {e}")
        return
        
    print(f"Sequence defined: {sequence.name} with {len(sequence.actions)} actions.")
    
    # 3. Compile
    compiler = Compiler(config)
    try:
        protocol = compiler.compile(sequence)
        print(f"Protocol compiled successfully. {len(protocol.steps)} steps generated.")
        
        # Print steps for preview
        for i, step in enumerate(protocol.steps):
            print(f"  Step {i+1}: {step.type} {step.parameters}")
            
    except Exception as e:
        print(f"Compilation failed: {e}")
        return

    # 4. Execute
    response = input("\nReady to execute on REAL HARDWARE? (y/n): ")
    if response.lower() != 'y':
        print("Aborting execution.")
        return

    try:
        # Connect to Mill
        print("Connecting to Mill...")
        # configure Mill based on config
        mill = Mill(port=config.serial_port)
        mill.auto_home = config.homing_enabled
        
        with mill:
            if config.homing_enabled:
                print("Homing enabled, waiting for homing...")
                # mill.home() # handled by auto_home=True in __enter__
            else:
                print("Homing disabled. Assuming current position is valid context or manually set.")
                # We might want to set coordinates to 0,0,0 or just warn user
                print("WARNING: Ensure machine is zeroed at Home (Work Coordinates).")
            
            # Initialize Camera
            print(f"Initializing Camera (Source {config.camera_source})...")
            try:
                camera = Camera(source=config.camera_source)
            except IOError as e:
                print(f"Failed to open configured camera source {config.camera_source}: {e}")
                raise e
            
            executor = ProtocolExecutor(mill=mill, camera=camera)
            
            print("Starting Execution...")
            start_time = time.time()
            
            try:
                executor.execute(protocol)
            except Exception as e:
                print(f"An error occurred during execution: {e}")
                print("Attempting to return to HOME (0, 0, 0)...")
                try:
                    # Move to safe Z first if possible, then home
                    # But using standard move_to_position(0,0,0) should be okay if path planner logic was used, 
                    # except here we are bypassing planner and sending direct command.
                    # Safety is paramount.
                    # Let's try to move to 0,0,0 directly.
                    mill.move_to_position(0, 0, 0)
                    print("Returned to HOME.")
                except Exception as cleanup_error:
                    print(f"CRITICAL: Failed to return to home during cleanup: {cleanup_error}")
                raise e
            finally:
                if 'camera' in locals():
                    camera.close()
            
            end_time = time.time()
            
            print(f"Execution completed in {end_time - start_time:.2f} seconds.")
            
    except Exception as e:
        print(f"Execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
