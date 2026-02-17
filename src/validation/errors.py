"""Validation error types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class BoundsViolation:
    """One position that falls outside the gantry working volume."""

    labware_key: str
    position_id: str
    instrument_name: Optional[str]
    coordinate_type: str
    x: float
    y: float
    z: float
    axis: str
    bound_name: str
    bound_value: float


class SetupValidationError(Exception):
    """Raised when protocol setup validation detects bounds violations."""

    def __init__(self, violations: List[BoundsViolation]) -> None:
        self.violations = violations
        messages = []
        for v in violations:
            instr_prefix = f"instrument '{v.instrument_name}' at " if v.instrument_name else ""
            messages.append(
                f"  {v.coordinate_type} position ({v.x}, {v.y}, {v.z}) for "
                f"{instr_prefix}{v.labware_key}.{v.position_id} "
                f"violates {v.bound_name}={v.bound_value}"
            )
        super().__init__(
            f"Bounds validation failed with {len(violations)} violation(s):\n"
            + "\n".join(messages)
        )
