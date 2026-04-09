"""Tests for the potentiostat instrument driver."""

from __future__ import annotations

import pytest

from instruments.potentiostat.driver import Potentiostat
from instruments.potentiostat.exceptions import PotentiostatConfigError
from instruments.potentiostat.mock import MockPotentiostat
from instruments.potentiostat.models import (
    ChronoAmperometryResult,
    CyclicVoltammetryResult,
    OCPResult,
    PotentiostatStatus,
)


class TestPotentiostatOffline:

    @pytest.mark.parametrize("vendor", ["gamry", "emstat"])
    def test_connect_disconnect_are_noops(self, vendor):
        instrument = Potentiostat(vendor=vendor, offline=True)
        instrument.connect()
        instrument.disconnect()

    @pytest.mark.parametrize("vendor", ["gamry", "emstat"])
    def test_health_check_returns_true(self, vendor):
        instrument = Potentiostat(vendor=vendor, offline=True)
        assert instrument.health_check() is True

    @pytest.mark.parametrize("vendor", ["gamry", "emstat"])
    def test_get_status_returns_connected_vendor_snapshot(self, vendor):
        instrument = Potentiostat(vendor=vendor, offline=True)

        status = instrument.get_status()

        assert isinstance(status, PotentiostatStatus)
        assert status.is_connected is True
        assert status.vendor == vendor
        assert status.backend_name == vendor

    @pytest.mark.parametrize("vendor", ["gamry", "emstat"])
    def test_measure_ocp_returns_valid_result(self, vendor):
        instrument = Potentiostat(vendor=vendor, offline=True)

        result = instrument.measure_ocp(duration_s=1.0, sample_period_s=0.1)

        assert isinstance(result, OCPResult)
        assert result.vendor == vendor
        assert result.technique == "ocp"
        assert result.is_valid is True
        assert len(result.time_s) == len(result.voltage_v)
        assert result.sample_period_s == pytest.approx(0.1)
        assert result.duration_s == pytest.approx(1.0)

    @pytest.mark.parametrize("vendor", ["gamry", "emstat"])
    def test_run_chronoamperometry_returns_valid_result(self, vendor):
        instrument = Potentiostat(vendor=vendor, offline=True)

        result = instrument.run_chronoamperometry(
            step_potential_v=-0.8,
            duration_s=1.0,
            sample_period_s=0.1,
        )

        assert isinstance(result, ChronoAmperometryResult)
        assert result.vendor == vendor
        assert result.technique == "ca"
        assert result.is_valid is True
        assert len(result.time_s) == len(result.current_a)
        assert len(result.time_s) == len(result.voltage_v)
        assert result.step_potential_v == pytest.approx(-0.8)

    @pytest.mark.parametrize("vendor", ["gamry", "emstat"])
    def test_run_cyclic_voltammetry_returns_valid_result(self, vendor):
        instrument = Potentiostat(vendor=vendor, offline=True)

        result = instrument.run_cyclic_voltammetry(
            initial_potential_v=0.0,
            vertex_potential_1_v=0.5,
            vertex_potential_2_v=-0.5,
            final_potential_v=0.0,
            scan_rate_v_s=0.1,
            step_size_v=0.05,
            cycles=1,
        )

        assert isinstance(result, CyclicVoltammetryResult)
        assert result.vendor == vendor
        assert result.technique == "cv"
        assert result.is_valid is True
        assert len(result.time_s) == len(result.current_a)
        assert len(result.time_s) == len(result.voltage_v)
        assert result.scan_rate_v_s == pytest.approx(0.1)
        assert result.step_size_v == pytest.approx(0.05)
        assert result.cycles == 1

    def test_measure_alias_runs_ocp(self):
        instrument = Potentiostat(vendor="emstat", offline=True)

        result = instrument.measure(duration_s=1.0, sample_period_s=0.2)

        assert isinstance(result, OCPResult)
        assert result.technique == "ocp"
        assert result.sample_period_s == pytest.approx(0.2)


class TestPotentiostatValidation:

    def test_unsupported_vendor_raises(self):
        with pytest.raises(PotentiostatConfigError, match="Unsupported potentiostat vendor"):
            Potentiostat(vendor="unknown", offline=True)

    @pytest.mark.parametrize("vendor", ["gamry", "emstat"])
    def test_invalid_ocp_duration_raises(self, vendor):
        instrument = Potentiostat(vendor=vendor, offline=True)

        with pytest.raises(PotentiostatConfigError, match="duration_s must be > 0"):
            instrument.measure_ocp(duration_s=0.0, sample_period_s=0.1)

    @pytest.mark.parametrize("vendor", ["gamry", "emstat"])
    def test_invalid_ocp_sample_period_raises(self, vendor):
        instrument = Potentiostat(vendor=vendor, offline=True)

        with pytest.raises(PotentiostatConfigError, match="sample_period_s must be > 0"):
            instrument.measure_ocp(duration_s=1.0, sample_period_s=0.0)

    @pytest.mark.parametrize("vendor", ["gamry", "emstat"])
    def test_invalid_ca_duration_raises(self, vendor):
        instrument = Potentiostat(vendor=vendor, offline=True)

        with pytest.raises(PotentiostatConfigError, match="duration_s must be > 0"):
            instrument.run_chronoamperometry(step_potential_v=-0.5, duration_s=0.0, sample_period_s=0.1)

    def test_invalid_cv_cycle_count_raises(self):
        instrument = Potentiostat(vendor="emstat", offline=True)

        with pytest.raises(PotentiostatConfigError, match="cycles must be >= 1"):
            instrument.run_cyclic_voltammetry(
                initial_potential_v=0.0,
                vertex_potential_1_v=0.5,
                vertex_potential_2_v=-0.5,
                final_potential_v=0.0,
                scan_rate_v_s=0.1,
                step_size_v=0.05,
                cycles=0,
            )

    def test_invalid_cv_scan_rate_raises(self):
        instrument = Potentiostat(vendor="gamry", offline=True)

        with pytest.raises(PotentiostatConfigError, match="scan_rate_v_s must be > 0"):
            instrument.run_cyclic_voltammetry(
                initial_potential_v=0.0,
                vertex_potential_1_v=0.5,
                vertex_potential_2_v=-0.5,
                final_potential_v=0.0,
                scan_rate_v_s=0.0,
                step_size_v=0.05,
                cycles=1,
            )

    def test_invalid_cv_step_size_raises(self):
        instrument = Potentiostat(vendor="emstat", offline=True)

        with pytest.raises(PotentiostatConfigError, match="step_size_v must be > 0"):
            instrument.run_cyclic_voltammetry(
                initial_potential_v=0.0,
                vertex_potential_1_v=0.5,
                vertex_potential_2_v=-0.5,
                final_potential_v=0.0,
                scan_rate_v_s=0.1,
                step_size_v=0.0,
                cycles=1,
            )

    @pytest.mark.parametrize("vendor_input,expected", [
        ("GAMRY", "gamry"),
        ("  emstat  ", "emstat"),
        ("EMSTAT", "emstat"),
    ])
    def test_vendor_string_is_normalized(self, vendor_input, expected):
        instrument = Potentiostat(vendor=vendor_input, offline=True)
        assert instrument.vendor == expected


class TestMockPotentiostat:

    def test_command_history_records_lifecycle(self):
        mock = MockPotentiostat(vendor="emstat")

        mock.connect()
        mock.measure_ocp(duration_s=1.0, sample_period_s=0.1)
        mock.run_chronoamperometry(step_potential_v=-0.5, duration_s=1.0, sample_period_s=0.1)
        mock.run_cyclic_voltammetry(
            initial_potential_v=0.0,
            vertex_potential_1_v=0.5,
            vertex_potential_2_v=-0.5,
            final_potential_v=0.0,
            scan_rate_v_s=0.1,
            step_size_v=0.05,
        )
        mock.disconnect()

        assert mock.command_history == [
            "connect",
            "measure_ocp",
            "run_chronoamperometry",
            "run_cyclic_voltammetry",
            "disconnect",
        ]

    def test_mock_returns_valid_results(self):
        mock = MockPotentiostat(vendor="gamry")

        result = mock.measure_ocp(duration_s=1.0, sample_period_s=0.2)

        assert isinstance(result, OCPResult)
        assert result.is_valid is True
