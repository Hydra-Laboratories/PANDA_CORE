"""Validation error types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Tuple


@dataclass(frozen=True)
class BoundsViolation:
    """One position that falls outside the gantry working volume."""

    labware_key: str
    position_id: str
    instrument_name: Optional[str]
    coordinate_type: Literal["deck", "gantry"]
    x: float
    y: float
    z: float
    axis: Literal["x", "y", "z"]
    bound_name: str
    bound_value: float


class SetupValidationError(Exception):
    """Raised when protocol setup validation detects bounds violations."""

    def __init__(self, violations: list[BoundsViolation]) -> None:
        self.violations: Tuple[BoundsViolation, ...] = tuple(violations)
        messages = []
        for v in self.violations:
            instr_prefix = f"instrument '{v.instrument_name}' at " if v.instrument_name else ""
            messages.append(
                f"  {v.coordinate_type} position ({v.x}, {v.y}, {v.z}) for "
                f"{instr_prefix}{v.labware_key}.{v.position_id} "
                f"violates {v.bound_name}={v.bound_value}"
            )
        super().__init__(
            f"Bounds validation failed with {len(self.violations)} violation(s):\n"
            + "\n".join(messages)
        )


@dataclass(frozen=True)
class CollisionIssue:
    """One collision validation error, warning, or suggestion."""

    severity: Literal["error", "warning", "suggestion"]
    code: str
    message: str
    step_index: int | None = None
    command_name: str | None = None
    active_instrument: str | None = None
    body_a: str | None = None
    body_b: str | None = None


class CollisionValidationError(Exception):
    """Raised when collision validation blocks protocol setup."""

    def __init__(self, issues: list[CollisionIssue]) -> None:
        self.issues: Tuple[CollisionIssue, ...] = tuple(issues)
        errors = [issue for issue in self.issues if issue.severity == "error"]
        messages = []
        for issue in errors:
            location = ""
            if issue.step_index is not None:
                location = f"step {issue.step_index}"
                if issue.command_name:
                    location += f" ({issue.command_name})"
                location += ": "
            messages.append(f"  {location}{issue.message}")
        super().__init__(
            f"Collision validation failed with {len(errors)} error(s):\n"
            + "\n".join(messages)
        )
