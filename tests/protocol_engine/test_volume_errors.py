"""Tests for volume-related error types."""

import pytest

from protocol_engine.errors import (
    ProtocolExecutionError,
    VolumeError,
    OverflowVolumeError,
    UnderflowVolumeError,
    InvalidVolumeError,
    PipetteVolumeError,
)


class TestVolumeErrorHierarchy:

    def test_volume_error_is_protocol_execution_error(self):
        assert issubclass(VolumeError, ProtocolExecutionError)

    def test_overflow_is_volume_error(self):
        assert issubclass(OverflowVolumeError, VolumeError)

    def test_underflow_is_volume_error(self):
        assert issubclass(UnderflowVolumeError, VolumeError)

    def test_invalid_is_volume_error(self):
        assert issubclass(InvalidVolumeError, VolumeError)

    def test_pipette_volume_is_volume_error(self):
        assert issubclass(PipetteVolumeError, VolumeError)


class TestOverflowVolumeError:

    def test_stores_attributes(self):
        err = OverflowVolumeError(
            labware_key="plate_1",
            well_id="A1",
            current_volume_ul=180.0,
            requested_ul=50.0,
            capacity_ul=200.0,
        )
        assert err.labware_key == "plate_1"
        assert err.well_id == "A1"
        assert err.current_volume_ul == 180.0
        assert err.requested_ul == 50.0
        assert err.capacity_ul == 200.0

    def test_message_includes_location_and_volumes(self):
        err = OverflowVolumeError(
            labware_key="plate_1",
            well_id="A1",
            current_volume_ul=180.0,
            requested_ul=50.0,
            capacity_ul=200.0,
        )
        msg = str(err)
        assert "plate_1.A1" in msg
        assert "50" in msg
        assert "180" in msg
        assert "200" in msg

    def test_vial_location_without_well_id(self):
        err = OverflowVolumeError(
            labware_key="vial_1",
            well_id=None,
            current_volume_ul=1400.0,
            requested_ul=200.0,
            capacity_ul=1500.0,
        )
        msg = str(err)
        assert "vial_1" in msg
        assert ".None" not in msg

    def test_is_catchable_as_protocol_execution_error(self):
        err = OverflowVolumeError("p", "A1", 100.0, 200.0, 200.0)
        with pytest.raises(ProtocolExecutionError):
            raise err


class TestUnderflowVolumeError:

    def test_stores_attributes(self):
        err = UnderflowVolumeError(
            labware_key="vial_1",
            well_id=None,
            current_volume_ul=10.0,
            requested_ul=50.0,
        )
        assert err.labware_key == "vial_1"
        assert err.well_id is None
        assert err.current_volume_ul == 10.0
        assert err.requested_ul == 50.0

    def test_message_includes_location_and_volumes(self):
        err = UnderflowVolumeError(
            labware_key="plate_1",
            well_id="B2",
            current_volume_ul=5.0,
            requested_ul=100.0,
        )
        msg = str(err)
        assert "plate_1.B2" in msg
        assert "5" in msg
        assert "100" in msg


class TestInvalidVolumeError:

    def test_accepts_custom_message(self):
        err = InvalidVolumeError("Volume must be positive, got -5.0")
        assert "-5.0" in str(err)

    def test_is_catchable_as_volume_error(self):
        with pytest.raises(VolumeError):
            raise InvalidVolumeError("bad volume")


class TestPipetteVolumeError:

    def test_stores_attributes(self):
        err = PipetteVolumeError(
            requested_ul=5.0,
            min_ul=20.0,
            max_ul=200.0,
        )
        assert err.requested_ul == 5.0
        assert err.min_ul == 20.0
        assert err.max_ul == 200.0

    def test_message_includes_range(self):
        err = PipetteVolumeError(
            requested_ul=5.0,
            min_ul=20.0,
            max_ul=200.0,
        )
        msg = str(err)
        assert "5" in msg
        assert "20" in msg
        assert "200" in msg
