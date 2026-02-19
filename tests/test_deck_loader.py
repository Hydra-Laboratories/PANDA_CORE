"""Tests for strict deck YAML loading and labware object mapping."""

import tempfile
from pathlib import Path

import pytest

from pydantic import ValidationError

from deck import WellPlate, Vial, Coordinate3D, Deck
from deck.loader import (
    DeckLoaderError,
    _PlateOrientation,
    _resolve_plate_orientation,
    load_deck_from_yaml,
    load_deck_from_yaml_safe,
)
from deck.yaml_schema import WellPlateYamlEntry, _YamlCalibrationPoints, _YamlPoint3D


# ----- Valid deck YAML fixtures -----

VALID_DECK_ONE_PLATE_ONE_VIAL = """
labware:
  plate_1:
    type: well_plate
    name: opentrons_96_well_20ml
    model_name: opentrons_96_well_20ml
    rows: 8
    columns: 12
    length_mm: 127.71
    width_mm: 85.43
    height_mm: 14.10
    calibration:
      a1:
        x: -10.0
        y: -10.0
        z: -15.0
      a2:
        x: -1.0
        y: -10.0
        z: -15.0
    x_offset_mm: 9.0
    y_offset_mm: -9.0
    capacity_ul: 200.0
    working_volume_ul: 150.0
  vial_1:
    type: vial
    name: standard_vial_rack
    model_name: standard_1_5ml_vial
    height_mm: 66.75
    diameter_mm: 28.0
    location:
      x: -30.0
      y: -40.0
      z: -20.0
    capacity_ul: 1500.0
    working_volume_ul: 1200.0
"""


def test_load_valid_deck_returns_deck_with_labware():
    """Valid deck YAML yields a Deck containing labware keyed by configured names."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(VALID_DECK_ONE_PLATE_ONE_VIAL)
        path = f.name
    try:
        deck = load_deck_from_yaml(path)
        assert isinstance(deck, Deck)
        assert "plate_1" in deck
        assert "vial_1" in deck
        assert len(deck) == 2
        assert isinstance(deck["plate_1"], WellPlate)
        assert isinstance(deck["vial_1"], Vial)
    finally:
        Path(path).unlink(missing_ok=True)


def test_loaded_well_plate_has_derived_wells_and_volume():
    """Loaded WellPlate has correct well count, A1 anchor, and volume fields."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(VALID_DECK_ONE_PLATE_ONE_VIAL)
        path = f.name
    try:
        result = load_deck_from_yaml(path)
        plate = result["plate_1"]
        assert plate.rows == 8
        assert plate.columns == 12
        assert len(plate.wells) == 8 * 12
        assert plate.get_well_center("A1").x == pytest.approx(-10.0)
        assert plate.get_well_center("A1").y == pytest.approx(-10.0)
        assert plate.get_well_center("A1").z == pytest.approx(-15.0)
        assert plate.model_name == "opentrons_96_well_20ml"
        assert plate.capacity_ul == pytest.approx(200.0)
        assert plate.working_volume_ul == pytest.approx(150.0)
    finally:
        Path(path).unlink(missing_ok=True)


def test_loaded_vial_has_location_and_volume():
    """Loaded Vial has a single location and volume fields."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(VALID_DECK_ONE_PLATE_ONE_VIAL)
        path = f.name
    try:
        result = load_deck_from_yaml(path)
        vial = result["vial_1"]
        assert vial.get_vial_center().x == pytest.approx(-30.0)
        assert vial.model_name == "standard_1_5ml_vial"
        assert vial.capacity_ul == pytest.approx(1500.0)
        assert vial.working_volume_ul == pytest.approx(1200.0)
    finally:
        Path(path).unlink(missing_ok=True)


# ----- Two-point calibration orientations -----

def test_calibration_horizontal_increasing_columns():
    """A2.x > A1.x, A2.y == A1.y: columns along +X."""
    yaml = """
labware:
  p:
    type: well_plate
    name: small
    model_name: small
    rows: 2
    columns: 2
    length_mm: 20.0
    width_mm: 20.0
    height_mm: 10.0
    a1: { x: 0.0, y: 0.0, z: -5.0 }
    calibration:
      a2: { x: 10.0, y: 0.0, z: -5.0 }
    x_offset_mm: 10.0
    y_offset_mm: -8.0
    capacity_ul: 100.0
    working_volume_ul: 80.0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        result = load_deck_from_yaml(path)
        plate = result["p"]
        assert plate.get_well_center("A1").x == pytest.approx(0.0)
        assert plate.get_well_center("A1").y == pytest.approx(0.0)
        assert plate.get_well_center("A2").x == pytest.approx(10.0)
        assert plate.get_well_center("A2").y == pytest.approx(0.0)
        assert plate.get_well_center("B1").x == pytest.approx(0.0)
        assert plate.get_well_center("B1").y == pytest.approx(-8.0)
    finally:
        Path(path).unlink(missing_ok=True)


def test_calibration_horizontal_decreasing_columns():
    """A2.x < A1.x, A2.y == A1.y: columns along -X."""
    yaml = """
labware:
  p:
    type: well_plate
    name: small
    model_name: small
    rows: 2
    columns: 2
    length_mm: 20.0
    width_mm: 20.0
    height_mm: 10.0
    a1: { x: 10.0, y: 0.0, z: -5.0 }
    calibration:
      a2: { x: 0.0, y: 0.0, z: -5.0 }
    x_offset_mm: -10.0
    y_offset_mm: -8.0
    capacity_ul: 100.0
    working_volume_ul: 80.0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        result = load_deck_from_yaml(path)
        plate = result["p"]
        assert plate.get_well_center("A1").x == pytest.approx(10.0)
        assert plate.get_well_center("A2").x == pytest.approx(0.0)
        assert plate.get_well_center("A2").y == pytest.approx(0.0)
    finally:
        Path(path).unlink(missing_ok=True)


def test_calibration_vertical_increasing_rows():
    """A2.y > A1.y, A2.x == A1.x: column direction is Y; A2 at (a1.x, a1.y + y_offset)."""
    yaml = """
labware:
  p:
    type: well_plate
    name: small
    model_name: small
    rows: 2
    columns: 2
    length_mm: 20.0
    width_mm: 20.0
    height_mm: 10.0
    a1: { x: 0.0, y: 0.0, z: -5.0 }
    calibration:
      a2: { x: 0.0, y: 8.0, z: -5.0 }
    x_offset_mm: 10.0
    y_offset_mm: 8.0
    capacity_ul: 100.0
    working_volume_ul: 80.0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        result = load_deck_from_yaml(path)
        plate = result["p"]
        assert plate.get_well_center("A1").x == pytest.approx(0.0)
        assert plate.get_well_center("A1").y == pytest.approx(0.0)
        assert plate.get_well_center("A2").x == pytest.approx(0.0)
        assert plate.get_well_center("A2").y == pytest.approx(8.0)
        assert plate.get_well_center("B1").x == pytest.approx(10.0)
        assert plate.get_well_center("B1").y == pytest.approx(0.0)
    finally:
        Path(path).unlink(missing_ok=True)


def test_calibration_vertical_decreasing_rows():
    """A2.y < A1.y, A2.x == A1.x."""
    yaml = """
labware:
  p:
    type: well_plate
    name: small
    model_name: small
    rows: 2
    columns: 2
    length_mm: 20.0
    width_mm: 20.0
    height_mm: 10.0
    a1: { x: 0.0, y: 8.0, z: -5.0 }
    calibration:
      a2: { x: 0.0, y: 0.0, z: -5.0 }
    x_offset_mm: 10.0
    y_offset_mm: -8.0
    capacity_ul: 100.0
    working_volume_ul: 80.0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        result = load_deck_from_yaml(path)
        plate = result["p"]
        assert plate.get_well_center("A1").y == pytest.approx(8.0)
        assert plate.get_well_center("A2").y == pytest.approx(0.0)
        assert plate.get_well_center("A2").x == pytest.approx(0.0)
    finally:
        Path(path).unlink(missing_ok=True)


def test_calibration_diagonal_fails():
    """A1 and A2 with both x and y different (diagonal) must fail."""
    yaml = """
labware:
  p:
    type: well_plate
    name: small
    model_name: small
    rows: 2
    columns: 2
    length_mm: 20.0
    width_mm: 20.0
    height_mm: 10.0
    a1: { x: 0.0, y: 0.0, z: -5.0 }
    calibration:
      a2: { x: 10.0, y: 5.0, z: -5.0 }
    x_offset_mm: 10.0
    y_offset_mm: -8.0
    capacity_ul: 100.0
    working_volume_ul: 80.0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        with pytest.raises(ValidationError, match="axis.aligned|diagonal|orientation"):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_safe_loader_returns_clean_error_message():
    """Safe loader raises DeckLoaderError with concise fix guidance."""
    yaml = """
labware:
  p:
    type: well_plate
    name: small
    model_name: small
    rows: 2
    columns: 2
    length_mm: 20.0
    width_mm: 20.0
    height_mm: 10.0
    a1: { x: 0.0, y: 0.0, z: -5.0 }
    calibration:
      a2: { x: 10.0, y: 5.0, z: -5.0 }
    x_offset_mm: 10.0
    y_offset_mm: -8.0
    capacity_ul: 100.0
    working_volume_ul: 80.0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        with pytest.raises(DeckLoaderError) as exc_info:
            load_deck_from_yaml_safe(path)
        message = str(exc_info.value)
        assert message.startswith("❌")
        assert "How to fix:" in message
        assert "axis-aligned" in message or "shares either the same x or the same y" in message
    finally:
        Path(path).unlink(missing_ok=True)


def test_safe_loader_yaml_parse_error_has_clean_message():
    """Safe loader reports YAML parse issues without traceback noise."""
    bad_yaml = "labware:\n  plate_1:\n    type: well_plate\n    calibration: [\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(bad_yaml)
        path = f.name
    try:
        with pytest.raises(DeckLoaderError) as exc_info:
            load_deck_from_yaml_safe(path)
        message = str(exc_info.value)
        assert message.startswith("❌")
        assert "parse error" in message.lower()
        assert "How to fix:" in message
    finally:
        Path(path).unlink(missing_ok=True)


def test_safe_loader_missing_file_has_clean_message():
    """Safe loader reports missing-file errors as DeckLoaderError."""
    missing_path = "/tmp/this_file_does_not_exist_12345.yaml"
    with pytest.raises(DeckLoaderError) as exc_info:
        load_deck_from_yaml_safe(missing_path)
    message = str(exc_info.value)
    assert message.startswith("❌")
    assert "deck loader error" in message.lower()
    assert "How to fix:" in message


def test_zero_offsets_fail_schema_validation():
    """x/y offsets must be non-zero in well plate schema."""
    yaml = """
labware:
  p:
    type: well_plate
    name: x
    model_name: x
    rows: 8
    columns: 12
    length_mm: 127.71
    width_mm: 85.43
    height_mm: 14.10
    calibration:
      a1: { x: 0.0, y: 0.0, z: -15.0 }
      a2: { x: 9.0, y: 0.0, z: -15.0 }
    x_offset_mm: 0.0
    y_offset_mm: -9.0
    capacity_ul: 200.0
    working_volume_ul: 150.0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        with pytest.raises(ValidationError):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_calibration_identical_points_fails():
    """A1 and A2 identical must fail."""
    yaml = """
labware:
  p:
    type: well_plate
    name: small
    model_name: small
    rows: 2
    columns: 2
    length_mm: 20.0
    width_mm: 20.0
    height_mm: 10.0
    a1: { x: 0.0, y: 0.0, z: -5.0 }
    calibration:
      a2: { x: 0.0, y: 0.0, z: -5.0 }
    x_offset_mm: 10.0
    y_offset_mm: -8.0
    capacity_ul: 100.0
    working_volume_ul: 80.0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        with pytest.raises(ValidationError, match="identical|degenerate|same"):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


# ----- Missing required fields -----

def test_missing_top_level_labware_fails():
    """Deck YAML without 'labware' key fails."""
    yaml = "other: 1\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        with pytest.raises(ValidationError):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_missing_well_plate_required_field_fails():
    """Well plate entry missing e.g. 'rows' or 'calibration' fails."""
    yaml = """
labware:
  p:
    type: well_plate
    name: x
    model_name: x
    columns: 12
    length_mm: 127.71
    width_mm: 85.43
    height_mm: 14.10
    a1: { x: 0.0, y: 0.0, z: -15.0 }
    x_offset_mm: 9.0
    y_offset_mm: -9.0
    capacity_ul: 200.0
    working_volume_ul: 150.0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        with pytest.raises(ValidationError):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_missing_vial_required_field_fails():
    """Vial entry missing e.g. 'location' fails."""
    yaml = """
labware:
  v:
    type: vial
    name: v1
    model_name: m1
    height_mm: 66.0
    diameter_mm: 28.0
    capacity_ul: 1500.0
    working_volume_ul: 1200.0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        with pytest.raises(ValidationError):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


# ----- Extra fields -----

def test_extra_top_level_field_fails():
    """Unknown top-level key in deck YAML fails."""
    yaml = """
labware: {}
gantry: {}
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        with pytest.raises(ValidationError):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_extra_labware_entry_field_fails():
    """Unknown key inside a labware entry fails."""
    yaml = """
labware:
  p:
    type: well_plate
    name: x
    model_name: x
    rows: 8
    columns: 12
    length_mm: 127.71
    width_mm: 85.43
    height_mm: 14.10
    a1: { x: 0.0, y: 0.0, z: -15.0 }
    calibration:
      a2: { x: 9.0, y: 0.0, z: -15.0 }
    x_offset_mm: 9.0
    y_offset_mm: -9.0
    capacity_ul: 200.0
    working_volume_ul: 150.0
    unknown_field: 1
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        with pytest.raises(ValidationError):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


# ----- Type coercion and invalid types -----

def test_numeric_string_coercion_allowed():
    """Numeric strings for numbers (e.g. rows: '8') are coerced where valid."""
    yaml = """
labware:
  p:
    type: well_plate
    name: x
    model_name: x
    rows: "8"
    columns: "12"
    length_mm: "127.71"
    width_mm: "85.43"
    height_mm: "14.10"
    a1: { x: 0.0, y: 0.0, z: -15.0 }
    calibration:
      a2: { x: 9.0, y: 0.0, z: -15.0 }
    x_offset_mm: 9.0
    y_offset_mm: -9.0
    capacity_ul: 200.0
    working_volume_ul: 150.0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        result = load_deck_from_yaml(path)
        assert result["p"].rows == 8
        assert result["p"].columns == 12
    finally:
        Path(path).unlink(missing_ok=True)


def test_non_coercible_type_fails():
    """rows: 'eight' (non-numeric string) fails."""
    yaml = """
labware:
  p:
    type: well_plate
    name: x
    model_name: x
    rows: eight
    columns: 12
    length_mm: 127.71
    width_mm: 85.43
    height_mm: 14.10
    a1: { x: 0.0, y: 0.0, z: -15.0 }
    calibration:
      a2: { x: 9.0, y: 0.0, z: -15.0 }
    x_offset_mm: 9.0
    y_offset_mm: -9.0
    capacity_ul: 200.0
    working_volume_ul: 150.0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        with pytest.raises(ValidationError):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


# ----- Volume validation -----

def test_working_volume_exceeds_capacity_fails():
    """working_volume_ul > capacity_ul must fail."""
    yaml = """
labware:
  p:
    type: well_plate
    name: x
    model_name: x
    rows: 8
    columns: 12
    length_mm: 127.71
    width_mm: 85.43
    height_mm: 14.10
    a1: { x: 0.0, y: 0.0, z: -15.0 }
    calibration:
      a2: { x: 9.0, y: 0.0, z: -15.0 }
    x_offset_mm: 9.0
    y_offset_mm: -9.0
    capacity_ul: 200.0
    working_volume_ul: 250.0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        with pytest.raises(ValidationError):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_negative_capacity_fails():
    """capacity_ul <= 0 fails."""
    yaml = """
labware:
  p:
    type: well_plate
    name: x
    model_name: x
    rows: 8
    columns: 12
    length_mm: 127.71
    width_mm: 85.43
    height_mm: 14.10
    a1: { x: 0.0, y: 0.0, z: -15.0 }
    calibration:
      a2: { x: 9.0, y: 0.0, z: -15.0 }
    x_offset_mm: 9.0
    y_offset_mm: -9.0
    capacity_ul: 0.0
    working_volume_ul: 0.0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        with pytest.raises(ValidationError):
            load_deck_from_yaml(path)
    finally:
        Path(path).unlink(missing_ok=True)


# ----- Empty labware -----

def test_empty_labware_dict_allowed():
    """Deck with labware: {} is valid and returns empty Deck."""
    yaml = "labware: {}\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        deck = load_deck_from_yaml(path)
        assert isinstance(deck, Deck)
        assert len(deck) == 0
    finally:
        Path(path).unlink(missing_ok=True)


# ----- _resolve_plate_orientation unit tests -----


def _make_entry(
    a1_x=0.0, a1_y=0.0, a2_x=10.0, a2_y=0.0,
    x_offset=10.0, y_offset=-8.0, z=-5.0,
) -> WellPlateYamlEntry:
    """Build a minimal WellPlateYamlEntry for orientation tests."""
    return WellPlateYamlEntry(
        name="t", model_name="t",
        rows=2, columns=2,
        length_mm=20.0, width_mm=20.0, height_mm=10.0,
        a1=_YamlPoint3D(x=a1_x, y=a1_y, z=z),
        calibration=_YamlCalibrationPoints(
            a2=_YamlPoint3D(x=a2_x, y=a2_y, z=z),
        ),
        x_offset_mm=x_offset, y_offset_mm=y_offset,
        capacity_ul=100.0, working_volume_ul=80.0,
    )


class TestResolvePlateOrientation:

    def test_horizontal_columns_along_x(self):
        entry = _make_entry(a1_x=0.0, a1_y=0.0, a2_x=10.0, a2_y=0.0,
                            x_offset=10.0, y_offset=-8.0)
        orient = _resolve_plate_orientation(entry)
        assert orient == _PlateOrientation(
            col_delta_x=10.0, col_delta_y=0.0,
            row_delta_x=0.0, row_delta_y=-8.0,
        )

    def test_vertical_columns_along_y(self):
        entry = _make_entry(a1_x=0.0, a1_y=0.0, a2_x=0.0, a2_y=8.0,
                            x_offset=10.0, y_offset=8.0)
        orient = _resolve_plate_orientation(entry)
        assert orient == _PlateOrientation(
            col_delta_x=0.0, col_delta_y=8.0,
            row_delta_x=10.0, row_delta_y=0.0,
        )

    def test_negative_x_column_step(self):
        entry = _make_entry(a1_x=10.0, a1_y=0.0, a2_x=0.0, a2_y=0.0,
                            x_offset=-10.0, y_offset=-8.0)
        orient = _resolve_plate_orientation(entry)
        assert orient.col_delta_x == pytest.approx(-10.0)
        assert orient.col_delta_y == pytest.approx(0.0)

    def test_negative_y_column_step(self):
        entry = _make_entry(a1_x=0.0, a1_y=8.0, a2_x=0.0, a2_y=0.0,
                            x_offset=10.0, y_offset=-8.0)
        orient = _resolve_plate_orientation(entry)
        assert orient.col_delta_y == pytest.approx(-8.0)
        assert orient.col_delta_x == pytest.approx(0.0)

    def test_mismatched_x_offset_raises(self):
        entry = _make_entry(a1_x=0.0, a1_y=0.0, a2_x=10.0, a2_y=0.0,
                            x_offset=5.0, y_offset=-8.0)
        with pytest.raises(ValueError, match="delta x must equal x_offset_mm"):
            _resolve_plate_orientation(entry)

    def test_mismatched_y_offset_raises(self):
        entry = _make_entry(a1_x=0.0, a1_y=0.0, a2_x=0.0, a2_y=8.0,
                            x_offset=10.0, y_offset=4.0)
        with pytest.raises(ValueError, match="delta y must equal y_offset_mm"):
            _resolve_plate_orientation(entry)

    def test_returns_frozen_dataclass(self):
        entry = _make_entry()
        orient = _resolve_plate_orientation(entry)
        assert isinstance(orient, _PlateOrientation)
        with pytest.raises(AttributeError):
            orient.col_delta_x = 99.0
