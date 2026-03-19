from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CureResult:
    """Result of a single UV curing exposure."""

    well_id: str
    intensity_percent: float
    exposure_time_s: float
    z_mm: float
    timestamp: float

    @property
    def is_valid(self) -> bool:
        return (
            self.intensity_percent > 0
            and self.exposure_time_s > 0
        )


@dataclass(frozen=True)
class UVCuringStatus:
    """Snapshot of UV curing system state."""

    is_connected: bool
    led_on: bool
    current_intensity: Optional[float]
