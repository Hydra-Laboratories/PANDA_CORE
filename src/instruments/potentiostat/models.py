from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PotentiostatStatus:
    """Snapshot of potentiostat connection state."""

    is_connected: bool
    vendor: str
    backend_name: str

    @property
    def is_valid(self) -> bool:
        return self.is_connected and bool(self.vendor) and bool(self.backend_name)


@dataclass(frozen=True)
class OCPResult:
    """Open-circuit potential trace."""

    time_s: tuple[float, ...]
    voltage_v: tuple[float, ...]
    sample_period_s: float
    duration_s: float
    vendor: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def technique(self) -> str:
        return "ocp"

    @property
    def final_voltage_v(self) -> float | None:
        return self.voltage_v[-1] if self.voltage_v else None

    @property
    def is_valid(self) -> bool:
        return (
            len(self.time_s) > 0
            and len(self.time_s) == len(self.voltage_v)
            and self.sample_period_s > 0
            and self.duration_s > 0
        )


@dataclass(frozen=True)
class ChronoAmperometryResult:
    """Chronoamperometry trace."""

    time_s: tuple[float, ...]
    current_a: tuple[float, ...]
    voltage_v: tuple[float, ...]
    sample_period_s: float
    duration_s: float
    step_potential_v: float
    vendor: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def technique(self) -> str:
        return "ca"

    @property
    def is_valid(self) -> bool:
        return (
            len(self.time_s) > 0
            and len(self.time_s) == len(self.current_a)
            and len(self.time_s) == len(self.voltage_v)
            and self.sample_period_s > 0
            and self.duration_s > 0
        )


@dataclass(frozen=True)
class CyclicVoltammetryResult:
    """Cyclic voltammetry trace."""

    time_s: tuple[float, ...]
    voltage_v: tuple[float, ...]
    current_a: tuple[float, ...]
    scan_rate_v_s: float
    step_size_v: float
    cycles: int
    vendor: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def technique(self) -> str:
        return "cv"

    @property
    def is_valid(self) -> bool:
        return (
            len(self.time_s) > 0
            and len(self.time_s) == len(self.current_a)
            and len(self.time_s) == len(self.voltage_v)
            and self.scan_rate_v_s > 0
            and self.step_size_v > 0
            and self.cycles >= 1
        )
