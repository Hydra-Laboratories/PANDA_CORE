"""Tests for protocol-layer measurement normalization."""

from __future__ import annotations

import pytest

from instruments.uvvis_ccs.models import UVVisSpectrum
from protocol_engine.measurements import (
    InstrumentMeasurement,
    MeasurementType,
    normalize_measurement,
)


def _make_uvvis_spectrum() -> UVVisSpectrum:
    return UVVisSpectrum(
        wavelengths=(400.0, 500.0, 600.0),
        intensities=(0.1, 0.2, 0.3),
        integration_time_s=0.24,
    )


class TestNormalizeMeasurement:

    def test_normalize_uvvis_returns_instrument_measurement(self):
        measurement = normalize_measurement(
            instrument_name="uvvis",
            method_name="measure",
            raw_result=_make_uvvis_spectrum(),
        )

        assert isinstance(measurement, InstrumentMeasurement)
        assert measurement.measurement_type == MeasurementType.UVVIS_SPECTRUM

    def test_normalize_uvvis_maps_mofcat_style_payload_fields(self):
        measurement = normalize_measurement(
            instrument_name="uvvis",
            method_name="measure",
            raw_result=_make_uvvis_spectrum(),
        )

        assert measurement.payload["wavelength_nm"] == [400.0, 500.0, 600.0]
        assert measurement.payload["intensity_au"] == [0.1, 0.2, 0.3]

    def test_normalize_uvvis_captures_integration_time_in_metadata(self):
        measurement = normalize_measurement(
            instrument_name="uvvis",
            method_name="measure",
            raw_result=_make_uvvis_spectrum(),
        )

        assert measurement.metadata["integration_time_s"] == pytest.approx(0.24)

    def test_unknown_measurement_type_raises_type_error(self):
        with pytest.raises(TypeError, match="Unsupported measurement result"):
            normalize_measurement(
                instrument_name="uvvis",
                method_name="measure",
                raw_result=object(),
            )
