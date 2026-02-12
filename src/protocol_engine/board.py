import logging
from typing import Any, Optional, Union

from src.gantry import Gantry
from src.instruments.base_instrument import BaseInstrument
from src.instruments.pipette.exceptions import PipetteError
from src.instruments.pipette.models import AspirateResult, MixResult

# A position is either a (x, y, z) tuple or any object with x, y, z attributes
# (e.g. a labware object sitting at a fixed deck location).
Position = Union[tuple[float, float, float], Any]


class Board:
    """Physical board layout: a gantry and the instruments mounted on it.

    Holds a single Gantry instance and a dictionary of named instruments.
    Each instrument's offset_x, offset_y, and depth describe its position
    relative to the router so the board can calculate absolute positions.
    """

    def __init__(
        self,
        gantry: Gantry,
        instruments: Optional[dict[str, BaseInstrument]] = None,
    ):
        self.gantry = gantry
        self.instruments: dict[str, BaseInstrument] = instruments or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # ── Helper methods ────────────────────────────────────────────────────

    def move(
        self,
        instrument: Union[str, BaseInstrument],
        position: Position,
    ) -> None:
        """Move the gantry so that *instrument* arrives at *position*.

        Accounts for the instrument's offset_x, offset_y, and depth so the
        gantry head ends up at the right place for the instrument tip to be
        at the requested (x, y, z).

        Args:
            instrument: Name (key in ``self.instruments``) or instance.
            position:   (x, y, z) tuple or labware object with x, y, z attrs.
        """
        instr = self._resolve_instrument(instrument)
        x, y, z = self._resolve_position(position)
        gantry_x = x - instr.offset_x
        gantry_y = y - instr.offset_y
        gantry_z = z - instr.depth
        self.logger.info(
            "Moving %s to (%.3f, %.3f, %.3f) → gantry (%.3f, %.3f, %.3f)",
            instr.name, x, y, z, gantry_x, gantry_y, gantry_z,
        )
        self.gantry.move_to(gantry_x, gantry_y, gantry_z)

    def object_position(
        self, obj: Union[str, BaseInstrument, Any],
    ) -> tuple[float, float]:
        """Return the current (x, y) position of an object on the board.

        For instruments (str key or BaseInstrument): computes position from
        the current gantry coordinates plus the instrument's offset.

        For labware or other objects: reads ``obj.x`` and ``obj.y`` directly
        (the object is assumed to have a fixed deck position).

        Args:
            obj: Instrument name, BaseInstrument instance, or any object
                 with ``x`` and ``y`` attributes.

        Returns:
            (x, y) tuple of the object's current position.
        """
        if isinstance(obj, str):
            obj = self._resolve_instrument(obj)

        if isinstance(obj, BaseInstrument):
            coords = self.gantry.get_coordinates()
            return (
                coords["x"] + obj.offset_x,
                coords["y"] + obj.offset_y,
            )

        return (obj.x, obj.y)

    # ── Pipette helpers ─────────────────────────────────────────────────

    def aspirate(
        self,
        position: Position,
        volume_ul: float,
        speed: float = 50.0,
    ) -> AspirateResult:
        """Move pipette to *position*, then aspirate."""
        pipette = self._require_pipette()
        self.move(pipette, position)
        return pipette.aspirate(volume_ul, speed)

    def dispense(
        self,
        position: Position,
        volume_ul: float,
        speed: float = 50.0,
    ) -> AspirateResult:
        """Move pipette to *position*, then dispense."""
        pipette = self._require_pipette()
        self.move(pipette, position)
        return pipette.dispense(volume_ul, speed)

    def blowout(
        self,
        position: Position,
        speed: float = 50.0,
    ) -> None:
        """Move pipette to *position*, then blowout."""
        pipette = self._require_pipette()
        self.move(pipette, position)
        pipette.blowout(speed)

    def mix(
        self,
        position: Position,
        volume_ul: float,
        repetitions: int = 3,
        speed: float = 50.0,
    ) -> MixResult:
        """Move pipette to *position*, then mix."""
        pipette = self._require_pipette()
        self.move(pipette, position)
        return pipette.mix(volume_ul, repetitions, speed)

    def pick_up_tip(
        self,
        position: Position,
        speed: float = 50.0,
    ) -> None:
        """Move pipette to *position*, then pick up a tip."""
        pipette = self._require_pipette()
        self.move(pipette, position)
        pipette.pick_up_tip(speed)

    def drop_tip(
        self,
        position: Position,
        speed: float = 50.0,
    ) -> None:
        """Move pipette to *position*, then drop the tip."""
        pipette = self._require_pipette()
        self.move(pipette, position)
        pipette.drop_tip(speed)

    # ── Private helpers ───────────────────────────────────────────────────

    def _require_pipette(self) -> BaseInstrument:
        """Return the pipette instrument or raise PipetteError."""
        if "pipette" not in self.instruments:
            raise PipetteError(
                "No pipette registered on this board. "
                "Add one via Board(instruments={'pipette': ...})"
            )
        return self.instruments["pipette"]

    def _resolve_instrument(
        self, instrument: Union[str, BaseInstrument],
    ) -> BaseInstrument:
        """Look up an instrument by name or return it directly."""
        if isinstance(instrument, str):
            if instrument not in self.instruments:
                raise KeyError(
                    f"Unknown instrument '{instrument}'. "
                    f"Available: {', '.join(sorted(self.instruments.keys()))}"
                )
            return self.instruments[instrument]
        return instrument

    @staticmethod
    def _resolve_position(position: Position) -> tuple[float, float, float]:
        """Convert a position tuple or labware object to (x, y, z)."""
        if isinstance(position, tuple):
            return position
        return (position.x, position.y, position.z)
