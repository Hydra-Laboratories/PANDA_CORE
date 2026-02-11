import time
from datetime import datetime
from src.protocol_engine.compiler import CompiledProtocol
from src.protocol_engine.camera import Camera
# Assuming Mill interface is duck-typed for now as passed in execution
# Or import type checking if available.
# from src.cnc_control.driver import Mill

class ProtocolExecutor:
    """Executes a compiled protocol on the hardware."""
    
    def __init__(self, mill, camera: Camera):
        """
        Initialize the executor.
        
        Args:
            mill: The Mill controller instance.
            camera: The Camera instance.
        """
        self.mill = mill
        self.camera = camera
        
    def execute(self, protocol: CompiledProtocol):
        """
        Execute the protocol steps.
        
        Args:
            protocol: The compiled protocol to execute.
        """
        for step in protocol.steps:
            if step.type == "move":
                params = step.parameters
                self.mill.move_to(
                    x=params["x"],
                    y=params["y"],
                    z=params["z"]
                )
            elif step.type == "image":
                params = step.parameters
                location = params.get("location", "unknown")
                label = params.get("label", "image")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{location}_{label}_{timestamp}.jpg"
                
                # In a real app we might want a specific directory
                self.camera.capture_image(filename)
                # Maybe Wait a bit?
                # time.sleep(0.5) 
            else:
                # Log unknown step?
                pass
