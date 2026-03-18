"""Protocol-layer measurement normalization and typing."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from instruments.uvvis_ccs.models import UVVisSpectrum


class MeasurementType(str, Enum):
    """Normalized measurement types understood by protocol persistence."""

    UVVIS_SPECTRUM = "uvvis_spectrum"
    ASMI_INDENTATION = "asmi_indentation"


@dataclass(frozen=True)
class InstrumentMeasurement:
    """Instrument-agnostic measurement returned by protocol normalization."""

    measurement_type: MeasurementType
    payload: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


def normalize_measurement(
    instrument_name: str,
    method_name: str,
    raw_result: Any,
) -> InstrumentMeasurement:
    """Normalize a raw instrument result into a protocol measurement object."""
    if isinstance(raw_result, UVVisSpectrum):
        return InstrumentMeasurement(
            measurement_type=MeasurementType.UVVIS_SPECTRUM,
            payload={
                # Align field names with mofcat-workflow conventions.
                "wavelength_nm": list(raw_result.wavelengths),
                "intensity_au": list(raw_result.intensities),
            },
            metadata={
                "integration_time_s": raw_result.integration_time_s,
                "instrument_name": instrument_name,
                "method_name": method_name,
            },
        )

    if isinstance(raw_result, dict) and "measurements" in raw_result:
        steps = raw_result["measurements"]
        return InstrumentMeasurement(
            measurement_type=MeasurementType.ASMI_INDENTATION,
            payload={
                "z_positions_mm": [s["z_mm"] for s in steps],
                "raw_forces_n": [s["raw_force_n"] for s in steps],
                "corrected_forces_n": [s["corrected_force_n"] for s in steps],
            },
            metadata={
                "baseline_avg": raw_result.get("baseline_avg", 0.0),
                "baseline_std": raw_result.get("baseline_std", 0.0),
                "force_exceeded": raw_result.get("force_exceeded", False),
                "data_points": raw_result.get("data_points", len(steps)),
                "instrument_name": instrument_name,
                "method_name": method_name,
            },
        )

    raise TypeError(
        "Unsupported measurement result type: "
        f"{type(raw_result).__name__} from {instrument_name}.{method_name}"
    )
