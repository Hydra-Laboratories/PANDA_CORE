"""Protocol engine exception types."""

from __future__ import annotations


class ProtocolLoaderError(Exception):
    """Human-friendly protocol loader error intended for CLI output."""


class ProtocolExecutionError(Exception):
    """Error raised during protocol step execution."""


# ── Volume errors ────────────────────────────────────────────────────────────


class VolumeError(ProtocolExecutionError):
    """Base class for volume-related protocol errors."""


class OverflowVolumeError(VolumeError):
    """Dispensing would exceed labware capacity."""

    def __init__(
        self,
        labware_key: str,
        well_id: str | None,
        current_volume_ul: float,
        requested_ul: float,
        capacity_ul: float,
    ) -> None:
        self.labware_key = labware_key
        self.well_id = well_id
        self.current_volume_ul = current_volume_ul
        self.requested_ul = requested_ul
        self.capacity_ul = capacity_ul
        loc = f"{labware_key}.{well_id}" if well_id else labware_key
        excess = current_volume_ul + requested_ul - capacity_ul
        super().__init__(
            f"Overflow: dispensing {requested_ul} uL into {loc} "
            f"(current={current_volume_ul}, capacity={capacity_ul}) "
            f"would exceed capacity by {excess:.2f} uL"
        )


class UnderflowVolumeError(VolumeError):
    """Aspirating would draw more than available volume."""

    def __init__(
        self,
        labware_key: str,
        well_id: str | None,
        current_volume_ul: float,
        requested_ul: float,
    ) -> None:
        self.labware_key = labware_key
        self.well_id = well_id
        self.current_volume_ul = current_volume_ul
        self.requested_ul = requested_ul
        loc = f"{labware_key}.{well_id}" if well_id else labware_key
        deficit = requested_ul - current_volume_ul
        super().__init__(
            f"Underflow: aspirating {requested_ul} uL from {loc} "
            f"(current={current_volume_ul}) — insufficient volume by "
            f"{deficit:.2f} uL"
        )


class InvalidVolumeError(VolumeError):
    """Volume value is invalid (negative, zero, NaN, or infinity)."""


class PipetteVolumeError(VolumeError):
    """Requested volume is outside the pipette's min/max range."""

    def __init__(
        self,
        requested_ul: float,
        min_ul: float,
        max_ul: float,
    ) -> None:
        self.requested_ul = requested_ul
        self.min_ul = min_ul
        self.max_ul = max_ul
        super().__init__(
            f"Pipette volume {requested_ul} uL is outside valid range "
            f"[{min_ul}, {max_ul}] uL"
        )
