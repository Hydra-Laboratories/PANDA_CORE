"""Protocol commands for pipette operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from deck.labware.well_plate import WellPlate

from ..errors import ProtocolExecutionError
from ..registry import protocol_command

if TYPE_CHECKING:
    from ..protocol import ProtocolContext


def _get_pipette(context: ProtocolContext):
    """Return the pipette instrument or raise ProtocolExecutionError."""
    if "pipette" not in context.board.instruments:
        raise ProtocolExecutionError(
            "No pipette registered on the board. "
            "Add one via Board(instruments={'pipette': ...})"
        )
    return context.board.instruments["pipette"]


@protocol_command("aspirate")
def aspirate(
    context: ProtocolContext,
    position: str,
    volume_ul: float,
    speed: float = 50.0,
) -> None:
    """Move pipette to *position*, then aspirate."""
    coord = context.deck.resolve(position)
    pipette = _get_pipette(context)
    context.board.move("pipette", coord)
    return pipette.aspirate(volume_ul, speed)


@protocol_command("dispense")
def dispense(
    context: ProtocolContext,
    position: str,
    volume_ul: float,
    speed: float = 50.0,
) -> None:
    """Move pipette to *position*, then dispense."""
    coord = context.deck.resolve(position)
    pipette = _get_pipette(context)
    context.board.move("pipette", coord)
    return pipette.dispense(volume_ul, speed)


@protocol_command("blowout")
def blowout(
    context: ProtocolContext,
    position: str,
    speed: float = 50.0,
) -> None:
    """Move pipette to *position*, then blowout."""
    coord = context.deck.resolve(position)
    pipette = _get_pipette(context)
    context.board.move("pipette", coord)
    pipette.blowout(speed)


@protocol_command("mix")
def mix(
    context: ProtocolContext,
    position: str,
    volume_ul: float,
    repetitions: int = 3,
    speed: float = 50.0,
) -> None:
    """Move pipette to *position*, then mix."""
    coord = context.deck.resolve(position)
    pipette = _get_pipette(context)
    context.board.move("pipette", coord)
    return pipette.mix(volume_ul, repetitions, speed)


@protocol_command("pick_up_tip")
def pick_up_tip(
    context: ProtocolContext,
    position: str,
    speed: float = 50.0,
) -> None:
    """Move pipette to *position*, then pick up a tip."""
    coord = context.deck.resolve(position)
    pipette = _get_pipette(context)
    context.board.move("pipette", coord)
    pipette.pick_up_tip(speed)


@protocol_command("transfer")
def transfer(
    context: ProtocolContext,
    source: str,
    destination: str,
    volume_ul: float,
    speed: float = 50.0,
) -> None:
    """Aspirate from *source* and dispense into *destination*."""
    source_coord = context.deck.resolve(source)
    dest_coord = context.deck.resolve(destination)
    pipette = _get_pipette(context)
    context.board.move("pipette", source_coord)
    pipette.aspirate(volume_ul, speed)
    context.board.move("pipette", dest_coord)
    pipette.dispense(volume_ul, speed)


@protocol_command("drop_tip")
def drop_tip(
    context: ProtocolContext,
    position: str,
    speed: float = 50.0,
) -> None:
    """Move pipette to *position*, then drop the tip."""
    coord = context.deck.resolve(position)
    pipette = _get_pipette(context)
    context.board.move("pipette", coord)
    pipette.drop_tip(speed)


# ── Compound helpers ──────────────────────────────────────────────────────


def _linspace(start: float, end: float, n: int) -> list:
    """Return *n* evenly spaced values from *start* to *end* inclusive."""
    if n == 1:
        return [start]
    step = (end - start) / (n - 1)
    return [start + i * step for i in range(n)]


def _wells_for_axis(plate: WellPlate, axis: str) -> list:
    """Return well IDs along *axis* in natural order.

    If *axis* is a letter (e.g. ``"A"``), returns the row (A1, A2, …).
    If *axis* is a digit string (e.g. ``"3"``), returns the column (A3, B3, …).
    """
    if axis.isalpha():
        wells = [w for w in plate.wells if w[0] == axis.upper()]
    else:
        wells = [w for w in plate.wells if w[1:] == axis]
    return sorted(wells, key=lambda w: (w[0], int(w[1:])))


@protocol_command("serial_transfer")
def serial_transfer(
    context: ProtocolContext,
    source: str,
    plate: str,
    axis: str,
    volumes: Optional[List[float]] = None,
    volume_range: Optional[List[float]] = None,
    speed: float = 50.0,
) -> None:
    """Transfer from *source* to each well along a row or column.

    Provide exactly one of *volumes* (explicit list) or *volume_range*
    ([min, max] linearly spaced across the axis).

    Args:
        context:      Runtime context.
        source:       Deck target to aspirate from (e.g. ``"vial_1"``).
        plate:        Deck key of the well plate.
        axis:         Row letter (``"A"``) or column number (``"1"``).
        volumes:      Explicit list of volumes matching the axis length.
        volume_range: ``[min, max]`` — linearly spaced across the axis.
        speed:        Pipette speed (default 50.0).
    """
    _get_pipette(context)

    plate_obj = context.deck[plate]
    if not isinstance(plate_obj, WellPlate):
        raise ProtocolExecutionError(
            f"serial_transfer requires a WellPlate, but '{plate}' is "
            f"{type(plate_obj).__name__}."
        )

    well_ids = _wells_for_axis(plate_obj, axis)
    if not well_ids:
        raise ProtocolExecutionError(
            f"No wells found for axis '{axis}' on plate '{plate}'."
        )

    has_volumes = volumes is not None
    has_range = volume_range is not None
    if has_volumes == has_range:
        raise ProtocolExecutionError(
            "Provide exactly one of volumes or volume_range, not both or neither."
        )

    if has_range:
        volumes = _linspace(volume_range[0], volume_range[1], len(well_ids))

    if len(volumes) != len(well_ids):
        raise ProtocolExecutionError(
            f"volumes length ({len(volumes)}) does not match axis '{axis}' "
            f"well count ({len(well_ids)})."
        )

    for well_id, vol in zip(well_ids, volumes):
        destination = f"{plate}.{well_id}"
        transfer(context, source=source, destination=destination,
                 volume_ul=vol, speed=speed)
