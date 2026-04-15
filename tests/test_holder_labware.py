from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from deck import (
    BoundingBoxGeometry,
    Coordinate3D,
    Deck,
    DeckLoaderError,
    LabwareSlot,
    TipDisposal,
    Vial,
    VialHolder,
    WellPlate,
    WellPlateHolder,
)
from deck.loader import load_deck_from_yaml, load_deck_from_yaml_safe
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


def test_holder_seat_offset_metadata_is_encoded():
    vial_holder = VialHolder(
        name="vial_holder",
        location=Coordinate3D(x=0.0, y=0.0, z=0.0),
    )
    plate_holder = WellPlateHolder(
        name="plate_holder",
        location=Coordinate3D(x=0.0, y=0.0, z=0.0),
    )

    assert vial_holder.height_mm == pytest.approx(35.1)
    assert vial_holder.labware_support_height_mm == pytest.approx(35.1)
    assert vial_holder.labware_seat_height_from_bottom_mm == pytest.approx(18.0)
    assert vial_holder.geometry == BoundingBoxGeometry(
        length_mm=36.2,
        width_mm=300.2,
        height_mm=35.1,
    )

    # Keep the existing collision-envelope height, while separately storing
    # the base/support geometry that defines the seated plate offset.
    assert plate_holder.height_mm == pytest.approx(14.8)
    assert plate_holder.labware_support_height_mm == pytest.approx(10.0)
    assert plate_holder.labware_seat_height_from_bottom_mm == pytest.approx(5.0)
    assert plate_holder.geometry == BoundingBoxGeometry(
        length_mm=100.0,
        width_mm=155.0,
        height_mm=14.8,
    )


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
        assert isinstance(deck["waste"], TipDisposal)
        assert isinstance(deck["slide_holder"], WellPlateHolder)
        assert isinstance(deck["vial_holder"], VialHolder)
        assert deck["waste"].location.z == pytest.approx(80.0)
        assert deck.resolve("slide_holder.plate") == Coordinate3D(x=51.0, y=61.0, z=12.0)
        assert deck.resolve("vial_holder.vial_1") == Coordinate3D(x=71.0, y=81.0, z=75.0)
    finally:
        Path(path).unlink(missing_ok=True)


def test_vial_bottom_and_top_center_helpers():
    vial = Vial(
        name="v1",
        height_mm=57.0,
        diameter_mm=28.0,
        location=Coordinate3D(x=10.0, y=20.0, z=100.0),
        capacity_ul=20000.0,
        working_volume_ul=15000.0,
    )
    assert vial.get_bottom_center() == Coordinate3D(x=10.0, y=20.0, z=100.0)
    assert vial.get_top_center() == Coordinate3D(x=10.0, y=20.0, z=157.0)


def test_vial_holder_with_name_references_resolves_typed_vials():
    yaml_str = """
labware:
  vial_1:
    type: vial
    name: vial_1
    model_name: 20ml_vial
    height_mm: 57.0
    diameter_mm: 28.0
    location:
      x: 17.1
      y: 0.9
      z: 182.0
    capacity_ul: 20000.0
    working_volume_ul: 6500.0
  vial_holder:
    type: vial_holder
    name: vial_holder
    location:
      x: 17.1
      y: 132.9
      z: 164.0
    vials:
      - vial_1
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        deck = load_deck_from_yaml(path)
        holder = deck["vial_holder"]
        vial = deck["vial_1"]

        assert isinstance(holder, VialHolder)
        assert isinstance(vial, Vial)
        # Typed API
        assert "vial_1" in holder.vials
        assert holder.vials["vial_1"] is vial
        # Back-reference
        assert vial.holder is holder
        # Convenience helper: top-Z of the held vial
        assert holder.get_vial_top_z("vial_1") == pytest.approx(182.0 + 57.0)
        # Dotted lookup resolves via contained_labware (keyed by labware name).
        assert deck.resolve("vial_holder.vial_1") == Coordinate3D(x=17.1, y=0.9, z=182.0)
        # .holder is excluded from model_dump
        dumped = vial.model_dump()
        assert "holder" not in dumped
    finally:
        Path(path).unlink(missing_ok=True)


def test_well_plate_holder_with_name_reference_resolves_typed_plate():
    yaml_str = """
labware:
  plate_1:
    type: well_plate
    name: plate_1
    model_name: panda_96_wellplate
    height_mm: 14.35
    rows: 2
    columns: 2
    calibration:
      a1:
        x: 221.75
        y: 78.5
        z: 188.0
      a2:
        x: 230.75
        y: 78.5
        z: 188.0
    x_offset_mm: 9.0
    y_offset_mm: 9.0
  plate_holder:
    type: well_plate_holder
    name: plate_holder
    location:
      x: 221.75
      y: 78.5
      z: 183.0
    well_plate: plate_1
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        deck = load_deck_from_yaml(path)
        holder = deck["plate_holder"]
        plate = deck["plate_1"]

        assert isinstance(holder, WellPlateHolder)
        assert isinstance(plate, WellPlate)
        assert holder.well_plate is plate
        assert plate.holder is holder
        # Convenience helper: top-Z of the plate
        assert holder.get_plate_top_z() == pytest.approx(188.0 + 14.35)
        # Dotted lookup resolves via contained_labware (keyed by labware name).
        assert deck.resolve("plate_holder.plate_1.A1") == Coordinate3D(x=221.75, y=78.5, z=188.0)
        assert deck.resolve("plate_holder.plate_1.B2") == Coordinate3D(x=230.75, y=87.5, z=188.0)
    finally:
        Path(path).unlink(missing_ok=True)


def test_vial_holder_rejects_z_drift_against_holder_geometry():
    """Loader must error if a referenced vial's z is inconsistent with
    holder.location.z + labware_seat_height_from_bottom_mm."""
    yaml_str = """
labware:
  vial_1:
    type: vial
    name: vial_1
    height_mm: 57.0
    diameter_mm: 28.0
    location:
      x: 17.1
      y: 0.9
      z: 999.0   # wrong: should be 164 + 18 = 182
    capacity_ul: 20000.0
    working_volume_ul: 6500.0
  vial_holder:
    type: vial_holder
    name: vial_holder
    location: {x: 17.1, y: 132.9, z: 164.0}
    vials: [vial_1]
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        with pytest.raises(DeckLoaderError, match=r"inconsistent with VialHolder"):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_vial_holder_errors_on_unknown_reference():
    yaml_str = """
labware:
  vial_holder:
    type: vial_holder
    name: vial_holder
    location: {x: 0.0, y: 0.0, z: 164.0}
    vials: [nonexistent_vial]
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        with pytest.raises(DeckLoaderError, match=r"references unknown vial 'nonexistent_vial'"):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_vial_holder_errors_on_wrong_type_reference():
    yaml_str = """
labware:
  plate_1:
    type: well_plate
    name: plate_1
    height_mm: 14.35
    rows: 1
    columns: 1
    calibration:
      a1: {x: 0.0, y: 0.0, z: 182.0}
      a2: {x: 9.0, y: 0.0, z: 182.0}
    x_offset_mm: 9.0
    y_offset_mm: 9.0
  vial_holder:
    type: vial_holder
    name: vial_holder
    location: {x: 0.0, y: 0.0, z: 164.0}
    vials: [plate_1]
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        with pytest.raises(DeckLoaderError, match=r"which is not a vial \(got WellPlate\)"):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_vial_cannot_be_referenced_by_two_holders():
    yaml_str = """
labware:
  vial_1:
    type: vial
    name: vial_1
    height_mm: 57.0
    diameter_mm: 28.0
    location: {x: 0.0, y: 0.0, z: 182.0}
    capacity_ul: 20000.0
    working_volume_ul: 6500.0
  holder_a:
    type: vial_holder
    name: holder_a
    location: {x: 0.0, y: 0.0, z: 164.0}
    vials: [vial_1]
  holder_b:
    type: vial_holder
    name: holder_b
    location: {x: 0.0, y: 0.0, z: 164.0}
    vials: [vial_1]
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        with pytest.raises(DeckLoaderError, match=r"referenced by both 'holder_a' and 'holder_b'"):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_yaml_rejects_legacy_nested_vials_dict_form():
    """The old form where vial_holder embedded vial dicts must now fail."""
    yaml_str = """
labware:
  vial_holder:
    type: vial_holder
    name: vial_holder
    location: {x: 0.0, y: 0.0, z: 164.0}
    vials:
      vial_1:
        model_name: 20ml_vial
        height_mm: 57.0
        diameter_mm: 28.0
        location: {x: 0.0, y: 0.0}
        capacity_ul: 20000.0
        working_volume_ul: 6500.0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        # Schema now expects List[str] for `vials`; a dict payload fails
        # Pydantic's list-input validation.
        with pytest.raises(ValidationError):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_yaml_rejects_legacy_nested_well_plate_dict_form():
    """A plate embedded inside well_plate_holder as a dict must now fail."""
    yaml_str = """
labware:
  plate_holder:
    type: well_plate_holder
    name: plate_holder
    location: {x: 0.0, y: 0.0, z: 183.0}
    well_plate:
      model_name: some_plate
      rows: 1
      columns: 1
      calibration:
        a1: {x: 0.0, y: 0.0}
        a2: {x: 9.0, y: 0.0}
      x_offset_mm: 9.0
      y_offset_mm: 9.0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        # Schema now expects Optional[str] for `well_plate`; a dict payload
        # fails Pydantic's str-input validation.
        with pytest.raises(ValidationError):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


def _make_plate(
    *,
    name: str = "plate_1",
    z: float = 188.0,
    height_mm: float | None = 14.35,
) -> str:
    """Build a minimal 1x1 well_plate YAML entry (as a literal block)."""
    height_line = f"    height_mm: {height_mm}\n" if height_mm is not None else ""
    return f"""\
  {name}:
    type: well_plate
    name: {name}
{height_line}    rows: 1
    columns: 1
    calibration:
      a1: {{x: 0.0, y: 0.0, z: {z}}}
      a2: {{x: 9.0, y: 0.0, z: {z}}}
    x_offset_mm: 9.0
    y_offset_mm: 9.0
"""


def test_well_plate_holder_errors_on_unknown_reference():
    yaml_str = """
labware:
  plate_holder:
    type: well_plate_holder
    name: plate_holder
    location: {x: 0.0, y: 0.0, z: 183.0}
    well_plate: nonexistent_plate
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        with pytest.raises(DeckLoaderError, match=r"references unknown well_plate 'nonexistent_plate'"):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_well_plate_holder_errors_on_wrong_type_reference():
    yaml_str = f"""
labware:
  vial_1:
    type: vial
    name: vial_1
    height_mm: 57.0
    diameter_mm: 28.0
    location: {{x: 0.0, y: 0.0, z: 188.0}}
    capacity_ul: 20000.0
    working_volume_ul: 6500.0
  plate_holder:
    type: well_plate_holder
    name: plate_holder
    location: {{x: 0.0, y: 0.0, z: 183.0}}
    well_plate: vial_1
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        with pytest.raises(DeckLoaderError, match=r"which is not a well_plate \(got Vial\)"):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_well_plate_cannot_be_referenced_by_two_holders():
    yaml_str = f"""
labware:
{_make_plate(name='plate_1', z=188.0)}
  holder_a:
    type: well_plate_holder
    name: holder_a
    location: {{x: 0.0, y: 0.0, z: 183.0}}
    well_plate: plate_1
  holder_b:
    type: well_plate_holder
    name: holder_b
    location: {{x: 0.0, y: 0.0, z: 183.0}}
    well_plate: plate_1
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        with pytest.raises(DeckLoaderError, match=r"referenced by both 'holder_a' and 'holder_b'"):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_well_plate_holder_rejects_z_drift_against_holder_geometry():
    """Drift between plate A1 z and holder seat must be rejected (plate branch)."""
    yaml_str = f"""
labware:
{_make_plate(name='plate_1', z=999.0)}
  plate_holder:
    type: well_plate_holder
    name: plate_holder
    location: {{x: 0.0, y: 0.0, z: 183.0}}
    well_plate: plate_1
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        with pytest.raises(DeckLoaderError, match=r"inconsistent with WellPlateHolder"):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_well_plate_holder_rejects_held_plate_without_height_mm():
    """A plate referenced by a holder must define height_mm for top-Z math."""
    yaml_str = f"""
labware:
{_make_plate(name='plate_1', z=188.0, height_mm=None)}
  plate_holder:
    type: well_plate_holder
    name: plate_holder
    location: {{x: 0.0, y: 0.0, z: 183.0}}
    well_plate: plate_1
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        with pytest.raises(DeckLoaderError, match=r"has no height_mm"):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_well_plate_holder_model_dump_excludes_holder_back_reference():
    """WellPlate.holder must be excluded from model_dump (parallel to Vial.holder)."""
    yaml_str = f"""
labware:
{_make_plate(name='plate_1', z=188.0)}
  plate_holder:
    type: well_plate_holder
    name: plate_holder
    location: {{x: 0.0, y: 0.0, z: 183.0}}
    well_plate: plate_1
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        deck = load_deck_from_yaml(path)
        plate = deck["plate_1"]
        assert plate.holder is deck["plate_holder"]
        assert "holder" not in plate.model_dump()
    finally:
        Path(path).unlink(missing_ok=True)


def test_get_plate_top_z_raises_when_no_plate_attached():
    """get_plate_top_z must raise when the holder has no well_plate."""
    holder = WellPlateHolder(
        name="empty_holder",
        location=Coordinate3D(x=0.0, y=0.0, z=183.0),
    )
    with pytest.raises(ValueError, match=r"does not contain a well plate"):
        holder.get_plate_top_z()


def test_well_plate_holder_rejects_plate_without_height_mm_at_construction():
    """Holder construction itself must reject a plate missing height_mm.

    The loader also rejects it earlier with a more YAML-oriented message, but
    the invariant is enforced on the type so programmatic callers get the
    same guarantee.
    """
    plate = WellPlate(
        name="plate_1",
        rows=1,
        columns=1,
        wells={"A1": Coordinate3D(x=0.0, y=0.0, z=188.0)},
    )
    with pytest.raises(ValidationError, match=r"has no height_mm"):
        WellPlateHolder(
            name="plate_holder",
            location=Coordinate3D(x=0.0, y=0.0, z=183.0),
            well_plate=plate,
        )


def test_vial_holder_accepts_drift_just_under_tolerance():
    """Drift under 1 µm must be accepted (below gantry precision)."""
    yaml_str = """
labware:
  vial_1:
    type: vial
    name: vial_1
    height_mm: 57.0
    diameter_mm: 28.0
    location: {x: 0.0, y: 0.0, z: 182.0000005}  # 5e-7 mm drift
    capacity_ul: 20000.0
    working_volume_ul: 6500.0
  vial_holder:
    type: vial_holder
    name: vial_holder
    location: {x: 0.0, y: 0.0, z: 164.0}
    vials: [vial_1]
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        deck = load_deck_from_yaml(path)
        assert "vial_1" in deck["vial_holder"].vials
    finally:
        Path(path).unlink(missing_ok=True)


def test_vial_holder_rejects_drift_just_over_tolerance():
    """Drift over 1 µm must be rejected — guards the tolerance boundary."""
    yaml_str = """
labware:
  vial_1:
    type: vial
    name: vial_1
    height_mm: 57.0
    diameter_mm: 28.0
    location: {x: 0.0, y: 0.0, z: 182.000002}  # 2e-6 mm drift
    capacity_ul: 20000.0
    working_volume_ul: 6500.0
  vial_holder:
    type: vial_holder
    name: vial_holder
    location: {x: 0.0, y: 0.0, z: 164.0}
    vials: [vial_1]
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        with pytest.raises(DeckLoaderError, match=r"inconsistent with VialHolder"):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_deck_yaml_load_name_expands_from_definitions_registry():
    """A deck YAML may reference a definition via `load_name:` and supply only
    the user-specific fields (typically just `location`)."""
    yaml_str = """
labware:
  my_vials:
    load_name: ursa_vial_holder
    location:
      x: 17.1
      y: 132.9
      z: 164.0
  my_plate_holder:
    load_name: ursa_wellplate_holder_conductive
    location:
      x: 50.0
      y: 60.0
      z: 12.0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        deck = load_deck_from_yaml(path)

        vials = deck["my_vials"]
        assert isinstance(vials, VialHolder)
        assert vials.name == "my_vials"  # defaulted to deck key
        assert vials.length_mm == pytest.approx(36.2)
        assert vials.width_mm == pytest.approx(300.2)
        assert vials.height_mm == pytest.approx(35.1)
        assert vials.labware_seat_height_from_bottom_mm == pytest.approx(18.0)
        assert vials.slot_count == 9
        assert vials.location == Coordinate3D(x=17.1, y=132.9, z=164.0)

        plate_holder = deck["my_plate_holder"]
        assert isinstance(plate_holder, WellPlateHolder)
        assert plate_holder.name == "my_plate_holder"
        assert plate_holder.length_mm == pytest.approx(100.0)
        assert plate_holder.width_mm == pytest.approx(155.0)
        assert plate_holder.height_mm == pytest.approx(14.8)
        assert plate_holder.labware_seat_height_from_bottom_mm == pytest.approx(5.0)
    finally:
        Path(path).unlink(missing_ok=True)


def test_deck_yaml_unknown_load_name_raises_clear_error():
    yaml_str = """
labware:
  broken:
    load_name: no_such_definition
    location: {x: 0.0, y: 0.0, z: 0.0}
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        with pytest.raises(
            DeckLoaderError,
            match=r"Unknown `load_name: 'no_such_definition'`",
        ):
            load_deck_from_yaml(path)
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


# ─── Programmatic construction + validate_assignment behavior ──────────────
#
# These tests exercise the holder validators directly (no deck YAML) so that
# invariants enforced on the type — not just via the loader — have regression
# coverage. Several of these paths are unreachable from the loader but still
# matter for unit tests, calibration scripts, and future programmatic APIs.


def _make_vial(name: str = "v1", z: float = 182.0, **overrides) -> Vial:
    """Build a minimal Vial at a holder's seat z (164.0 + 18.0)."""
    defaults = dict(
        name=name,
        height_mm=57.0,
        diameter_mm=28.0,
        location=Coordinate3D(x=0.0, y=0.0, z=z),
        capacity_ul=20000.0,
        working_volume_ul=6500.0,
    )
    defaults.update(overrides)
    return Vial(**defaults)


def test_vial_holder_programmatic_drift_rejects_at_construction():
    """Constructing a holder with a drifty vial raises at model validation."""
    drifty_vial = _make_vial(name="v1", z=999.0)  # seat is at 164+18 = 182
    with pytest.raises(ValidationError, match=r"inconsistent with VialHolder"):
        VialHolder(
            name="h",
            location=Coordinate3D(x=0.0, y=0.0, z=164.0),
            vials={"v1": drifty_vial},
        )


def test_vial_holder_programmatic_key_name_mismatch_rejected():
    """Dict key must match vial.name; caught by the type validator."""
    vial = _make_vial(name="actual_name")
    with pytest.raises(ValidationError, match=r"key 'alias' must match vial\.name 'actual_name'"):
        VialHolder(
            name="h",
            location=Coordinate3D(x=0.0, y=0.0, z=164.0),
            vials={"alias": vial},
        )


def test_vial_holder_cross_holder_ownership_rejected_at_type_level():
    """Two holders cannot own the same vial even without the loader's claimed dict."""
    shared_vial = _make_vial()
    _ = VialHolder(
        name="first",
        location=Coordinate3D(x=0.0, y=0.0, z=164.0),
        vials={"v1": shared_vial},
    )
    # first holder claimed ownership; second must now reject the vial.
    with pytest.raises(ValidationError, match=r"already held by another VialHolder \('first'\)"):
        VialHolder(
            name="second",
            location=Coordinate3D(x=0.0, y=0.0, z=164.0),
            vials={"v1": shared_vial},
        )


def test_vial_holder_reassignment_clears_orphan_back_references():
    """Reassigning holder.vials must clear .holder on vials no longer held."""
    v1 = _make_vial(name="v1")
    v2 = _make_vial(name="v2")
    holder = VialHolder(
        name="h",
        location=Coordinate3D(x=0.0, y=0.0, z=164.0),
        vials={"v1": v1, "v2": v2},
    )
    assert v1.holder is holder
    assert v2.holder is holder

    # Reassign to keep only v1; v2 should become orphaned.
    holder.vials = {"v1": v1}
    assert v1.holder is holder
    assert v2.holder is None


def test_vial_holder_contained_labware_is_derived_from_vials():
    """contained_labware is a read-through view of vials (per-call copy)."""
    v1 = _make_vial(name="v1")
    holder = VialHolder(
        name="h",
        location=Coordinate3D(x=0.0, y=0.0, z=164.0),
        vials={"v1": v1},
    )
    assert holder.contained_labware == {"v1": v1}
    # Mutating the returned dict does not affect internal state —
    # the property returns a fresh dict each call.
    holder.contained_labware["ghost"] = v1
    assert "ghost" not in holder.contained_labware


def test_vial_holder_validate_assignment_reruns_drift_check():
    """Post-construction reassignment of vials re-runs the drift validator.

    Note: pydantic v2's ``validate_assignment`` does NOT roll back the field
    on validation failure — the field is set, then the validator raises.
    Callers are expected to treat the holder as untrusted state after a
    failed assignment. This test only pins that the validator DOES fire.
    """
    v1 = _make_vial(name="v1")
    holder = VialHolder(
        name="h",
        location=Coordinate3D(x=0.0, y=0.0, z=164.0),
        vials={"v1": v1},
    )
    drifty = _make_vial(name="v2", z=999.0)
    with pytest.raises(ValidationError, match=r"inconsistent with VialHolder"):
        holder.vials = {"v1": v1, "v2": drifty}


def test_well_plate_holder_accepts_drift_just_under_tolerance():
    """Plate-side parity with the vial tolerance boundary test."""
    plate = WellPlate(
        name="p",
        height_mm=14.35,
        rows=1,
        columns=1,
        wells={"A1": Coordinate3D(x=0.0, y=0.0, z=188.0000005)},  # 5e-7 mm drift
    )
    holder = WellPlateHolder(
        name="h",
        location=Coordinate3D(x=0.0, y=0.0, z=183.0),
        well_plate=plate,
    )
    assert holder.well_plate is plate


def test_well_plate_holder_rejects_drift_just_over_tolerance():
    plate = WellPlate(
        name="p",
        height_mm=14.35,
        rows=1,
        columns=1,
        wells={"A1": Coordinate3D(x=0.0, y=0.0, z=188.000002)},  # 2e-6 mm drift
    )
    with pytest.raises(ValidationError, match=r"inconsistent with WellPlateHolder"):
        WellPlateHolder(
            name="h",
            location=Coordinate3D(x=0.0, y=0.0, z=183.0),
            well_plate=plate,
        )


def test_well_plate_holder_reassignment_clears_back_reference():
    """Setting well_plate=None clears the previous plate's .holder."""
    plate = WellPlate(
        name="p",
        height_mm=14.35,
        rows=1,
        columns=1,
        wells={"A1": Coordinate3D(x=0.0, y=0.0, z=188.0)},
    )
    holder = WellPlateHolder(
        name="h",
        location=Coordinate3D(x=0.0, y=0.0, z=183.0),
        well_plate=plate,
    )
    assert plate.holder is holder
    holder.well_plate = None
    assert plate.holder is None


def test_load_deck_from_yaml_safe_passes_through_deck_loader_error():
    """Already-formatted DeckLoaderErrors must NOT be wrapped / reformatted."""
    yaml_str = """
labware:
  vial_holder:
    type: vial_holder
    name: h
    location: {x: 0.0, y: 0.0, z: 164.0}
    vials: [nonexistent_vial]
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_str)
        path = handle.name

    try:
        raw_msg = None
        try:
            load_deck_from_yaml(path)
        except DeckLoaderError as raw:
            raw_msg = str(raw)

        safe_msg = None
        try:
            load_deck_from_yaml_safe(path)
        except DeckLoaderError as safe:
            safe_msg = str(safe)

        assert raw_msg is not None and safe_msg is not None
        # The safe wrapper must not prepend its generic envelope; the
        # resolver's actionable message should come through verbatim.
        assert safe_msg == raw_msg
    finally:
        Path(path).unlink(missing_ok=True)


def test_load_deck_from_yaml_safe_propagates_unexpected_exceptions(monkeypatch):
    """Unknown exceptions must propagate raw, not be wrapped as DeckLoaderError."""
    from deck import loader as loader_mod

    def explode(*args, **kwargs):
        raise RuntimeError("unexpected programming error")

    monkeypatch.setattr(loader_mod, "load_deck_from_yaml", explode)

    with pytest.raises(RuntimeError, match=r"unexpected programming error"):
        loader_mod.load_deck_from_yaml_safe("irrelevant.yaml")
