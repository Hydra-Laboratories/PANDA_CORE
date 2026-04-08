"""Coordinate translation between user and machine spaces.

User-facing coordinates are positive-down XYZ.
Machine-facing (GRBL) coordinates are negative-space XYZ.
"""

from __future__ import annotations

import re
from typing import overload

from .gantry_driver.instruments import Coordinates

_STATUS_COORD_PATTERN = re.compile(
    r"(?P<label>[WM]Pos:)"
    r"(?P<x>[+-]?(?:\d+(?:\.\d*)?|\.\d+)),"
    r"(?P<y>[+-]?(?:\d+(?:\.\d*)?|\.\d+)),"
    r"(?P<z>[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
)


def _negate(value: float) -> float:
    translated = -float(value)
    if abs(translated) < 1e-12:
        return 0.0
    return translated


def _format_like(original_token: str, value: float) -> str:
    if "." in original_token:
        decimals = len(original_token.split(".", maxsplit=1)[1])
        return f"{value:.{decimals}f}"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


@overload
def to_user_coordinates(x: float, y: float, z: float) -> tuple[float, float, float]:
    ...


@overload
def to_user_coordinates(coords: Coordinates) -> Coordinates:
    ...


def to_user_coordinates(
    x_or_coords: float | Coordinates,
    y: float | None = None,
    z: float | None = None,
) -> tuple[float, float, float] | Coordinates:
    """Translate machine-space coordinates to user-space coordinates."""
    if isinstance(x_or_coords, Coordinates):
        return Coordinates(_negate(x_or_coords.x), _negate(x_or_coords.y), _negate(x_or_coords.z))
    if y is None or z is None:
        raise TypeError("Expected x, y, z floats when not passing a Coordinates object.")
    return (_negate(x_or_coords), _negate(y), _negate(z))


@overload
def to_machine_coordinates(x: float, y: float, z: float) -> tuple[float, float, float]:
    ...


@overload
def to_machine_coordinates(coords: Coordinates) -> Coordinates:
    ...


def to_machine_coordinates(
    x_or_coords: float | Coordinates,
    y: float | None = None,
    z: float | None = None,
) -> tuple[float, float, float] | Coordinates:
    """Translate user-space coordinates to machine-space coordinates."""
    return to_user_coordinates(x_or_coords, y, z)


def translate_status_string(status: str) -> str:
    """Translate WPos/MPos fields in a GRBL status line to user-space values."""

    def _replace(match: re.Match[str]) -> str:
        tx = _format_like(match.group("x"), _negate(float(match.group("x"))))
        ty = _format_like(match.group("y"), _negate(float(match.group("y"))))
        tz = _format_like(match.group("z"), _negate(float(match.group("z"))))
        return f"{match.group('label')}{tx},{ty},{tz}"

    return _STATUS_COORD_PATTERN.sub(_replace, status)
