"""Tests for TipRack labware model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from deck.labware import Coordinate3D
from deck.labware.tip_rack import TipRack


def _make_tip_rack(**overrides) -> TipRack:
    """Build a minimal 2x3 TipRack for testing."""
    defaults = dict(
        name="test_rack",
        model_name="opentrons_96_tiprack_300ul",
        rows=2,
        columns=3,
        length_mm=127.71,
        width_mm=85.43,
        height_mm=64.69,
        wells={
            "A1": Coordinate3D(x=0.0, y=0.0, z=-5.0),
            "A2": Coordinate3D(x=9.0, y=0.0, z=-5.0),
            "A3": Coordinate3D(x=18.0, y=0.0, z=-5.0),
            "B1": Coordinate3D(x=0.0, y=-9.0, z=-5.0),
            "B2": Coordinate3D(x=9.0, y=-9.0, z=-5.0),
            "B3": Coordinate3D(x=18.0, y=-9.0, z=-5.0),
        },
    )
    defaults.update(overrides)
    return TipRack(**defaults)


class TestTipRackModel:

    def test_valid_construction(self):
        rack = _make_tip_rack()
        assert rack.name == "test_rack"
        assert rack.model_name == "opentrons_96_tiprack_300ul"
        assert rack.rows == 2
        assert rack.columns == 3
        assert len(rack.wells) == 6

    def test_get_location_returns_correct_coordinate(self):
        rack = _make_tip_rack()
        coord = rack.get_location("A1")
        assert coord.x == pytest.approx(0.0)
        assert coord.y == pytest.approx(0.0)
        assert coord.z == pytest.approx(-5.0)

    def test_get_location_specific_well(self):
        rack = _make_tip_rack()
        coord = rack.get_location("B2")
        assert coord.x == pytest.approx(9.0)
        assert coord.y == pytest.approx(-9.0)

    def test_get_location_unknown_well_raises(self):
        rack = _make_tip_rack()
        with pytest.raises(KeyError, match="Unknown well ID 'Z9'"):
            rack.get_location("Z9")

    def test_get_location_none_raises(self):
        rack = _make_tip_rack()
        with pytest.raises(KeyError, match="location_id is required"):
            rack.get_location()

    def test_get_initial_position_returns_a1(self):
        rack = _make_tip_rack()
        initial = rack.get_initial_position()
        assert initial == rack.wells["A1"]

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            _make_tip_rack(unknown_field=42)

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            _make_tip_rack(name="")

    def test_requires_a1_well(self):
        with pytest.raises(ValidationError, match="A1"):
            TipRack(
                name="bad",
                model_name="m",
                rows=1,
                columns=1,
                length_mm=10.0,
                width_mm=10.0,
                height_mm=10.0,
                wells={"B1": Coordinate3D(x=0.0, y=0.0, z=0.0)},
            )

    def test_well_count_must_match_rows_columns(self):
        with pytest.raises(ValidationError, match="rows.*columns"):
            TipRack(
                name="bad",
                model_name="m",
                rows=2,
                columns=2,
                length_mm=10.0,
                width_mm=10.0,
                height_mm=10.0,
                wells={"A1": Coordinate3D(x=0.0, y=0.0, z=0.0)},
            )

    def test_positive_dimensions_required(self):
        with pytest.raises(ValidationError):
            _make_tip_rack(length_mm=-1.0)

    def test_no_volume_fields(self):
        """TipRack should not have capacity_ul or working_volume_ul."""
        rack = _make_tip_rack()
        assert not hasattr(rack, "capacity_ul")
        assert not hasattr(rack, "working_volume_ul")
