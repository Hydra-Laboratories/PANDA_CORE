"""Parameter and result dataclasses for SquidStat experiments.

All dataclasses are frozen. Param types validate in ``__post_init__`` and raise
:class:`PotentiostatConfigError` on bad input. Result types carry numpy arrays
and a ``metadata`` mapping with run-level info (model, channel, timestamps,
aborted flag).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np

from instruments.potentiostat.exceptions import PotentiostatConfigError


# ── Param types ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CVParams:
    """Cyclic voltammetry sweep parameters.

    The sweep goes start_V → vertex1_V → vertex2_V → end_V and repeats for
    ``cycles`` passes. ``scan_rate_V_per_s`` controls ramp speed;
    ``sampling_interval_s`` controls how often data is recorded.
    """

    start_V: float
    vertex1_V: float
    vertex2_V: float
    end_V: float
    scan_rate_V_per_s: float
    cycles: int = 1
    sampling_interval_s: float = 0.01

    def __post_init__(self) -> None:
        if self.scan_rate_V_per_s <= 0:
            raise PotentiostatConfigError(
                f"scan_rate_V_per_s must be > 0, got {self.scan_rate_V_per_s}"
            )
        if self.cycles < 1:
            raise PotentiostatConfigError(
                f"cycles must be >= 1, got {self.cycles}"
            )
        if self.sampling_interval_s <= 0:
            raise PotentiostatConfigError(
                f"sampling_interval_s must be > 0, got {self.sampling_interval_s}"
            )
        if self.vertex1_V == self.vertex2_V:
            raise PotentiostatConfigError(
                "vertex1_V and vertex2_V must differ to define a sweep"
            )


@dataclass(frozen=True)
class OCPParams:
    """Open-circuit potential measurement parameters."""

    duration_s: float
    sampling_interval_s: float = 0.1

    def __post_init__(self) -> None:
        if self.duration_s <= 0:
            raise PotentiostatConfigError(
                f"duration_s must be > 0, got {self.duration_s}"
            )
        if self.sampling_interval_s <= 0:
            raise PotentiostatConfigError(
                f"sampling_interval_s must be > 0, got {self.sampling_interval_s}"
            )
        if self.sampling_interval_s > self.duration_s:
            raise PotentiostatConfigError(
                "sampling_interval_s must be <= duration_s"
            )


@dataclass(frozen=True)
class CAParams:
    """Chronoamperometry (constant applied potential) parameters."""

    potential_V: float
    duration_s: float
    sampling_interval_s: float = 0.01

    def __post_init__(self) -> None:
        if self.duration_s <= 0:
            raise PotentiostatConfigError(
                f"duration_s must be > 0, got {self.duration_s}"
            )
        if self.sampling_interval_s <= 0:
            raise PotentiostatConfigError(
                f"sampling_interval_s must be > 0, got {self.sampling_interval_s}"
            )
        if self.sampling_interval_s > self.duration_s:
            raise PotentiostatConfigError(
                "sampling_interval_s must be <= duration_s"
            )


@dataclass(frozen=True)
class CPParams:
    """Chronopotentiometry (constant applied current) parameters."""

    current_A: float
    duration_s: float
    sampling_interval_s: float = 0.01

    def __post_init__(self) -> None:
        if self.duration_s <= 0:
            raise PotentiostatConfigError(
                f"duration_s must be > 0, got {self.duration_s}"
            )
        if self.sampling_interval_s <= 0:
            raise PotentiostatConfigError(
                f"sampling_interval_s must be > 0, got {self.sampling_interval_s}"
            )
        if self.sampling_interval_s > self.duration_s:
            raise PotentiostatConfigError(
                "sampling_interval_s must be <= duration_s"
            )


# ── Result types ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CVResult:
    potentials_V: np.ndarray
    currents_A: np.ndarray
    timestamps_s: np.ndarray
    cycle_index: np.ndarray
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OCPResult:
    potentials_V: np.ndarray
    timestamps_s: np.ndarray
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CAResult:
    currents_A: np.ndarray
    potentials_V: np.ndarray
    timestamps_s: np.ndarray
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CPResult:
    currents_A: np.ndarray
    potentials_V: np.ndarray
    timestamps_s: np.ndarray
    metadata: Mapping[str, Any] = field(default_factory=dict)
