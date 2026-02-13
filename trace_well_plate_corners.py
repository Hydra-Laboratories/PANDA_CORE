"""Dry-run helper to report and trace well-plate patterns.

This script:
  - Loads a deck YAML (defaults to configs/deck.sample.yaml)
  - Locates the first WellPlate on the deck
  - Computes the four corner well coordinates:
      * top_left: A1
      * top_right: A{last_column}
      * bottom_left: {last_row}1
      * bottom_right: {last_row}{last_column}
  - Prints corner coordinates
  - Builds an X-shape trace across a square well region:
      * first diagonal: A1, B2, C3, ...
      * second diagonal: A{N}, B{N-1}, C{N-2}, ...
    where N is min(rows, columns)

It performs no hardware I/O or motion commands; it is purely a geometry
inspection tool intended for dry runs.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple

from src.deck import Coordinate3D, Deck, WellPlate, load_deck_from_yaml
from src.gantry import Gantry


DEFAULT_DECK_PATH = Path("configs/deck.sample.yaml")


CornerIdMap = Dict[str, str]
CornerCoordinateMap = Dict[str, Coordinate3D]


@dataclass(frozen=True)
class CornerWells:
    """Logical identifiers and coordinates for the four plate corners."""

    ids: CornerIdMap
    coordinates: CornerCoordinateMap


def _ensure_well_plate_present(deck: Deck) -> Tuple[str, WellPlate]:
    """Return the first well plate on the deck.

    Raises:
        ValueError: if no well plates are present.
    """
    for name, labware in deck.labware.items():
        if isinstance(labware, WellPlate):
            return name, labware
    raise ValueError("No WellPlate instances found on the loaded deck.")


def _last_row_label(rows: int) -> str:
    """Return the last row label for a given row count.

    Mirrors the row-label generation in src/deck/loader._row_labels but only
    returns the final label (e.g., 8 -> 'H', 1 -> 'A').
    """
    if rows <= 0:
        raise ValueError("rows must be positive to compute a row label.")

    value = rows
    label = ""
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        label = chr(65 + remainder) + label
    return label


def get_corner_well_ids(plate: WellPlate) -> CornerIdMap:
    """Compute the logical well IDs for the four plate corners.

    Corner semantics:
        - top_left: A1
        - top_right: A{columns}
        - bottom_left: {last_row}1
        - bottom_right: {last_row}{columns}
    """
    last_row = _last_row_label(plate.rows)
    last_column = plate.columns

    ids: CornerIdMap = {
        "top_left": "A1",
        "top_right": f"A{last_column}",
        "bottom_left": f"{last_row}1",
        "bottom_right": f"{last_row}{last_column}",
    }
    return ids


def get_corner_coordinates(plate: WellPlate) -> CornerCoordinateMap:
    """Resolve the four plate corners into absolute deck coordinates."""
    ids = get_corner_well_ids(plate)
    return {
        name: plate.get_well_center(well_id) for name, well_id in ids.items()
    }


def build_x_well_id_sequence(plate: WellPlate, *, size: int | None = None) -> Tuple[str, ...]:
    """Build an X-shape well ID sequence over a square sub-grid.

    Examples for N=8:
      - first diagonal:  A1, B2, C3, ..., H8
      - second diagonal: A8, B7, C6, ..., H1
    """
    max_size = min(plate.rows, plate.columns)
    n = max_size if size is None else size
    if n <= 0:
        raise ValueError("size must be positive.")
    if n > max_size:
        raise ValueError(f"size={n} exceeds available square size {max_size}.")

    first_diagonal = []
    second_diagonal = []
    for row_index in range(n):
        row_label = _last_row_label(row_index + 1)
        first_diagonal.append(f"{row_label}{row_index + 1}")
        second_diagonal.append(f"{row_label}{n - row_index}")

    return tuple(first_diagonal + second_diagonal)


def build_x_coordinate_sequence(
    plate: WellPlate,
    *,
    size: int | None = None,
) -> Tuple[Coordinate3D, ...]:
    """Resolve the X-shape well sequence into absolute coordinates."""
    return tuple(plate.get_well_center(well_id) for well_id in build_x_well_id_sequence(plate, size=size))


def build_trace_sequence(corners: CornerCoordinateMap) -> Tuple[Coordinate3D, ...]:
    """Return an ordered trace sequence around the plate corners.

    Sequence:
        TL -> TR -> BR -> BL -> TL
    """
    return (
        corners["top_left"],
        corners["top_right"],
        corners["bottom_right"],
        corners["bottom_left"],
        corners["top_left"],
    )


def _format_coordinate(label: str, coord: Coordinate3D) -> str:
    return f"{label:12s} -> x={coord.x:.3f}, y={coord.y:.3f}, z={coord.z:.3f}"


def _print_corners(plate_name: str, corners: CornerCoordinateMap) -> None:
    print(f"Well plate: {plate_name}")
    print("Corner well centers:")
    print(_format_coordinate("top_left", corners["top_left"]))
    print(_format_coordinate("top_right", corners["top_right"]))
    print(_format_coordinate("bottom_right", corners["bottom_right"]))
    print(_format_coordinate("bottom_left", corners["bottom_left"]))
    print()


def _print_trace_sequence(sequence: Iterable[Coordinate3D]) -> None:
    print("Trace sequence:")
    for index, coord in enumerate(sequence, start=1):
        print(f"  step {index:2d}: x={coord.x:.3f}, y={coord.y:.3f}, z={coord.z:.3f}")


def _print_well_id_sequence(well_ids: Iterable[str]) -> None:
    print("Well ID sequence:")
    for index, well_id in enumerate(well_ids, start=1):
        print(f"  step {index:2d}: {well_id}")


def execute_trace_sequence_on_gantry(
    gantry: Gantry,
    sequence: Iterable[Coordinate3D],
) -> None:
    """Move the gantry through the provided absolute coordinate sequence."""
    for coord in sequence:
        gantry.move_to(coord.x, coord.y, coord.z)


def run_corner_trace_on_gantry(
    sequence: Iterable[Coordinate3D],
    *,
    home_first: bool = False,
) -> None:
    """Connect to gantry and execute the corner trace sequence."""
    gantry = Gantry()
    gantry.connect()
    try:
        if not gantry.is_healthy():
            raise RuntimeError("Gantry is not healthy after connect.")
        if home_first:
            gantry.home()
        execute_trace_sequence_on_gantry(gantry, sequence)
    finally:
        gantry.disconnect()


def _confirm_gantry_execution(input_func=input) -> bool:
    """Request explicit confirmation before any hardware motion."""
    print("\nAbout to execute gantry motion for corner trace.")
    print("Type 'yes' to continue, or anything else to cancel.")
    response = input_func("Confirm gantry execution? [yes/NO]: ").strip().lower()
    return response == "yes"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trace well-plate corner wells.")
    parser.add_argument(
        "--deck-path",
        type=Path,
        default=DEFAULT_DECK_PATH,
        help="Path to deck YAML file.",
    )
    parser.add_argument(
        "--execute-gantry",
        action="store_true",
        help="Execute the sequence on connected gantry (opt-in; hardware motion).",
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Bypass interactive confirmation prompt before gantry motion.",
    )
    return parser.parse_args()


def main(
    deck_path: Path = DEFAULT_DECK_PATH,
    *,
    execute_gantry: bool = False,
    require_confirmation: bool = True,
) -> None:
    """Entry point for X-trace reporting and optional execution."""
    deck = load_deck_from_yaml(deck_path)
    plate_name, plate = _ensure_well_plate_present(deck)

    corners = get_corner_coordinates(plate)
    x_well_ids = build_x_well_id_sequence(plate)
    sequence = build_x_coordinate_sequence(plate)

    _print_corners(plate_name, corners)
    print(f"X-shape size: {min(plate.rows, plate.columns)}")
    _print_well_id_sequence(x_well_ids)
    _print_trace_sequence(sequence)

    if execute_gantry:
        if require_confirmation and not _confirm_gantry_execution():
            print("Gantry execution cancelled by user.")
            return
        run_corner_trace_on_gantry(sequence, home_first=False)


if __name__ == "__main__":
    cli_args = _parse_args()
    main(
        deck_path=cli_args.deck_path,
        execute_gantry=cli_args.execute_gantry,
        require_confirmation=not cli_args.no_confirm,
    )

