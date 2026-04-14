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
    Coordinates use the gantry's user-space convention: larger Z = further
    above the deck (away from labware surfaces). Both offsets are added to
    the labware reference z by ``Board.move_to_labware``.

    * ``measurement_height`` — signed Z offset from the labware reference
      during the measurement/action. Positive = above the reference;
      negative = below. Non-contact instruments (uvvis, filmetrics,
      uv_curing) use a small positive value (probe clearance above sample).
      Contact instruments (pipette, asmi, potentiostat) use 0 (touch) or
      negative (dip into the sample).
    * ``safe_approach_height`` — signed Z offset during XY travel. Must
      be >= ``measurement_height`` (enforced in __init__) so the
      instrument never travels *below* its own action Z. Defaults to
      ``measurement_height`` (correct for non-contact tools); contact
      instruments should set a larger positive value explicitly.
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
        resolved_safe = (
            safe_approach_height if safe_approach_height is not None else measurement_height
        )
        if resolved_safe < measurement_height:
            raise ValueError(
                f"safe_approach_height ({resolved_safe}) must be >= "
                f"measurement_height ({measurement_height}) for "
                f"{self.__class__.__name__}. Otherwise Board.move_to_labware "
                f"would travel XY below the action Z and the 'lower' step "
                f"would move the instrument upward — defeating the retract-"
                f"travel-lower safety guarantee."
            )
        self.name = name or self.__class__.__name__
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.depth = depth
        self.measurement_height = measurement_height
        self.safe_approach_height = resolved_safe
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
