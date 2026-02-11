from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict
from src.cnc_control.driver import Mill
from src.protocol_engine.config import DeckConfig
from pathlib import Path

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="src/web_server/static", html=True), name="static")

# Singleton Mill instance
mill_instance = None
CONFIG_PATH = Path("configs/genmitsu_3018_PROver_v2.yaml")
deck_config = None

class MoveRequest(BaseModel):
    x: float
    y: float
    z: float

@app.on_event("startup")
async def startup_event():
    global deck_config, mill_instance
    try:
        if CONFIG_PATH.exists():
            deck_config = DeckConfig.from_yaml(str(CONFIG_PATH))
            print(f"Loaded config from {CONFIG_PATH}")
        else:
            print(f"Warning: Config file not found at {CONFIG_PATH}")
            deck_config = None
            
        # Optional: Auto-connect on startup using config?
        # For safety, let's wait for user to hit "Connect" in UI
    except Exception as e:
        print(f"Startup error: {e}")

@app.post("/connect")
async def connect_mill():
    global mill_instance
    try:
        if mill_instance and mill_instance.active_connection:
             return {"status": "Already Connected"}
        
        port = deck_config.serial_port if deck_config else None
        print(f"Connecting to mill on port {port}...")
        
        # Initialize Mill
        mill_instance = Mill(port=port)
        mill_instance.connect_to_mill(port=port)
        mill_instance.set_feed_rate(5000) # Required for G01 moves (fixes error:22)
        # We don't use 'with' here because we want to keep it open
        
        return {"status": "Connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/move")
async def move_mill(request: MoveRequest):
    global mill_instance
    
    if not mill_instance or not mill_instance.active_connection:
        raise HTTPException(status_code=400, detail="Mill not connected")
        
    # Validate bounds
    if deck_config:
        bounds = deck_config.machine_bounds
        if not (bounds.x_min <= request.x <= bounds.x_max):
             raise HTTPException(status_code=400, detail=f"X out of bounds [{bounds.x_min}, {bounds.x_max}]")
        if not (bounds.y_min <= request.y <= bounds.y_max):
             raise HTTPException(status_code=400, detail=f"Y out of bounds [{bounds.y_min}, {bounds.y_max}]")
        if not (bounds.z_min <= request.z <= bounds.z_max):
             raise HTTPException(status_code=400, detail=f"Z out of bounds [{bounds.z_min}, {bounds.z_max}]")

    try:
        # Move logic
        mill_instance.move_to_position(request.x, request.y, request.z)
        return {"status": "Moved", "x": request.x, "y": request.y, "z": request.z}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def get_status():
    connected = mill_instance is not None and mill_instance.active_connection
    return {
        "connected": connected,
        # TODO: Retrieve actual position from Mill if driver supports it easily
        # For now, UI tracks sent moves
    }
