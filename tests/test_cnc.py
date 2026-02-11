import pytest
from unittest.mock import MagicMock, patch
from src.core.base_instrument import InstrumentError

# Assumed import path
try:
    from src.core.instruments.cnc import CNC
except ImportError:
    CNC = None

@pytest.fixture
def mock_mill():
    with patch("src.core.instruments.cnc.Mill") as MockMill:
        yield MockMill.return_value

def test_initialization(mock_mill):
    if CNC is None:
        pytest.fail("CNC not implemented")
    driver = CNC() # No config
    assert driver._mill is mock_mill
    assert driver.config == {}

def test_connect_explicit_cnc_config(mock_mill):
    """Test connection using nested cnc.serial_port config."""
    if CNC is None:
        pytest.fail("CNC not implemented")
        
    config = {"cnc": {"serial_port": "/dev/nested_port"}}
    driver = CNC(config=config)
    driver.connect()
    
    mock_mill.connect_to_mill.assert_called_with(port="/dev/nested_port")

def test_connect_legacy_config(mock_mill):
    """Test connection using top-level serial_port (backward compatibility)."""
    if CNC is None:
        pytest.fail("CNC not implemented")
        
    config = {"serial_port": "/dev/top_level_port"}
    driver = CNC(config=config)
    driver.connect()
    
    mock_mill.connect_to_mill.assert_called_with(port="/dev/top_level_port")

def test_connect_auto_scan(mock_mill):
    """Test fallback to auto-scan if no port in config."""
    if CNC is None:
        pytest.fail("CNC not implemented")
        
    config = {"other_setting": "value"}
    driver = CNC(config=config)
    driver.connect()
    
    # Should call with None to trigger auto-scan logic in Mill
    mock_mill.connect_to_mill.assert_called_with(port=None)

def test_disconnect(mock_mill):
    if CNC is None:
        pytest.fail("CNC not implemented")
    driver = CNC()
    driver.disconnect()
    mock_mill.disconnect.assert_called_once()

def test_health_check_healthy(mock_mill):
    if CNC is None:
        pytest.fail("CNC not implemented")
    driver = CNC()
    mock_mill.active_connection = True
    mock_mill.current_status.return_value = "Idle"
    assert driver.health_check() is True

def test_home_delegation(mock_mill):
    if CNC is None:
        pytest.fail("CNC not implemented")
    driver = CNC()
    driver.home()
    mock_mill.home.assert_called_once()

def test_move_delegation(mock_mill):
    if CNC is None:
        pytest.fail("CNC not implemented")
    driver = CNC()
    driver.move_to(x=10, y=20, z=-5)
    mock_mill.safe_move.assert_called_with(x_coord=10, y_coord=20, z_coord=-5)
