"""Instrument/TCP calibration placeholder.

TODO:
- Move the old interactive TCP offset workflow here.
- Calibrate one selected instrument after deck-origin calibration is stable.
- Record offset_x, offset_y, signed depth, and reach_limits.
- Keep the origin/bounds script independent from instrument calibration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstrumentCalibrationResult:
    offset_x: float
    offset_y: float
    depth: float
    reach_limits: dict[str, float]


def run_instrument_calibration() -> InstrumentCalibrationResult:
    raise NotImplementedError(
        "TODO: move the interactive instrument offset/depth/reach calibration here."
    )
