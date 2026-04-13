"""Unit tests for potentiostat params/results dataclasses and exceptions."""

import numpy as np
import pytest

from instruments.base_instrument import InstrumentError
from instruments.potentiostat.exceptions import (
    PotentiostatCommandError,
    PotentiostatConfigError,
    PotentiostatConnectionError,
    PotentiostatError,
    PotentiostatTimeoutError,
)
from instruments.potentiostat.models import (
    CAParams,
    CAResult,
    CPParams,
    CPResult,
    CVParams,
    CVResult,
    OCPParams,
    OCPResult,
)


# --- Exception hierarchy ------------------------------------------------------


class TestExceptionHierarchy:

    @pytest.mark.parametrize(
        "cls",
        [
            PotentiostatConnectionError,
            PotentiostatCommandError,
            PotentiostatTimeoutError,
            PotentiostatConfigError,
        ],
    )
    def test_subclasses_inherit_from_potentiostat_error(self, cls):
        assert issubclass(cls, PotentiostatError)

    def test_potentiostat_error_inherits_from_instrument_error(self):
        assert issubclass(PotentiostatError, InstrumentError)


# --- CVParams -----------------------------------------------------------------


class TestCVParams:

    def test_valid_params_construct(self):
        p = CVParams(
            start_V=0.0,
            vertex1_V=0.5,
            vertex2_V=-0.5,
            end_V=0.0,
            scan_rate_V_per_s=0.05,
            cycles=3,
            sampling_interval_s=0.02,
        )
        assert p.cycles == 3
        assert p.scan_rate_V_per_s == 0.05

    def test_frozen(self):
        p = CVParams(0.0, 0.5, -0.5, 0.0, 0.05)
        with pytest.raises(AttributeError):
            p.cycles = 5  # type: ignore[misc]

    def test_zero_scan_rate_rejected(self):
        with pytest.raises(PotentiostatConfigError, match="scan_rate_V_per_s"):
            CVParams(0.0, 0.5, -0.5, 0.0, 0.0)

    def test_negative_scan_rate_rejected(self):
        with pytest.raises(PotentiostatConfigError):
            CVParams(0.0, 0.5, -0.5, 0.0, -0.1)

    def test_zero_cycles_rejected(self):
        with pytest.raises(PotentiostatConfigError, match="cycles"):
            CVParams(0.0, 0.5, -0.5, 0.0, 0.05, cycles=0)

    def test_zero_sampling_interval_rejected(self):
        with pytest.raises(PotentiostatConfigError, match="sampling_interval_s"):
            CVParams(0.0, 0.5, -0.5, 0.0, 0.05, sampling_interval_s=0.0)

    def test_identical_vertices_rejected(self):
        with pytest.raises(PotentiostatConfigError, match="vertex"):
            CVParams(0.0, 0.5, 0.5, 0.0, 0.05)


# --- OCPParams / CAParams / CPParams -----------------------------------------


class TestDurationParams:

    @pytest.mark.parametrize(
        "cls,kwargs",
        [
            (OCPParams, {"duration_s": 10.0}),
            (CAParams, {"potential_V": 0.5, "duration_s": 10.0}),
            (CPParams, {"current_A": 1e-3, "duration_s": 10.0}),
        ],
    )
    def test_valid(self, cls, kwargs):
        p = cls(**kwargs)
        assert p.duration_s == 10.0

    @pytest.mark.parametrize(
        "cls,kwargs",
        [
            (OCPParams, {"duration_s": 0.0}),
            (CAParams, {"potential_V": 0.5, "duration_s": 0.0}),
            (CPParams, {"current_A": 1e-3, "duration_s": 0.0}),
        ],
    )
    def test_zero_duration_rejected(self, cls, kwargs):
        with pytest.raises(PotentiostatConfigError, match="duration_s"):
            cls(**kwargs)

    @pytest.mark.parametrize(
        "cls,kwargs",
        [
            (OCPParams, {"duration_s": 1.0, "sampling_interval_s": 0.0}),
            (CAParams, {"potential_V": 0.5, "duration_s": 1.0, "sampling_interval_s": 0.0}),
            (CPParams, {"current_A": 1e-3, "duration_s": 1.0, "sampling_interval_s": 0.0}),
        ],
    )
    def test_zero_sampling_interval_rejected(self, cls, kwargs):
        with pytest.raises(PotentiostatConfigError, match="sampling_interval_s"):
            cls(**kwargs)

    def test_sampling_interval_larger_than_duration_rejected(self):
        with pytest.raises(PotentiostatConfigError, match="sampling_interval_s"):
            OCPParams(duration_s=0.5, sampling_interval_s=1.0)


# --- Result dataclasses -------------------------------------------------------


class TestResults:

    def test_cv_result_holds_arrays_and_metadata(self):
        r = CVResult(
            potentials_V=np.array([0.0, 0.1, 0.2]),
            currents_A=np.array([1e-6, 2e-6, 3e-6]),
            timestamps_s=np.array([0.0, 0.01, 0.02]),
            cycle_index=np.array([0, 0, 0]),
            metadata={"model": "SquidStatPlus", "aborted": False},
        )
        assert r.potentials_V.shape == (3,)
        assert r.metadata["model"] == "SquidStatPlus"

    def test_cv_result_is_frozen(self):
        r = CVResult(
            potentials_V=np.array([0.0]),
            currents_A=np.array([0.0]),
            timestamps_s=np.array([0.0]),
            cycle_index=np.array([0]),
        )
        with pytest.raises(AttributeError):
            r.metadata = {"x": 1}  # type: ignore[misc]

    def test_default_metadata_is_empty_mapping(self):
        r = OCPResult(
            potentials_V=np.array([0.0]),
            timestamps_s=np.array([0.0]),
        )
        assert r.metadata == {}

    def test_ca_and_cp_shapes_align(self):
        ca = CAResult(
            currents_A=np.array([1e-6, 2e-6]),
            potentials_V=np.array([0.5, 0.5]),
            timestamps_s=np.array([0.0, 0.01]),
        )
        cp = CPResult(
            currents_A=np.array([1e-3, 1e-3]),
            potentials_V=np.array([0.3, 0.31]),
            timestamps_s=np.array([0.0, 0.01]),
        )
        assert ca.currents_A.shape == ca.potentials_V.shape == ca.timestamps_s.shape
        assert cp.currents_A.shape == cp.potentials_V.shape == cp.timestamps_s.shape
