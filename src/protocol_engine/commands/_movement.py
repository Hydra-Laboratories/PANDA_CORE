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

import math
from typing import Any


def _assert_finite_number(value: Any, *, field_name: str, source: str) -> None:
    """Reject non-numeric / non-finite values reaching the height resolver.

    YAML loads `Dict[str, Any]` paths can carry strings, bools, NaN, or inf
    that would otherwise hit late `TypeError`s deep in motion arithmetic.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            f"{source}: `{field_name}` must be a finite number, got "
            f"{type(value).__name__} {value!r}."
        )
    if not math.isfinite(float(value)):
        raise ValueError(
            f"{source}: `{field_name}` must be a finite number, got {value!r}."
        )


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


def resolve_height_field(
    *,
    field_name: str,
    instrument_value: float | None,
    command_value: float | None,
    instrument_name: str,
    command_label: str,
) -> float:
    """Resolve a labware-relative height field from two possible sources.

    The field may be set on the instrument config, on the protocol command,
    or both. At least one source must define it. If both are set, they must
    agree; conflicting values raise.

    Args:
        field_name: Name of the field for error messages (e.g.
            ``"measurement_height"``, ``"safe_approach_height"``).
        instrument_value: Value from the instrument config (or ``None``).
        command_value: Value from the protocol command (or ``None``).
        instrument_name: Instrument name for error messages.
        command_label: Command name for error messages
            (e.g. ``"measure"``, ``"scan"``).
    """
    if instrument_value is not None:
        _assert_finite_number(
            instrument_value, field_name=field_name,
            source=f"instrument '{instrument_name}'",
        )
    if command_value is not None:
        _assert_finite_number(
            command_value, field_name=field_name,
            source=f"command '{command_label}'",
        )
    if instrument_value is not None and command_value is not None:
        if instrument_value != command_value:
            raise ValueError(
                f"{command_label}: `{field_name}` is set on instrument "
                f"'{instrument_name}' ({instrument_value}) and on the "
                f"command ({command_value}) with conflicting values. "
                "When both sources are set they must match."
            )
        return instrument_value
    if instrument_value is None and command_value is None:
        raise ValueError(
            f"{command_label}: `{field_name}` is not set. Provide it on "
            f"the command or on instrument '{instrument_name}'."
        )
    return instrument_value if instrument_value is not None else command_value


# Backwards-compatible wrapper for the common ``measurement_height`` case.
def resolve_measurement_height(
    *,
    instrument_value: float | None,
    command_value: float | None,
    instrument_name: str,
    command_label: str,
) -> float:
    return resolve_height_field(
        field_name="measurement_height",
        instrument_value=instrument_value,
        command_value=command_value,
        instrument_name=instrument_name,
        command_label=command_label,
    )


def engage_at_labware(
    context: Any,
    instrument: str,
    position: str,
    *,
    command_label: str,
    measurement_height: float | None = None,
) -> float:
    """Travel above *position* at ``safe_z``, descend to the action plane.

    Resolves the labware-relative ``measurement_height`` from two sources
    (instrument config and protocol command). At least one source must
    define it; if both are set the values must match. Composes
    ``board.move_to_labware`` (XY at ``safe_z``) followed by a straight
    descent to ``labware.height_mm + measurement_height``.

    Returns the resolved absolute action Z.

    Raises:
        ValueError: missing labware/instrument, missing height_mm on
            labware, missing or conflicting ``measurement_height``,
            non-finite numeric values. All command-boundary failures
            surface as ``ValueError`` so callers can wrap them into
            ``ProtocolExecutionError`` consistently.
    """
    try:
        instr = context.board.instruments[instrument]
    except KeyError as exc:
        raise ValueError(
            f"{command_label}: unknown instrument '{instrument}'."
        ) from exc
    try:
        coord = context.deck.resolve(position)
    except (KeyError, AttributeError, ValueError) as exc:
        raise ValueError(
            f"{command_label}: cannot resolve position {position!r} on the "
            f"deck: {exc}"
        ) from exc
    labware_key = position.split(".", 1)[0]
    try:
        labware = context.deck[labware_key]
    except KeyError as exc:
        raise ValueError(
            f"{command_label}: labware {labware_key!r} not found on the deck."
        ) from exc
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
