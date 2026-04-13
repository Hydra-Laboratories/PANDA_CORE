from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from instruments.base_instrument import BaseInstrument

if TYPE_CHECKING:
    from gantry import Gantry

# A position is either an (x, y, z) tuple or any object with x, y, z attributes
# (e.g. a labware object sitting at a fixed deck location).
Position = Any


class Board:
    """Physical board layout: a gantry and the instruments mounted on it.

    Holds a single Gantry instance and a dictionary of named instruments.
    Each instrument's offset_x, offset_y, and depth describe its position
    relative to the router so the board can calculate absolute positions
    in user-facing positive coordinates.
    """

    def __init__(
        self,
        gantry: Gantry,
        instruments: dict[str, BaseInstrument] | None = None,
    ):
        self.gantry = gantry
        self.instruments: dict[str, BaseInstrument] = instruments or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def move(
        self,
        instrument: str | BaseInstrument,
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

    def move_to_labware(
        self,
        instrument: str | BaseInstrument,
        position: Position,
    ) -> None:
        """Safely move *instrument* to a labware *position*, applying the
        instrument's Z offsets.

        Two-step sequence:
          1. Travel to (x, y, labware_z + safe_approach_height) — keeps the
             instrument above labware during XY motion.
          2. Lower to (x, y, labware_z + measurement_height) — the final
             action position (touch / dip / probe clearance).

        If safe_approach_height equals measurement_height (the default for
        non-contact instruments), the second step is skipped.

        Args:
            instrument: Name or instance.
            position:   (x, y, z) or labware object whose z is the labware
                        reference point (e.g. well bottom, vial bottom,
                        tip engagement Z).
        """
        instr = self._resolve_instrument(instrument)
        x, y, z = self._resolve_position(position)
        approach_z = z + instr.safe_approach_height
        action_z = z + instr.measurement_height
        self.move(instr, (x, y, approach_z))
        if abs(approach_z - action_z) > 1e-9:
            self.move(instr, (x, y, action_z))

    def object_position(
        self, obj: str | BaseInstrument | Any,
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

    # ── Instrument lifecycle ─────────────────────────────────────────────

    def connect_instruments(self) -> None:
        """Connect all instruments on the board."""
        for name, instrument in self.instruments.items():
            self.logger.info("Connecting instrument: %s", name)
            instrument.connect()

    def disconnect_instruments(self) -> None:
        """Disconnect all instruments, logging errors without re-raising.

        Ensures every instrument gets a disconnect attempt even if one fails.
        """
        for name, instrument in self.instruments.items():
            try:
                self.logger.info("Disconnecting instrument: %s", name)
                instrument.disconnect()
            except Exception:
                self.logger.exception(
                    "Failed to disconnect instrument '%s'", name,
                )

    # ── Private helpers ───────────────────────────────────────────────────

    def _resolve_instrument(
        self, instrument: str | BaseInstrument,
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
