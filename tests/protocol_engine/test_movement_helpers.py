"""Tests for the shared movement helpers used by engaging commands."""

from unittest.mock import MagicMock

import pytest

from deck.labware.labware import Coordinate3D
from protocol_engine.commands._movement import approach_and_descend, unpack_xyz


# ─── unpack_xyz ─────────────────────────────────────────────────────────────


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


# ─── approach_and_descend ───────────────────────────────────────────────────


def _mock_ctx(measurement_height=0.0):
    instr = MagicMock()
    instr.measurement_height = measurement_height
    board = MagicMock()
    board.instruments = {"sensor": instr}
    ctx = MagicMock()
    ctx.board = board
    return ctx, instr


class TestApproachAndDescend:

    def test_calls_move_to_labware_then_descent_move(self):
        ctx, instr = _mock_ctx(measurement_height=3.0)
        coord = Coordinate3D(x=10.0, y=20.0, z=30.0)

        order = []
        ctx.board.move_to_labware.side_effect = lambda *a, **k: order.append("approach")
        ctx.board.move.side_effect = lambda *a, **k: order.append("descent")

        approach_and_descend(ctx, "sensor", coord)

        assert order == ["approach", "descent"]
        ctx.board.move_to_labware.assert_called_once_with("sensor", coord)

    def test_descent_uses_measurement_height(self):
        ctx, instr = _mock_ctx(measurement_height=3.0)
        coord = Coordinate3D(x=10.0, y=20.0, z=30.0)
        approach_and_descend(ctx, "sensor", coord)
        ctx.board.move.assert_called_once_with("sensor", (10.0, 20.0, 3.0))

    def test_descent_for_contact_instrument_is_below_reference(self):
        # Lower absolute Z means the tip moves down toward the deck.
        ctx, instr = _mock_ctx(measurement_height=-5.0)
        coord = Coordinate3D(x=10.0, y=20.0, z=30.0)
        approach_and_descend(ctx, "sensor", coord)
        ctx.board.move.assert_called_once_with("sensor", (10.0, 20.0, -5.0))

    def test_descent_for_non_contact_lands_at_same_z_as_approach(self):
        """Non-contact instrument: action == approach Z. Descent is a
        structural no-op (same Z) but the call still happens."""
        ctx, instr = _mock_ctx(measurement_height=0.0)
        coord = Coordinate3D(x=10.0, y=20.0, z=30.0)
        approach_and_descend(ctx, "sensor", coord)
        ctx.board.move.assert_called_once_with("sensor", (10.0, 20.0, 0.0))

    def test_accepts_tuple_coord(self):
        ctx, instr = _mock_ctx(measurement_height=2.0)
        approach_and_descend(ctx, "sensor", (5.0, 6.0, 7.0))
        ctx.board.move.assert_called_once_with("sensor", (5.0, 6.0, 2.0))

    def test_safe_approach_height_override_uses_protocol_value(self):
        """Protocol-level absolute safe_approach_height overrides
        move_to_labware. In positive-down Z, approach (smaller z)
        must be above action (larger z)."""
        ctx, instr = _mock_ctx(measurement_height=3.0)
        coord = Coordinate3D(x=10.0, y=20.0, z=30.0)

        approach_and_descend(
            ctx, "sensor", coord,
            safe_approach_height=20.0, measurement_height=50.0,
        )

        ctx.board.move_to_labware.assert_not_called()
        assert len(ctx.board.move.call_args_list) == 2
        first_call, second_call = ctx.board.move.call_args_list
        assert first_call.args == ("sensor", (10.0, 20.0, 20.0))
        assert first_call.kwargs == {"travel_z": 20.0}
        assert second_call.args == ("sensor", (10.0, 20.0, 50.0))
        assert second_call.kwargs == {}

    def test_safe_approach_height_override_must_not_sit_below_action_height(self):
        """In positive-down Z, approach z must be <= action z. An approach
        z larger than action z means travel below the action height."""
        ctx, instr = _mock_ctx(measurement_height=3.0)
        coord = Coordinate3D(x=10.0, y=20.0, z=30.0)

        with pytest.raises(ValueError, match="safe_approach_height"):
            approach_and_descend(
                ctx, "sensor", coord,
                safe_approach_height=60.0, measurement_height=50.0,
            )
