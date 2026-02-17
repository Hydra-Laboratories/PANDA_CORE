"""Bounds validation: deck positions and gantry-computed positions vs. machine volume."""

from __future__ import annotations

from typing import List, Optional, Tuple

from src.board.board import Board
from src.deck.deck import Deck
from src.deck.labware.vial import Vial
from src.deck.labware.well_plate import WellPlate
from src.machine.machine_config import MachineConfig, WorkingVolume

from .errors import BoundsViolation


def _check_point(
    volume: WorkingVolume, x: float, y: float, z: float,
) -> List[Tuple[str, str, float]]:
    """Return (axis, bound_name, bound_value) for each violated bound."""
    violations: List[Tuple[str, str, float]] = []
    if x < volume.x_min:
        violations.append(("x", "x_min", volume.x_min))
    if x > volume.x_max:
        violations.append(("x", "x_max", volume.x_max))
    if y < volume.y_min:
        violations.append(("y", "y_min", volume.y_min))
    if y > volume.y_max:
        violations.append(("y", "y_max", volume.y_max))
    if z < volume.z_min:
        violations.append(("z", "z_min", volume.z_min))
    if z > volume.z_max:
        violations.append(("z", "z_max", volume.z_max))
    return violations


def _get_all_positions(
    deck: Deck,
) -> List[Tuple[str, str, float, float, float]]:
    """Extract every (labware_key, position_id, x, y, z) from the deck."""
    positions: List[Tuple[str, str, float, float, float]] = []
    for key in deck:
        labware = deck[key]
        if isinstance(labware, WellPlate):
            for well_id, coord in labware.wells.items():
                positions.append((key, well_id, coord.x, coord.y, coord.z))
        elif isinstance(labware, Vial):
            loc = labware.location
            positions.append((key, "location", loc.x, loc.y, loc.z))
    return positions


def validate_deck_positions(
    machine: MachineConfig, deck: Deck,
) -> List[BoundsViolation]:
    """Check every labware position is within the machine working volume.

    Returns a list of violations (empty if all pass).
    """
    violations: List[BoundsViolation] = []
    volume = machine.working_volume
    for lw_key, pos_id, x, y, z in _get_all_positions(deck):
        for axis, bound_name, bound_value in _check_point(volume, x, y, z):
            violations.append(BoundsViolation(
                labware_key=lw_key,
                position_id=pos_id,
                instrument_name=None,
                coordinate_type="deck",
                x=x, y=y, z=z,
                axis=axis,
                bound_name=bound_name,
                bound_value=bound_value,
            ))
    return violations


def validate_gantry_positions(
    machine: MachineConfig, deck: Deck, board: Board,
) -> List[BoundsViolation]:
    """For each (instrument, deck_position), compute gantry position and check bounds.

    Gantry formula (from board.py Board.move):
        gantry_x = position_x - instrument.offset_x
        gantry_y = position_y - instrument.offset_y
        gantry_z = position_z - instrument.depth

    Returns a list of violations (empty if all pass).
    """
    violations: List[BoundsViolation] = []
    volume = machine.working_volume
    for instr_name, instrument in board.instruments.items():
        for lw_key, pos_id, x, y, z in _get_all_positions(deck):
            gx = x - instrument.offset_x
            gy = y - instrument.offset_y
            gz = z - instrument.depth
            for axis, bound_name, bound_value in _check_point(volume, gx, gy, gz):
                violations.append(BoundsViolation(
                    labware_key=lw_key,
                    position_id=pos_id,
                    instrument_name=instr_name,
                    coordinate_type="gantry",
                    x=gx, y=gy, z=gz,
                    axis=axis,
                    bound_name=bound_name,
                    bound_value=bound_value,
                ))
    return violations
