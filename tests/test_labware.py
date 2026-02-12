import pytest

from pydantic import ValidationError

from src.labware import (
    Labware,
    WellPlate,
    Vial,
    Coordinate3D,
    generate_wells_from_offsets,
)


def test_labware_requires_name_and_locations():
    """Base Labware requires a name and at least one location."""
    # Missing name should fail
    with pytest.raises(ValidationError):
        Labware(name="", locations={})

    # Empty locations should fail
    with pytest.raises(ValidationError):
        Labware(name="empty", locations={})


def test_labware_get_location_success_and_failure():
    """Labware exposes a safe lookup API for locations."""
    locations = {
        "A1": Coordinate3D(x=-10.0, y=-20.0, z=-5.0),
    }
    labware = Labware(name="generic", locations=locations)

    # Happy path: known location
    center = labware.get_location("A1")
    assert isinstance(center, Coordinate3D)
    assert center.x == pytest.approx(-10.0)
    assert center.y == pytest.approx(-20.0)
    assert center.z == pytest.approx(-5.0)

    # Unknown ID should raise a clear error
    with pytest.raises(KeyError, match="Unknown location ID 'B1'"):
        labware.get_location("B1")


def test_well_plate_sbs_96_dimensions_and_well_lookup():
    """WellPlate captures SBS 96 dimensions and resolves wells by ID."""
    wells = {
        "A1": Coordinate3D(x=-10.0, y=-10.0, z=-15.0),
        "B1": Coordinate3D(x=-10.0, y=-20.0, z=-15.0),
    }

    plate = WellPlate(
        name="SBS_96",
        length_mm=127.71,
        width_mm=85.43,
        height_mm=14.10,
        rows=8,
        columns=12,
        wells=wells,
    )

    assert plate.name == "SBS_96"
    assert plate.length_mm == pytest.approx(127.71)
    assert plate.width_mm == pytest.approx(85.43)
    assert plate.height_mm == pytest.approx(14.10)
    assert plate.rows == 8
    assert plate.columns == 12

    # Well lookup using ergonomic API
    a1_center = plate.get_well_center("A1")
    assert a1_center.x == pytest.approx(-10.0)
    assert a1_center.y == pytest.approx(-10.0)
    assert a1_center.z == pytest.approx(-15.0)

    # Falling back to base Labware API should also work
    assert plate.get_location("A1") == a1_center

    # Initial position for a well plate should be A1
    initial = plate.get_initial_position()
    assert initial == a1_center

    # Invalid well ID should raise a clear error
    with pytest.raises(KeyError, match="Unknown well ID 'Z9'"):
        plate.get_well_center("Z9")


def test_well_plate_requires_positive_dimensions_and_wells():
    """WellPlate validates dimensions and requires at least one well."""
    with pytest.raises(ValidationError):
        WellPlate(
            name="invalid_plate",
            length_mm=-1.0,
            width_mm=85.43,
            height_mm=14.10,
            rows=8,
            columns=12,
            wells={},
        )

    # Missing A1 should also fail, since A1 is the anchor position
    with pytest.raises(ValidationError):
        WellPlate(
            name="missing_a1",
            length_mm=127.71,
            width_mm=85.43,
            height_mm=14.10,
            rows=8,
            columns=12,
            wells={"B1": Coordinate3D(x=-10.0, y=-20.0, z=-15.0)},
        )


def test_vial_rack_dimensions_and_vial_lookup():
    """Vial labware captures vial geometry and resolves vial positions by ID."""
    vials = {
        "A1": Coordinate3D(x=-30.0, y=-40.0, z=-20.0),
        "A2": Coordinate3D(x=-60.0, y=-40.0, z=-20.0),
    }

    vial_labware = Vial(
        name="standard_vial_rack",
        height_mm=66.75,
        diameter_mm=28.00,
        center=Coordinate3D(x=-30.0, y=-40.0, z=-20.0),
        vials=vials,
    )

    assert vial_labware.name == "standard_vial_rack"
    assert vial_labware.height_mm == pytest.approx(66.75)
    assert vial_labware.diameter_mm == pytest.approx(28.00)

    a1_center = vial_labware.get_vial_center("A1")
    assert a1_center.x == pytest.approx(-30.0)
    assert a1_center.y == pytest.approx(-40.0)
    assert a1_center.z == pytest.approx(-20.0)

    # Base Labware API should also work
    assert vial_labware.get_location("A1") == a1_center

    # Initial position for vial labware should be the configured center
    initial = vial_labware.get_initial_position()
    assert initial == Coordinate3D(x=-30.0, y=-40.0, z=-20.0)

    with pytest.raises(KeyError, match="Unknown vial ID 'B1'"):
        vial_labware.get_vial_center("B1")


def test_vial_requires_positive_geometry_and_vials():
    """Vial validates geometry and requires at least one vial position."""
    with pytest.raises(ValidationError):
        Vial(
            name="invalid_vial_rack",
            height_mm=0.0,
            diameter_mm=28.0,
            vials={},
        )


def test_generate_wells_from_offsets():
    """Generate a small 2x2 well layout from A1 anchor and offsets."""
    row_labels = ["A", "B"]
    column_indices = [1, 2]
    a1_center = Coordinate3D(x=0.0, y=0.0, z=-15.0)

    wells = generate_wells_from_offsets(
        row_labels=row_labels,
        column_indices=column_indices,
        a1_center=a1_center,
        x_offset_mm=10.0,
        y_offset_mm=-5.0,
        rounding_decimals=3,
    )

    # Expect 4 wells: A1, A2, B1, B2
    assert set(wells.keys()) == {"A1", "A2", "B1", "B2"}

    # A1 is the anchor
    assert wells["A1"].x == pytest.approx(0.0)
    assert wells["A1"].y == pytest.approx(0.0)
    assert wells["A1"].z == pytest.approx(-15.0)

    # A2: one column step in X
    assert wells["A2"].x == pytest.approx(10.0)
    assert wells["A2"].y == pytest.approx(0.0)

    # B1: one row step in Y
    assert wells["B1"].x == pytest.approx(0.0)
    assert wells["B1"].y == pytest.approx(-5.0)

    # B2: both row and column offsets applied
    assert wells["B2"].x == pytest.approx(10.0)
    assert wells["B2"].y == pytest.approx(-5.0)

