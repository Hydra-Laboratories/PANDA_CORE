from abc import ABC, abstractmethod
from typing import Optional, Any
import logging

# Configure logger for core instruments if not already configured
logger = logging.getLogger(__name__)

class InstrumentError(Exception):
    """Base exception for all instrument errors."""
    pass

class BaseInstrument(ABC):
    """
    Abstract base class for all instruments in the CNC/Lab Automation project.
    Enforces a standard interface for connection, disconnection, and health checks.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        depth: float = 0.0,
    ):
        self.name = name or self.__class__.__name__
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.depth = depth
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    @abstractmethod
    def connect(self) -> None:
        """
        Establish a connection to the instrument.
        Must raise InstrumentError if connection fails.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Safely disconnect from the instrument.
        Must handle cases where the instrument is already disconnected.
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if the instrument is healthy and ready for operation.
        Returns True if healthy, False otherwise.
        """
        pass

    def warm_up(self) -> None:
        """
        Optional warmup routine (e.g., homing, heating, self-test).
        """
        pass

    def calibrate(self) -> None:
        """
        Optional calibration routine.
        """
        pass

    def handle_error(self, error: Exception, context: str = "") -> None:
        """
        Generic error handler. Logs the error and re-raises as InstrumentError
        if it's not already one.
        
        Args:
            error: The caught exception.
            context: Contextual message describing where the error occurred.
        """
        msg = f"Error in {self.name}{f' ({context})' if context else ''}: {str(error)}"
        self.logger.error(msg)
        if isinstance(error, InstrumentError):
            raise error
        raise InstrumentError(msg) from error
