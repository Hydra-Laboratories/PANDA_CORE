"""Shared movement helpers for protocol commands.

CubOS uses a +Z-up deck frame and labware-relative action heights.

* ``measurement_height`` and ``safe_approach_height`` are *labware-relative*
  offsets above (positive) or below (negative) the labware's ``height_mm``
  surface.
* Inter-labware travel uses the gantry's absolute ``safe_z``, exposed on
  ``Board.safe_z``.

There is no inter-labware helper. Callers compose the motion explicitly:
``board.move_to_labware`` (travels at ``safe_z``) followed by
``board.move`` to descend to the per-labware action plane.
"""

from __future__ import annotations

from typing import Any


def unpack_xyz(coord: Any) -> tuple[float, float, float]:
    """Extract ``(x, y, z)`` from a ``Coordinate3D``-like object, tuple, or list."""
    if isinstance(coord, (tuple, list)):
        return (coord[0], coord[1], coord[2])
    return (coord.x, coord.y, coord.z)


def resolve_labware_height(labware: Any, position: str) -> float:
    """Return the labware's ``height_mm`` reference Z, raising if unset.

    All labware-relative scan/measure heights are computed against this Z.
    """
    height_mm = getattr(labware, "height_mm", None)
    if height_mm is None:
        raise ValueError(
            f"Labware at {position!r} has no `height_mm` set. Add "
            "`height_mm` to the deck YAML so labware-relative measurement "
            "and approach heights can be resolved."
        )
    return height_mm


def resolve_measurement_height(
    *,
    instrument_value: float | None,
    command_value: float | None,
    instrument_name: str,
    command_label: str,
) -> float:
    """Return the resolved relative ``measurement_height`` per the XOR rule.

    Exactly one of the instrument-config and protocol-command values must
    be set. Both → conflict; neither → missing.
    """
    if instrument_value is not None and command_value is not None:
        raise ValueError(
            f"{command_label}: `measurement_height` is set both on "
            f"instrument '{instrument_name}' ({instrument_value}) and on "
            f"the command ({command_value}). Set it in exactly one place."
        )
    if instrument_value is None and command_value is None:
        raise ValueError(
            f"{command_label}: `measurement_height` is not set. Provide it "
            f"on the command or on instrument '{instrument_name}'."
        )
    return instrument_value if instrument_value is not None else command_value


def engage_at_labware(
    context: Any,
    instrument: str,
    position: str,
    *,
    command_label: str,
    measurement_height: float | None = None,
) -> float:
    """Travel above *position* at ``safe_z``, descend to the action plane.

    Resolves the labware-relative ``measurement_height`` via the XOR rule
    against the instrument config, then composes
    ``board.move_to_labware`` (XY at ``safe_z``) followed by a straight
    descent to ``labware.height_mm + measurement_height``.

    Returns the resolved absolute action Z.
    """
    instr = context.board.instruments[instrument]
    coord = context.deck.resolve(position)
    labware_key = position.split(".", 1)[0]
    labware = context.deck[labware_key]
    ref_z = resolve_labware_height(labware, position)
    relative_offset = resolve_measurement_height(
        instrument_value=instr.measurement_height,
        command_value=measurement_height,
        instrument_name=instrument,
        command_label=command_label,
    )
    action_z = ref_z + relative_offset
    x, y, _ = unpack_xyz(coord)
    context.board.move_to_labware(instrument, coord)
    context.board.move(instrument, (x, y, action_z))
    return action_z
