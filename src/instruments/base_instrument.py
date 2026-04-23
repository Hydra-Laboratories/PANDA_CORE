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
    User-space Z is positive-down in this system: z=0 at the gantry's home
    position (top of travel), larger z moves closer to the deck. Both
    offsets below are signed heights ABOVE the labware reference z:
    Board/commands subtract the offset from the labware z to get the
    tip's target z. Bigger offset = smaller z = higher above the labware.

    * ``measurement_height`` — signed offset above the labware reference
      during the measurement/action. Positive = above the reference
      (tip held over the sample); negative = below (tip dipped into the
      sample). Non-contact instruments (uvvis, filmetrics, uv_curing) use
      a small positive value for probe clearance. Contact instruments
      (pipette, asmi, potentiostat) use 0 (touch) or negative (dip).
      Applied by each *engaging* command (measure/scan/aspirate/etc.)
      when it descends after approach.
    * ``safe_approach_height`` — signed offset above the labware reference
      during XY travel. Must be >= ``measurement_height`` (enforced in
      __init__) so the instrument never travels *lower* than its own
      action height. Defaults to ``measurement_height`` (correct for
      non-contact tools); contact instruments should set a larger positive
      value explicitly. Applied by ``Board.move_to_labware``.
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
                f"{self.__class__.__name__}. Board.move_to_labware travels "
                f"XY at safe_approach_height and then descends to "
                f"measurement_height; if the travel height sits below the "
                f"action height, that 'descent' would lift the instrument "
                f"instead — defeating the approach-above-then-descend contract."
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
