import pytest
from pydantic import ValidationError
from src.protocol_engine.schema import MoveAction, ImageAction, ExperimentSequence

def test_move_action_valid():
    """Test creating a valid MoveAction."""
    action = MoveAction(target_location="well_A1", instrument="pipette")
    assert action.action_type == "move"
    assert action.target_location == "well_A1"
    assert action.instrument == "pipette"
    assert action.z_offset == 0.0

def test_move_action_defaults():
    """Test MoveAction default values."""
    action = MoveAction(target_location="home", instrument="center")
    assert action.z_offset == 0.0

def test_image_action_valid():
    """Test creating a valid ImageAction."""
    action = ImageAction(target_location="well_A1", label="before_process")
    assert action.action_type == "image"
    assert action.target_location == "well_A1"
    assert action.label == "before_process"

def test_experiment_sequence_valid():
    """Test creating a valid ExperimentSequence with multiple actions."""
    move = MoveAction(target_location="well_A1", instrument="pipette")
    image = ImageAction(target_location="well_A1", label="check")
    seq = ExperimentSequence(name="Test Sequence", actions=[move, image])
    
    assert seq.name == "Test Sequence"
    assert len(seq.actions) == 2
    assert seq.actions[0] == move
    assert seq.actions[1] == image

def test_experiment_sequence_invalid_action():
    """Test ExperimentSequence validation with invalid action type."""
    with pytest.raises(ValidationError):
        ExperimentSequence(name="Invalid", actions=[{"invalid": "dict"}])

def test_move_action_invalid_instrument():
    """Test MoveAction validation (generic check, specific validation logic might be in Planner later)."""
    # Simply ensuring it accepts strings for now
    action = MoveAction(target_location="loc", instrument="unknown_instrument")
    assert action.instrument == "unknown_instrument"

# Deck Config Tests
from src.protocol_engine.config import DeckConfig, MachineBounds
from src.instrument_drivers.cnc_driver.instruments import Coordinates

def test_deck_config_valid():
    """Test creating a valid DeckConfig from a dictionary."""
    config_data = {
        "machine_bounds": {
            "x_min": -415, "x_max": 0,
            "y_min": -300, "y_max": 0,
            "z_min": -75, "z_max": 0
        },
        "safe_z_height": -5.0,
        "locations": {
            "home": {"x": 0, "y": 0, "z": 0},
            "well_A1": {"x": -10, "y": -10, "z": -10}
        }
    }
    config = DeckConfig(**config_data)
    
    assert config.safe_z_height == -5.0
    assert config.locations["home"].x == 0
    assert config.locations["well_A1"].x == -10
    assert config.machine_bounds.x_min == -415

def test_deck_config_missing_bounds():
    """Test validation when bounds are missing."""
    with pytest.raises(ValidationError):
        DeckConfig(safe_z_height=0, locations={})

def test_deck_config_load_yaml(tmp_path):
    """Test loading DeckConfig from a YAML file."""
    import yaml
    
    config_data = {
        "machine_bounds": {
            "x_min": -100, "x_max": 0,
            "y_min": -100, "y_max": 0,
            "z_min": -50, "z_max": 0
        },
        "safe_z_height": -1.0,
        "locations": {
            "test_loc": {"x": -50, "y": -50, "z": -5}
        }
    }
    
    config_file = tmp_path / "deck_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
        
    config = DeckConfig.from_yaml(str(config_file))
    assert config.machine_bounds.x_min == -100
    assert config.locations["test_loc"].y == -50

# Path Planner Tests
from src.protocol_engine.path_planner import PathPlanner
from src.protocol_engine.config import CoordinateModel

def test_path_planner_validate_bounds_success():
    """Test valid coordinates within bounds."""
    bounds = MachineBounds(x_min=-100, x_max=0, y_min=-100, y_max=0, z_min=-50, z_max=0)
    # config is only needed for safe z, bounds can be passed or attached to config? 
    # Let's assume PathPlanner takes DeckConfig.
    config = DeckConfig(
        machine_bounds=bounds, 
        safe_z_height=-5.0, 
        locations={}
    )
    planner = PathPlanner(config)
    
    valid_coord = CoordinateModel(x=-10, y=-10, z=-10)
    # Should not raise
    planner.validate_bounds(valid_coord)

def test_path_planner_validate_bounds_failure():
    """Test coordinates outside bounds."""
    bounds = MachineBounds(x_min=-100, x_max=0, y_min=-100, y_max=0, z_min=-10, z_max=0)
    config = DeckConfig(machine_bounds=bounds, safe_z_height=-5, locations={})
    planner = PathPlanner(config)
    
    invalid_coord = CoordinateModel(x=-150, y=0, z=0)
    with pytest.raises(ValueError):
        planner.validate_bounds(invalid_coord)

def test_path_planner_plan_naive():
    """Test naive path generation: Lift -> Move XY -> Lower."""
    bounds = MachineBounds(x_min=-100, x_max=0, y_min=-100, y_max=0, z_min=-50, z_max=0)
    config = DeckConfig(machine_bounds=bounds, safe_z_height=-5.0, locations={})
    planner = PathPlanner(config)
    
    start = CoordinateModel(x=0, y=0, z=-10)
    end = CoordinateModel(x=-10, y=-10, z=-20)
    
    plan = planner.plan_path(start, end)
    
    # Expect 3 waypoints if start Z < safe Z
    # 1. Lift to safe Z (-5) at start XY (0,0)
    # 2. Move to end XY (-10, -10) at safe Z (-5)
    # 3. Lower to end Z (-20) at end XY (-10, -10)
    
    assert len(plan.waypoints) == 3
    
    # Waypoint 1: Lift
    assert plan.waypoints[0].x == start.x
    assert plan.waypoints[0].y == start.y
    assert plan.waypoints[0].z == config.safe_z_height
    
    # Waypoint 2: Travel XY
    assert plan.waypoints[1].x == end.x
    assert plan.waypoints[1].y == end.y
    assert plan.waypoints[1].z == config.safe_z_height
    
    # Waypoint 3: Lower
    assert plan.waypoints[2].x == end.x
    assert plan.waypoints[2].y == end.y
    assert plan.waypoints[2].z == end.z

def test_path_planner_plan_naive_already_safe():
    """Test optimization: if already at safe Z, don't lift unnecessarily?"""
    # For now, simplistic implementation might always lift or check z.
    # If start Z is safe (e.g. -2) and safe Z is -5 (higher/safer?), wait. 
    # Usually Z=0 is highest/safest? 
    # My config has safe_z_height = -5.0. 
    # If I am at -2 (higher than -5), I am SAFE.
    # If I am at -10 (lower than -5), I am UNSAFE.
    
    bounds = MachineBounds(x_min=-100, x_max=0, y_min=-100, y_max=0, z_min=-50, z_max=0)
    config = DeckConfig(machine_bounds=bounds, safe_z_height=-5.0, locations={})
    planner = PathPlanner(config)
    
    # Start at -2 (above safe height -5).
    # End at -10.
    start = CoordinateModel(x=0, y=0, z=-2)
    end = CoordinateModel(x=-10, y=-10, z=-10)
    
    # Naive implementation might still lift to safe Z (-5) which is actually LOWER than -2?
    # Wait, Z=0 is top. -5 is below top. -75 is bottom.
    # Safe Z height is typically HIGH (close to 0).
    # If I am at -2, getting to -5 is moving DOWN?
    # Usually "Safe Z" means "Travel Height".
    # So we should always move to Safe Z for travel unless we are higher?
    # If safe Z is -5, and we are at -2, we can travel?
    # Let's just enforce: Go to Safe Z (-5), Travel, Go to Target.
    # If Safe Z (-5) is lower than current (-2), that's a risk if there are obstacles at -2... 
    # But usually Safe Z is the configured "clearance plane".
    # Let's stick to the simple plan: Move Z -> Safe Z, Move XY, Move Z -> Target.
    
    plan = planner.plan_path(start, end)
    
    assert plan.waypoints[0].z == start.z
    assert plan.waypoints[0].x == end.x
    assert plan.waypoints[0].y == end.y

# Compiler Tests
from src.protocol_engine.compiler import Compiler
from src.protocol_engine.schema import MoveAction, ImageAction, ExperimentSequence

def test_compiler_compile_valid_sequence():
    """Test compiling a simple move -> image -> move sequence."""
    bounds = MachineBounds(x_min=-100, x_max=0, y_min=-100, y_max=0, z_min=-50, z_max=0)
    config = DeckConfig(
        machine_bounds=bounds, 
        safe_z_height=-5.0, 
        locations={
            "home": {"x": 0, "y": 0, "z": 0},
            "loc_A": {"x": -10, "y": -10, "z": -10}
        }
    )
    
    actions = [
        MoveAction(target_location="loc_A", instrument="center"),
        ImageAction(target_location="loc_A", label="test_img"),
        MoveAction(target_location="home", instrument="center")
    ]
    seq = ExperimentSequence(name="Test Seq", actions=actions)
    
    compiler = Compiler(config)
    protocol = compiler.compile(seq)
    
    # Analyze generated steps
    # 1. Move to loc_A: Start (0,0,0) -> Safe Z (-5). 0 > -5 so NO Lift.
    #    Travel (x, y, 0). Lower (x, y, -10). -> 2 steps.
    # 2. Capture Image: Already at target. -> 1 step.
    # 3. Move to home: Start (-10,-10,-10). < -5. Lift. Travel. Lower. -> 3 steps.
    # Total 6 steps
    assert len(protocol.steps) == 6
    
    # Check Step Types
    assert protocol.steps[0].type == "move"
    # Image step is after 2 moves -> index 2
    assert protocol.steps[2].type == "image"
    assert protocol.steps[2].parameters["label"] == "test_img"
    # Last move step is index 5
    assert protocol.steps[5].type == "move"
    # Last move should be to home (0,0,0)
    assert protocol.steps[5].parameters["x"] == 0
    assert protocol.steps[5].parameters["y"] == 0
    assert protocol.steps[5].parameters["z"] == 0

def test_compiler_unknown_location():
    """Test error when referencing unknown location."""
    bounds = MachineBounds(x_min=-100, x_max=0, y_min=-100, y_max=0, z_min=-50, z_max=0)
    config = DeckConfig(machine_bounds=bounds, safe_z_height=-5, locations={}) # Empty locations
    
    seq = ExperimentSequence(name="Fail", actions=[MoveAction(target_location="nowhere")])
    compiler = Compiler(config)
    
    with pytest.raises(ValueError, match="Unknown location"):
        compiler.compile(seq)

# Camera Tests
from unittest.mock import MagicMock, patch
from src.protocol_engine.camera import Camera

@patch("src.protocol_engine.camera.cv2")
def test_camera_capture(mock_cv2, tmp_path):
    """Test camera capture calls cv2 correctly."""
    # Mock capture object
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, "fake_frame_data")
    mock_cv2.VideoCapture.return_value = mock_cap
    
    camera = Camera(source=0)
    
    # Verify open
    mock_cv2.VideoCapture.assert_called_with(0)
    
    # Capture
    filename = tmp_path / "test_image.jpg"
    camera.capture_image(str(filename))
    
    # Verify read and write
    mock_cap.read.assert_called()
    mock_cv2.imwrite.assert_called_with(str(filename), "fake_frame_data")
    
    # Close
    camera.close()
    mock_cap.release.assert_called()

# Executor Tests
from src.protocol_engine.executor import ProtocolExecutor
from src.protocol_engine.compiler import CompiledProtocol, ProtocolStep

def test_executor_execute():
    """Test executing a compiled protocol."""
    # Mock Mill and Camera
    mock_mill = MagicMock()
    mock_camera = MagicMock()
    
    # Create a simple protocol
    steps = [
        ProtocolStep(type="move", parameters={"x": 10, "y": 20, "z": -5}),
        ProtocolStep(type="image", parameters={"location": "loc_A", "label": "test_img"}),
        ProtocolStep(type="move", parameters={"x": 0, "y": 0, "z": 0})
    ]
    protocol = CompiledProtocol(steps=steps)
    
    executor = ProtocolExecutor(mill=mock_mill, camera=mock_camera)
    executor.execute(protocol)
    
    # Verify calls
    assert mock_mill.move_to_position.call_count == 2
    mock_mill.move_to_position.assert_any_call(x_coordinate=10, y_coordinate=20, z_coordinate=-5)
    mock_mill.move_to_position.assert_any_call(x_coordinate=0, y_coordinate=0, z_coordinate=0)
    
    mock_camera.capture_image.assert_called_once()
    # Check that filename was generated
    args, _ = mock_camera.capture_image.call_args
    assert "test_img" in args[0]
    assert "loc_A" in args[0]
    assert args[0].endswith(".jpg")

