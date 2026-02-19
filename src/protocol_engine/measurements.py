"""Protocol-layer measurement normalization and typing."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from instruments.uvvis_ccs.models import UVVisSpectrum


class MeasurementType(str, Enum):
    """Normalized measurement types understood by protocol persistence."""

    UVVIS_SPECTRUM = "uvvis_spectrum"


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

    raise TypeError(
        "Unsupported measurement result type: "
        f"{type(raw_result).__name__} from {instrument_name}.{method_name}"
    )
