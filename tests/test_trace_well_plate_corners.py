import pytest
from unittest.mock import call, MagicMock, patch

from src.deck import Coordinate3D, WellPlate, generate_wells_from_offsets, load_deck_from_yaml

import trace_well_plate_corners as module_under_test


def _make_simple_well_plate(rows: int, columns: int) -> WellPlate:
    """Create a minimal well plate with a regular grid of wells for testing."""
    row_labels = [chr(65 + i) for i in range(rows)]
    column_indices = list(range(1, columns + 1))
    a1_center = Coordinate3D(x=0.0, y=0.0, z=-10.0)

    wells = generate_wells_from_offsets(
        row_labels=row_labels,
        column_indices=column_indices,
        a1_center=a1_center,
        x_offset_mm=10.0,
        y_offset_mm=-5.0,
        rounding_decimals=3,
    )

    return WellPlate(
        name="test_plate",
        model_name="test_model",
        length_mm=127.71,
        width_mm=85.43,
        height_mm=14.10,
        rows=rows,
        columns=columns,
        wells=wells,
        capacity_ul=200.0,
        working_volume_ul=150.0,
    )


def test_corner_well_ids_for_standard_plate():
    """Corner well ID helper should resolve the four logical corners."""
    plate = _make_simple_well_plate(rows=8, columns=12)

    ids = module_under_test.get_corner_well_ids(plate)

    assert ids["top_left"] == "A1"
    assert ids["top_right"] == "A12"
    assert ids["bottom_left"] == "H1"
    assert ids["bottom_right"] == "H12"


def test_corner_coordinates_match_plate_wells():
    """Corner coordinate helper should delegate to the plate's well centers."""
    plate = _make_simple_well_plate(rows=8, columns=12)

    corners = module_under_test.get_corner_coordinates(plate)

    assert corners["top_left"] == plate.get_well_center("A1")
    assert corners["top_right"] == plate.get_well_center("A12")
    assert corners["bottom_left"] == plate.get_well_center("H1")
    assert corners["bottom_right"] == plate.get_well_center("H12")


def test_trace_sequence_order_is_tl_tr_br_bl_tl():
    """Trace sequence helper should return corners in a consistent loop order."""
    plate = _make_simple_well_plate(rows=2, columns=2)
    corners = module_under_test.get_corner_coordinates(plate)

    sequence = module_under_test.build_trace_sequence(corners)

    assert sequence[0] == corners["top_left"]
    assert sequence[1] == corners["top_right"]
    assert sequence[2] == corners["bottom_right"]
    assert sequence[3] == corners["bottom_left"]
    assert sequence[4] == corners["top_left"]
    assert len(sequence) == 5


def test_build_x_well_id_sequence_for_8x12_uses_8x8_x_shape():
    """X-shape IDs should follow both diagonals over the square region."""
    plate = _make_simple_well_plate(rows=8, columns=12)

    ids = module_under_test.build_x_well_id_sequence(plate)

    assert ids == (
        "A1", "B2", "C3", "D4", "E5", "F6", "G7", "H8",
        "A8", "B7", "C6", "D5", "E4", "F3", "G2", "H1",
    )


def test_build_x_coordinate_sequence_matches_well_centers():
    """X-shape coordinates should map directly from the generated well IDs."""
    plate = _make_simple_well_plate(rows=8, columns=12)
    ids = module_under_test.build_x_well_id_sequence(plate)

    sequence = module_under_test.build_x_coordinate_sequence(plate)

    assert len(sequence) == len(ids)
    assert sequence[0] == plate.get_well_center("A1")
    assert sequence[1] == plate.get_well_center("B2")
    assert sequence[7] == plate.get_well_center("H8")
    assert sequence[8] == plate.get_well_center("A8")
    assert sequence[-1] == plate.get_well_center("H1")


def test_corners_from_sample_deck_yaml_use_expected_wells():
    """Using the sample deck YAML, corner wells should be A1, A12, H1, H12."""
    deck = load_deck_from_yaml("configs/deck.sample.yaml")
    assert "plate_1" in deck

    plate = deck["plate_1"]
    assert isinstance(plate, WellPlate)

    corners = module_under_test.get_corner_coordinates(plate)

    assert corners["top_left"] == plate.get_well_center("A1")
    assert corners["top_right"] == plate.get_well_center("A12")
    assert corners["bottom_left"] == plate.get_well_center("H1")
    assert corners["bottom_right"] == plate.get_well_center("H12")


def test_sample_deck_x_well_ids_match_requested_pattern():
    """Sample deck should generate A1..H8 then A8..H1 for X-shape."""
    deck = load_deck_from_yaml("configs/deck.sample.yaml")
    plate = deck["plate_1"]
    ids = module_under_test.build_x_well_id_sequence(plate)
    assert ids[:8] == ("A1", "B2", "C3", "D4", "E5", "F6", "G7", "H8")
    assert ids[8:] == ("A8", "B7", "C6", "D5", "E4", "F3", "G2", "H1")


def test_execute_trace_sequence_on_gantry_calls_move_to_in_order():
    """Execution helper should send ordered absolute coordinates to gantry."""
    gantry = MagicMock()
    sequence = (
        Coordinate3D(x=1.0, y=2.0, z=3.0),
        Coordinate3D(x=4.0, y=5.0, z=6.0),
    )

    module_under_test.execute_trace_sequence_on_gantry(gantry, sequence)

    assert gantry.move_to.call_args_list == [
        call(1.0, 2.0, 3.0),
        call(4.0, 5.0, 6.0),
    ]


@patch("trace_well_plate_corners.Gantry")
def test_run_corner_trace_on_gantry_connects_executes_and_disconnects(mock_gantry_cls):
    """Gantry runner should perform connection lifecycle and execute sequence."""
    mock_gantry = mock_gantry_cls.return_value
    mock_gantry.is_healthy.return_value = True
    sequence = (
        Coordinate3D(x=1.0, y=2.0, z=3.0),
        Coordinate3D(x=4.0, y=5.0, z=6.0),
    )

    module_under_test.run_corner_trace_on_gantry(sequence)

    mock_gantry.connect.assert_called_once()
    mock_gantry.is_healthy.assert_called_once()
    mock_gantry.home.assert_not_called()
    assert mock_gantry.move_to.call_args_list == [
        call(1.0, 2.0, 3.0),
        call(4.0, 5.0, 6.0),
    ]
    mock_gantry.disconnect.assert_called_once()


@patch("trace_well_plate_corners.Gantry")
def test_run_corner_trace_on_gantry_raises_when_unhealthy(mock_gantry_cls):
    """Unhealthy gantry should raise and still disconnect."""
    mock_gantry = mock_gantry_cls.return_value
    mock_gantry.is_healthy.return_value = False
    sequence = (Coordinate3D(x=1.0, y=2.0, z=3.0),)

    with pytest.raises(RuntimeError, match="not healthy"):
        module_under_test.run_corner_trace_on_gantry(sequence)

    mock_gantry.disconnect.assert_called_once()


def test_confirm_gantry_execution_yes_returns_true():
    """Confirmation helper should return true only for explicit yes."""
    result = module_under_test._confirm_gantry_execution(input_func=lambda _: "yes")
    assert result is True


def test_confirm_gantry_execution_non_yes_returns_false():
    """Any response other than yes should cancel execution."""
    result = module_under_test._confirm_gantry_execution(input_func=lambda _: "no")
    assert result is False


@patch("trace_well_plate_corners.run_corner_trace_on_gantry")
@patch("trace_well_plate_corners._confirm_gantry_execution")
def test_main_cancels_when_confirmation_rejected(mock_confirm, mock_run):
    """Main should not execute gantry motion when confirmation is rejected."""
    mock_confirm.return_value = False
    module_under_test.main(execute_gantry=True, require_confirmation=True)
    mock_run.assert_not_called()

