"""Tests for the shared movement helpers used by engaging commands."""

from unittest.mock import MagicMock

import pytest

from deck.labware.labware import Coordinate3D
from protocol_engine.commands._movement import (
    _assert_finite_number,
    engage_at_labware,
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


class TestAssertFiniteNumber:

    def test_accepts_int_and_float(self):
        _assert_finite_number(0, field_name="x", source="test")
        _assert_finite_number(1.5, field_name="x", source="test")
        _assert_finite_number(-1.0, field_name="x", source="test")

    @pytest.mark.parametrize("bad", ["", "1.0", "abc", float("nan"), float("inf"), True, False, None])
    def test_rejects_non_finite_or_wrong_type(self, bad):
        with pytest.raises(ValueError, match="must be a finite number"):
            _assert_finite_number(bad, field_name="x", source="test")


def _mock_ctx_with_labware(height_mm=14.10):
    instr = MagicMock()
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

    def test_descends_to_labware_plus_offset(self):
        ctx, _, _ = _mock_ctx_with_labware(height_mm=14.10)
        action_z = engage_at_labware(
            ctx, "sensor", "plate.A1",
            measurement_height=2.0, command_label="measure",
        )
        assert action_z == pytest.approx(16.10)
        ctx.board.move_to_labware.assert_called_once()
        ctx.board.move.assert_called_once_with("sensor", (10.0, 20.0, 16.10))

    def test_negative_offset_descends_below_surface(self):
        ctx, _, _ = _mock_ctx_with_labware(height_mm=14.10)
        action_z = engage_at_labware(
            ctx, "sensor", "plate.A1",
            measurement_height=-1.0, command_label="measure",
        )
        assert action_z == pytest.approx(13.10)

    def test_missing_height_mm_raises(self):
        ctx, _, labware = _mock_ctx_with_labware(height_mm=None)
        labware.height_mm = None
        with pytest.raises(ValueError, match="height_mm"):
            engage_at_labware(
                ctx, "sensor", "plate.A1",
                measurement_height=2.0, command_label="measure",
            )

    @pytest.mark.parametrize("bad", ["", "1.0", float("nan"), True])
    def test_rejects_non_finite_measurement_height(self, bad):
        ctx, _, _ = _mock_ctx_with_labware(height_mm=14.10)
        with pytest.raises(ValueError, match="finite number"):
            engage_at_labware(
                ctx, "sensor", "plate.A1",
                measurement_height=bad, command_label="measure",
            )
