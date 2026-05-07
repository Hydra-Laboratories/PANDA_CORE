"""Shared movement helpers for protocol commands.

CubOS uses a +Z-up deck frame and labware-relative action heights.

* ``measurement_height`` and ``safe_approach_height`` are *labware-relative*
  offsets above (positive) or below (negative) the labware's ``height_mm``
  surface. ``measurement_height`` is owned by the instrument config; protocol
  commands do not override it.
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


def resolve_instrument_measurement_height(
    *,
    instrument_value: float | None,
    instrument_name: str,
    command_label: str,
) -> float:
    """Return the labware-relative ``measurement_height`` from the instrument
    config, raising a clear error if unset.

    ``measurement_height`` is owned by the instrument; protocol commands do
    not override it. This helper exists to centralize the "instrument must
    declare it" + finite-number checks.
    """
    if instrument_value is None:
        raise ValueError(
            f"{command_label}: `measurement_height` is not set on instrument "
            f"'{instrument_name}'. Set it in the gantry YAML's `instruments:` "
            f"block as a labware-relative offset."
        )
    _assert_finite_number(
        instrument_value, field_name="measurement_height",
        source=f"instrument '{instrument_name}'",
    )
    return float(instrument_value)


def engage_at_labware(
    context: Any,
    instrument: str,
    position: str,
    *,
    command_label: str,
) -> float:
    """Travel above *position* at ``safe_z``, descend to the action plane.

    Reads the labware-relative ``measurement_height`` from the instrument
    config (the only source) and descends to
    ``labware.height_mm + measurement_height``.

    Returns the resolved absolute action Z.

    Raises:
        ValueError: missing labware/instrument, missing height_mm on
            labware, missing ``instr.measurement_height``, non-finite
            numeric value. All command-boundary failures surface as
            ``ValueError`` so callers can wrap them into
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
    relative_offset = resolve_instrument_measurement_height(
        instrument_value=instr.measurement_height,
        instrument_name=instrument,
        command_label=command_label,
    )
    action_z = ref_z + relative_offset
    x, y, _ = unpack_xyz(coord)
    context.board.move_to_labware(instrument, coord)
    context.board.move(instrument, (x, y, action_z))
    return action_z
