import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from deck import (
    Coordinate3D,
    Deck,
    LabwareSlot,
    TipDisposal,
    TipHolder,
    VialHolder,
    WellPlateHolder,
)
from deck.loader import load_deck_from_yaml
from gantry.gantry_config import GantryConfig, HomingStrategy, WorkingVolume
from validation.bounds import validate_deck_positions


def _make_gantry() -> GantryConfig:
    return GantryConfig(
        serial_port="/dev/ttyUSB0",
        homing_strategy=HomingStrategy.STANDARD,
        total_z_height=90.0,
        working_volume=WorkingVolume(
            x_min=0.0,
            x_max=300.0,
            y_min=0.0,
            y_max=300.0,
            z_min=0.0,
            z_max=100.0,
        ),
    )


def test_tip_holder_uses_fixed_dimensions_and_anchor_location():
    holder = TipHolder(
        name="tips",
        location=Coordinate3D(x=10.0, y=20.0, z=30.0),
    )

    assert holder.length_mm == pytest.approx(138.0)
    assert holder.width_mm == pytest.approx(66.0)
    assert holder.height_mm == pytest.approx(22.0)
    assert holder.get_initial_position() == Coordinate3D(x=10.0, y=20.0, z=30.0)
    assert holder.get_location() == Coordinate3D(x=10.0, y=20.0, z=30.0)


def test_well_plate_holder_resolves_named_slot_positions():
    holder = WellPlateHolder(
        name="slide_holder",
        location=Coordinate3D(x=50.0, y=60.0, z=12.0),
        slots={
            "plate": LabwareSlot(
                location=Coordinate3D(x=51.0, y=61.0, z=12.0),
                supported_labware_types=("well_plate",),
            ),
        },
    )

    assert holder.length_mm == pytest.approx(100.0)
    assert holder.width_mm == pytest.approx(155.0)
    assert holder.height_mm == pytest.approx(14.8)
    assert holder.get_location("plate") == Coordinate3D(x=51.0, y=61.0, z=12.0)
    assert holder.iter_positions()["plate"] == Coordinate3D(x=51.0, y=61.0, z=12.0)


def test_vial_holder_rejects_more_slots_than_capacity():
    too_many_slots = {
        f"vial_{index}": LabwareSlot(
            location=Coordinate3D(x=float(index), y=0.0, z=0.0),
            supported_labware_types=("vial",),
        )
        for index in range(1, 11)
    }

    with pytest.raises(ValidationError, match="slot_count"):
        VialHolder(
            name="vial_holder",
            location=Coordinate3D(x=0.0, y=0.0, z=0.0),
            slots=too_many_slots,
        )


def test_tip_disposal_resolves_from_deck():
    deck = Deck(
        {
            "waste": TipDisposal(
                name="waste",
                location=Coordinate3D(x=100.0, y=110.0, z=15.0),
            ),
        }
    )

    assert deck.resolve("waste") == Coordinate3D(x=100.0, y=110.0, z=15.0)


def test_load_holder_labware_from_yaml():
    yaml_str = """
labware:
  tips:
    type: tip_holder
    name: tips
    location:
      x: 10.0
      y: 20.0
      z: 30.0
  waste:
    type: tip_disposal
    name: waste
    location:
      x: 25.0
      y: 35.0
    height: 10.0
  slide_holder:
    type: well_plate_holder
    name: slide_holder
    location:
      x: 50.0
      y: 60.0
      z: 12.0
    slots:
      plate:
        location:
          x: 51.0
          y: 61.0
        supported_labware_types:
          - well_plate
  vial_holder:
    type: vial_holder
    name: vial_holder
    location:
      x: 70.0
      y: 80.0
    height: 15.0
    slots:
      vial_1:
        location:
          x: 71.0
          y: 81.0
        supported_labware_types:
          - vial
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        deck = load_deck_from_yaml(path, total_z_height=90.0)
        assert isinstance(deck["tips"], TipHolder)
        assert isinstance(deck["waste"], TipDisposal)
        assert isinstance(deck["slide_holder"], WellPlateHolder)
        assert isinstance(deck["vial_holder"], VialHolder)
        assert deck["waste"].location.z == pytest.approx(80.0)
        assert deck.resolve("slide_holder.plate") == Coordinate3D(x=51.0, y=61.0, z=12.0)
        assert deck.resolve("vial_holder.vial_1") == Coordinate3D(x=71.0, y=81.0, z=75.0)
    finally:
        Path(path).unlink(missing_ok=True)


def test_holder_slots_participate_in_bounds_validation():
    gantry = _make_gantry()
    holder = VialHolder(
        name="vial_holder",
        location=Coordinate3D(x=20.0, y=20.0, z=20.0),
        slots={
            "vial_1": LabwareSlot(
                location=Coordinate3D(x=301.0, y=20.0, z=20.0),
                supported_labware_types=("vial",),
            )
        },
    )
    deck = Deck({"vials": holder})

    violations = validate_deck_positions(gantry, deck)

    assert len(violations) == 1
    assert violations[0].labware_key == "vials"
    assert violations[0].position_id == "vial_1"
    assert violations[0].axis == "x"
    assert violations[0].bound_name == "x_max"
