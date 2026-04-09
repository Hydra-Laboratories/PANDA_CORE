"""Tests for protocol-layer measurement normalization."""

from __future__ import annotations

import pytest

from instruments.potentiostat.models import (
    ChronoAmperometryResult,
    CyclicVoltammetryResult,
    OCPResult,
)
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


def _make_ocp_result() -> OCPResult:
    return OCPResult(
        time_s=(0.0, 0.5, 1.0),
        voltage_v=(0.11, 0.12, 0.13),
        sample_period_s=0.5,
        duration_s=1.0,
        vendor="emstat",
    )


def _make_ca_result() -> ChronoAmperometryResult:
    return ChronoAmperometryResult(
        time_s=(0.0, 0.5, 1.0),
        current_a=(1e-6, 8e-7, 6e-7),
        voltage_v=(-0.8, -0.8, -0.8),
        sample_period_s=0.5,
        duration_s=1.0,
        step_potential_v=-0.8,
        vendor="gamry",
    )


def _make_cv_result() -> CyclicVoltammetryResult:
    return CyclicVoltammetryResult(
        time_s=(0.0, 0.5, 1.0),
        voltage_v=(0.0, 0.5, 0.0),
        current_a=(1e-6, 2e-6, 1e-6),
        scan_rate_v_s=0.1,
        step_size_v=0.05,
        cycles=1,
        vendor="emstat",
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

    def test_normalize_ocp_returns_potentiostat_measurement(self):
        measurement = normalize_measurement(
            instrument_name="potentiostat",
            method_name="measure_ocp",
            raw_result=_make_ocp_result(),
        )

        assert isinstance(measurement, InstrumentMeasurement)
        assert measurement.measurement_type == MeasurementType.POTENTIOSTAT_OCP
        assert measurement.payload["time_s"] == [0.0, 0.5, 1.0]
        assert measurement.payload["voltage_v"] == [0.11, 0.12, 0.13]
        assert measurement.metadata["vendor"] == "emstat"
        assert measurement.metadata["technique"] == "ocp"

    def test_normalize_ca_returns_potentiostat_measurement(self):
        measurement = normalize_measurement(
            instrument_name="potentiostat",
            method_name="run_chronoamperometry",
            raw_result=_make_ca_result(),
        )

        assert measurement.measurement_type == MeasurementType.POTENTIOSTAT_CA
        assert measurement.payload["current_a"] == [1e-6, 8e-7, 6e-7]
        assert measurement.payload["voltage_v"] == [-0.8, -0.8, -0.8]
        assert measurement.metadata["step_potential_v"] == pytest.approx(-0.8)
        assert measurement.metadata["vendor"] == "gamry"

    def test_normalize_cv_returns_potentiostat_measurement(self):
        measurement = normalize_measurement(
            instrument_name="potentiostat",
            method_name="run_cyclic_voltammetry",
            raw_result=_make_cv_result(),
        )

        assert measurement.measurement_type == MeasurementType.POTENTIOSTAT_CV
        assert measurement.payload["time_s"] == [0.0, 0.5, 1.0]
        assert measurement.payload["voltage_v"] == [0.0, 0.5, 0.0]
        assert measurement.payload["current_a"] == [1e-6, 2e-6, 1e-6]
        assert measurement.metadata["cycles"] == 1
        assert measurement.metadata["scan_rate_v_s"] == pytest.approx(0.1)

    def test_unknown_measurement_type_raises_type_error(self):
        with pytest.raises(TypeError, match="Unsupported measurement result"):
            normalize_measurement(
                instrument_name="uvvis",
                method_name="measure",
                raw_result=object(),
            )
