"""In-memory volume state tracker for labware during protocol execution."""

from __future__ import annotations

import math
from typing import Optional

from deck.labware.vial import Vial
from deck.labware.well_plate import WellPlate
from protocol_engine.errors import (
    InvalidVolumeError,
    OverflowVolumeError,
    PipetteVolumeError,
    UnderflowVolumeError,
)


class VolumeTracker:
    """Track current volumes for every registered labware location.

    Validates aspirate and dispense operations against capacity and
    available volume.  Operates entirely in-memory with O(1) lookups.
    """

    def __init__(self) -> None:
        self._volumes: dict[tuple[str, Optional[str]], float] = {}
        self._capacities: dict[tuple[str, Optional[str]], float] = {}

    # ── Registration ─────────────────────────────────────────────────────

    def register_labware(
        self,
        labware_key: str,
        labware: WellPlate | Vial,
        *,
        initial_volume_ul: float = 0.0,
        initial_volumes: dict[str, float] | None = None,
    ) -> None:
        """Register a labware item for volume tracking.

        For a WellPlate, one entry per well is created.
        For a Vial, a single entry (well_id=None) is created.

        Args:
            labware_key: Unique key matching the deck labware key.
            labware: The WellPlate or Vial model instance.
            initial_volume_ul: Starting volume for vials (ignored for plates).
            initial_volumes: Per-well starting volumes for plates (optional).
        """
        if any(k == labware_key for k, _ in self._volumes):
            raise ValueError(f"Labware '{labware_key}' already registered.")

        if isinstance(labware, WellPlate):
            self._register_well_plate(labware_key, labware, initial_volumes)
        elif isinstance(labware, Vial):
            self._register_vial(labware_key, labware, initial_volume_ul)
        else:
            raise TypeError(
                f"Unsupported labware type: {type(labware).__name__}"
            )

    def _register_vial(
        self, key: str, vial: Vial, initial_volume_ul: float,
    ) -> None:
        if initial_volume_ul < 0:
            raise ValueError("initial_volume_ul must be non-negative.")
        if initial_volume_ul > vial.capacity_ul:
            raise ValueError(
                f"initial_volume_ul ({initial_volume_ul}) exceeds capacity "
                f"({vial.capacity_ul})."
            )
        self._volumes[(key, None)] = initial_volume_ul
        self._capacities[(key, None)] = vial.capacity_ul

    def _register_well_plate(
        self,
        key: str,
        plate: WellPlate,
        initial_volumes: dict[str, float] | None,
    ) -> None:
        initial_volumes = initial_volumes or {}
        for well_id in plate.wells:
            vol = initial_volumes.get(well_id, 0.0)
            if vol < 0:
                raise ValueError(
                    f"Initial volume for {key}.{well_id} must be non-negative."
                )
            if vol > plate.capacity_ul:
                raise ValueError(
                    f"Initial volume for {key}.{well_id} ({vol}) exceeds capacity "
                    f"({plate.capacity_ul})."
                )
            self._volumes[(key, well_id)] = vol
            self._capacities[(key, well_id)] = plate.capacity_ul

    # ── Queries ──────────────────────────────────────────────────────────

    def get_volume(
        self, labware_key: str, well_id: Optional[str] = None,
    ) -> float:
        """Return the current volume at a labware location."""
        loc = (labware_key, well_id)
        if loc not in self._volumes:
            raise KeyError(
                f"Location '{labware_key}' well '{well_id}' not registered."
            )
        return self._volumes[loc]

    def get_capacity(
        self, labware_key: str, well_id: Optional[str] = None,
    ) -> float:
        """Return the total capacity at a labware location."""
        loc = (labware_key, well_id)
        if loc not in self._capacities:
            raise KeyError(
                f"Location '{labware_key}' well '{well_id}' not registered."
            )
        return self._capacities[loc]

    def get_available_capacity(
        self, labware_key: str, well_id: Optional[str] = None,
    ) -> float:
        """Return remaining capacity at a labware location."""
        return self.get_capacity(labware_key, well_id) - self.get_volume(
            labware_key, well_id
        )

    # ── Validation ───────────────────────────────────────────────────────

    def validate_aspirate(
        self, labware_key: str, well_id: Optional[str], volume_ul: float,
    ) -> None:
        """Raise if aspirating *volume_ul* would underflow."""
        _validate_volume_value(volume_ul)
        current = self.get_volume(labware_key, well_id)
        if volume_ul > current:
            raise UnderflowVolumeError(
                labware_key, well_id, current, volume_ul,
            )

    def validate_dispense(
        self, labware_key: str, well_id: Optional[str], volume_ul: float,
    ) -> None:
        """Raise if dispensing *volume_ul* would overflow."""
        _validate_volume_value(volume_ul)
        current = self.get_volume(labware_key, well_id)
        capacity = self.get_capacity(labware_key, well_id)
        if current + volume_ul > capacity:
            raise OverflowVolumeError(
                labware_key, well_id, current, volume_ul, capacity,
            )

    # ── Record (validate + mutate) ───────────────────────────────────────

    def record_aspirate(
        self, labware_key: str, well_id: Optional[str], volume_ul: float,
    ) -> None:
        """Validate and record an aspirate (decreases volume)."""
        self.validate_aspirate(labware_key, well_id, volume_ul)
        self._volumes[(labware_key, well_id)] -= volume_ul

    def record_dispense(
        self, labware_key: str, well_id: Optional[str], volume_ul: float,
    ) -> None:
        """Validate and record a dispense (increases volume)."""
        self.validate_dispense(labware_key, well_id, volume_ul)
        self._volumes[(labware_key, well_id)] += volume_ul

    # ── Pipette range validation ─────────────────────────────────────────

    @staticmethod
    def validate_pipette_volume(
        volume_ul: float, *, min_ul: float, max_ul: float,
    ) -> None:
        """Raise if *volume_ul* is outside the pipette's [min, max] range."""
        _validate_volume_value(volume_ul)
        if volume_ul < min_ul or volume_ul > max_ul:
            raise PipetteVolumeError(volume_ul, min_ul, max_ul)


def _validate_volume_value(volume_ul: float) -> None:
    """Raise InvalidVolumeError for non-finite or non-positive volumes."""
    if not math.isfinite(volume_ul):
        raise InvalidVolumeError(
            f"Volume must be finite, got {volume_ul}"
        )
    if volume_ul <= 0:
        raise InvalidVolumeError(
            f"Volume must be positive, got {volume_ul}"
        )
