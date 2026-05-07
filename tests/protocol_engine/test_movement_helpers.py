"""Tests for the shared movement helpers used by engaging commands."""

from unittest.mock import MagicMock

import pytest

from deck.labware.labware import Coordinate3D
from protocol_engine.commands._movement import (
    engage_at_labware,
    resolve_instrument_measurement_height,
    resolve_labware_height,
    unpack_xyz,
)


class TestUnpackXyz:

    def test_tuple(self):
        assert unpack_xyz((1.0, 2.0, 3.0)) == (1.0, 2.0, 3.0)

    def test_list(self):
        assert unpack_xyz([4.0, 5.0, 6.0]) == (4.0, 5.0, 6.0)

    def test_coordinate3d(self):
        assert unpack_xyz(Coordinate3D(x=1.5, y=2.5, z=3.5)) == (1.5, 2.5, 3.5)

    def test_object_with_xyz_attrs(self):
        obj = MagicMock()
        obj.x, obj.y, obj.z = 10.0, 20.0, 30.0
        assert unpack_xyz(obj) == (10.0, 20.0, 30.0)


class TestResolveLabwareHeight:

    def test_returns_height_mm(self):
        labware = MagicMock(height_mm=14.10)
        assert resolve_labware_height(labware, "plate") == 14.10

    def test_raises_when_height_mm_missing(self):
        labware = MagicMock(spec=["x", "y"])
        with pytest.raises(ValueError, match="height_mm"):
            resolve_labware_height(labware, "plate")


class TestResolveInstrumentMeasurementHeight:

    def test_returns_instrument_value(self):
        assert resolve_instrument_measurement_height(
            instrument_value=-1.0,
            instrument_name="probe",
            command_label="measure",
        ) == -1.0

    def test_rejects_when_unset(self):
        with pytest.raises(ValueError, match="not set on instrument"):
            resolve_instrument_measurement_height(
                instrument_value=None,
                instrument_name="probe",
                command_label="measure",
            )

    @pytest.mark.parametrize("bad_value", ["", "1.0", "abc", float("nan"), float("inf"), True])
    def test_rejects_non_finite_values(self, bad_value):
        with pytest.raises(ValueError, match="finite number"):
            resolve_instrument_measurement_height(
                instrument_value=bad_value,
                instrument_name="probe",
                command_label="measure",
            )


def _mock_ctx_with_labware(measurement_height=None, height_mm=14.10):
    instr = MagicMock()
    instr.measurement_height = measurement_height
    board = MagicMock()
    board.instruments = {"sensor": instr}
    labware = MagicMock(height_mm=height_mm)
    labware.x, labware.y, labware.z = 10.0, 20.0, height_mm or 0.0
    deck = MagicMock()
    deck.resolve.return_value = Coordinate3D(x=10.0, y=20.0, z=height_mm or 0.0)
    deck.__getitem__.return_value = labware
    ctx = MagicMock()
    ctx.board = board
    ctx.deck = deck
    return ctx, instr, labware


class TestEngageAtLabware:

    def test_travels_at_safe_z_then_descends_to_action_plane(self):
        ctx, _, _ = _mock_ctx_with_labware(measurement_height=2.0, height_mm=14.10)
        action_z = engage_at_labware(
            ctx, "sensor", "plate.A1", command_label="measure",
        )
        assert action_z == pytest.approx(16.10)
        ctx.board.move_to_labware.assert_called_once()
        ctx.board.move.assert_called_once_with("sensor", (10.0, 20.0, 16.10))

    def test_negative_offset_descends_below_surface(self):
        ctx, _, _ = _mock_ctx_with_labware(measurement_height=-1.0, height_mm=14.10)
        action_z = engage_at_labware(
            ctx, "sensor", "plate.A1", command_label="measure",
        )
        assert action_z == pytest.approx(13.10)

    def test_missing_instrument_measurement_height_raises(self):
        ctx, _, _ = _mock_ctx_with_labware(measurement_height=None, height_mm=14.10)
        with pytest.raises(ValueError, match="not set on instrument"):
            engage_at_labware(
                ctx, "sensor", "plate.A1", command_label="measure",
            )

    def test_missing_height_mm_raises(self):
        ctx, _, labware = _mock_ctx_with_labware(measurement_height=2.0, height_mm=None)
        labware.height_mm = None
        with pytest.raises(ValueError, match="height_mm"):
            engage_at_labware(
                ctx, "sensor", "plate.A1", command_label="measure",
            )
