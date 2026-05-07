"""Unit tests for :mod:`protocol_engine.scan_args`."""

from __future__ import annotations

import pytest

from protocol_engine.scan_args import (
    NormalizedScanArguments,
    normalize_scan_arguments,
)


class TestNormalizeScanArguments:

    def test_returns_relative_offsets_when_provided(self):
        normalized = normalize_scan_arguments(safe_approach_height=10.0)
        assert isinstance(normalized, NormalizedScanArguments)
        assert normalized.safe_approach_height == 10.0
        assert normalized.method_kwargs == {}

    def test_safe_approach_height_optional_at_args_layer(self):
        """``normalize_scan_arguments`` no longer requires
        ``safe_approach_height`` — runtime resolution against the
        instrument config happens later in the scan command."""
        normalized = normalize_scan_arguments()
        assert normalized.safe_approach_height is None

    def test_legacy_entry_travel_height_rejected(self):
        with pytest.raises(ValueError, match="entry_travel_height"):
            normalize_scan_arguments(
                safe_approach_height=10.0,
                method_kwargs={"entry_travel_height": 30.0},
            )

    def test_legacy_interwell_travel_height_rejected(self):
        with pytest.raises(ValueError, match="interwell_travel_height"):
            normalize_scan_arguments(
                safe_approach_height=10.0,
                method_kwargs={"interwell_travel_height": 20.0},
            )

    def test_indentation_limit_passes_through_to_method_kwargs(self):
        normalized = normalize_scan_arguments(
            safe_approach_height=10.0,
            indentation_limit=5.0,
        )
        assert normalized.method_kwargs == {"indentation_limit": 5.0}

    def test_indentation_limit_conflict_rejected(self):
        with pytest.raises(ValueError, match="indentation_limit"):
            normalize_scan_arguments(
                safe_approach_height=10.0,
                indentation_limit=5.0,
                method_kwargs={"indentation_limit": 4.0},
            )

    def test_z_limit_kwarg_rejected(self):
        with pytest.raises(ValueError, match="z_limit"):
            normalize_scan_arguments(
                safe_approach_height=10.0,
                method_kwargs={"z_limit": 5.0},
            )
