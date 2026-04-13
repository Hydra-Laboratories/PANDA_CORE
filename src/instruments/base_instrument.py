from abc import ABC, abstractmethod
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

class InstrumentError(Exception):
    """Base exception for all instrument errors."""
    pass

class BaseInstrument(ABC):
    """Abstract base class for all instruments.

    All instruments accept an ``offline`` flag. When True, connect/disconnect
    are no-ops, health_check returns True, and instrument-specific methods
    return synthetic data without touching hardware.

    Z-offset convention
    -------------------
    * ``measurement_height`` — Z offset from the labware reference point
      when the instrument is taking its measurement/action. Positive =
      above, negative = below. Non-contact instruments (uvvis, filmetrics,
      uv_curing) use a small positive value (probe clearance). Contact
      instruments (pipette, asmi, potentiostat) use 0 (touch) or negative
      (dip into the sample).
    * ``safe_approach_height`` — Z offset from the labware reference point
      while traveling toward a target. Always >= ``measurement_height``
      so the instrument never drags through labware during XY motion.
      Defaults to ``measurement_height`` (correct for non-contact tools);
      contact instruments should set a positive value explicitly.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        depth: float = 0.0,
        measurement_height: float = 0.0,
        safe_approach_height: Optional[float] = None,
        offline: bool = False,
    ):
        self.name = name or self.__class__.__name__
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.depth = depth
        self.measurement_height = measurement_height
        self.safe_approach_height = (
            safe_approach_height if safe_approach_height is not None else measurement_height
        )
        self._offline = offline
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def health_check(self) -> bool:
        pass

    def warm_up(self) -> None:
        pass

    def calibrate(self) -> None:
        pass

    def handle_error(self, error: Exception, context: str = "") -> None:
        msg = f"Error in {self.name}{f' ({context})' if context else ''}: {str(error)}"
        self.logger.error(msg)
        if isinstance(error, InstrumentError):
            raise error
        raise InstrumentError(msg) from error
