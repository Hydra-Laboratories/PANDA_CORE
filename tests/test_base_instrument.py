import pytest
from src.core.base_instrument import BaseInstrument, InstrumentError

# Mock concrete implementation for testing
class MockInstrument(BaseInstrument):
    def __init__(self, name="mock_instrument"):
        super().__init__(name)
        self.connected = False
        self.healthy = True

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False

    def health_check(self):
        return self.healthy

class BadInstrument(BaseInstrument):
    """Missing abstract methods to test ABC enforcement"""
    pass

def test_cannot_instantiate_abc():
    """Ensure BaseInstrument cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseInstrument()

def test_cannot_instantiate_incomplete_subclass():
    """Ensure subclasses must implement all abstract methods."""
    with pytest.raises(TypeError):
        BadInstrument()

def test_concrete_implementation():
    """Test a valid concrete implementation."""
    instr = MockInstrument()
    assert instr.name == "mock_instrument"
    
    # Test lifecycle methods
    instr.connect()
    assert instr.connected is True
    
    instr.disconnect()
    assert instr.connected is False
    
    assert instr.health_check() is True

def test_handle_error_wraps_exception():
    """Test that handle_error wraps arbitrary exceptions in InstrumentError."""
    instr = MockInstrument()
    original_error = ValueError("Something went wrong")
    
    with pytest.raises(InstrumentError) as exc_info:
        instr.handle_error(original_error, "testing context")
    
    assert "Something went wrong" in str(exc_info.value)
    assert "testing context" in str(exc_info.value)
    assert exc_info.value.__cause__ is original_error

def test_handle_error_passes_through_instrument_error():
    """Test that handle_error re-raises InstrumentError without wrapping it again."""
    instr = MockInstrument()
    original_error = InstrumentError("Already an instrument error")
    
    with pytest.raises(InstrumentError) as exc_info:
        instr.handle_error(original_error, "processing")
        
    assert exc_info.value is original_error
