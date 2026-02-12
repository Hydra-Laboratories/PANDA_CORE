"""Instrument definitions and offset management for the CNC mill."""

import json
from enum import Enum
from pathlib import Path
from typing import Dict, Tuple, Union

from .types import JSONSerializable, InstrumentInfo


class Instruments(Enum):
    """Enumeration of available mill instruments."""

    CENTER = "center"
    PIPETTE = "pipette"
    ELECTRODE = "electrode"
    LENS = "lens"
    DECAPPER = "decapper"


class Coordinates:
    """Immutable-style 3D coordinate representation with auto-rounding."""

    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def __str__(self):
        return f"({self.x}, {self.y}, {self.z})"

    @property
    def x(self):
        """Getter for the x-coordinate."""
        return round(float(self._x), 6)

    @x.setter
    def x(self, value):
        if not isinstance(value, (int, float)):
            raise ValueError("x-coordinate must be an int, float, or Decimal object")
        self._x = round(value, 6)

    @property
    def y(self):
        """Getter for the y-coordinate."""
        return round(float(self._y), 6)

    @y.setter
    def y(self, value):
        if not isinstance(value, (int, float)):
            raise ValueError("y-coordinate must be an int, float, or Decimal object")
        self._y = round(value, 6)

    @property
    def z(self):
        """Getter for the z-coordinate."""
        return round(float(self._z), 6)

    @z.setter
    def z(self, value):
        if not isinstance(value, (int, float)):
            raise ValueError("z-coordinate must be an int, float, or Decimal object")
        self._z = round(value, 6)

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z

    def __repr__(self):
        return f"Coordinates(x={self.x}, y={self.y}, z={self.z})"

    def __eq__(self, other):
        if not isinstance(other, Coordinates):
            return False
        return self.x == other.x and self.y == other.y and self.z == other.z

    def __setitem__(self, key, value):
        if key == 0 or key == "x":
            self.x = value
        elif key == 1 or key == "y":
            self.y = value
        elif key == 2 or key == "z":
            self.z = value
        else:
            raise IndexError("Index out of range")

    def __getitem__(self, key):
        if key == 0 or key == "x":
            return self.x
        elif key == 1 or key == "y":
            return self.y
        elif key == 2 or key == "z":
            return self.z
        else:
            raise IndexError("Index out of range")

    def to_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "z": self.z,
        }


class InstrumentOffset(JSONSerializable):
    """Stores the name and XYZ offset for a single instrument."""

    def __init__(self, name: str, offset: Coordinates):
        self.name: str = name
        self.offset: Coordinates = offset

    @classmethod
    def from_dict(cls, data: InstrumentInfo):
        offset = Coordinates(data["x"], data["y"], data["z"])
        return cls(name=data["name"], offset=offset)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "x": self.offset.x,
            "y": self.offset.y,
            "z": self.offset.z,
        }

    def __str__(self):
        return f"{self.name}: {str(self.offset)}"


class InstrumentManager:
    """
    Manages instrument offsets for the CNC mill.

    On initialization, loads instrument definitions from a JSON file located
    alongside this module. If the file does not exist, creates a default
    set of instruments with zero offsets.

    A different JSON file path can be provided on initialization.

    Attributes:
        json_file (str): Path to the JSON file containing instrument offsets.
        instrument_offsets (dict): Mapping of instrument names to InstrumentOffset objects.
    """

    def __init__(self, json_file: str = Path(__file__).parent / "instruments.json"):
        self.json_file = json_file
        self.instrument_offsets: Dict[str, InstrumentOffset] = self._load_instruments()

        if self.instrument_offsets == {}:
            self.instrument_offsets = {self._default_instrument().name: self._default_instrument()}
            self._save_instruments()

    def _load_instruments(self) -> Dict[str, InstrumentOffset]:
        try:
            with open(self.json_file, "r") as file:
                data = json.load(file)
                return {item["name"]: InstrumentOffset.from_dict(item) for item in data}
        except (FileNotFoundError, json.JSONDecodeError):
            with open(self.json_file, "w") as file:
                json.dump(DEFAULT_INSTRUMENT_DATA, file, indent=4)
            return {
                item["name"]: InstrumentOffset.from_dict(item)
                for item in DEFAULT_INSTRUMENT_DATA
            }
        except Exception as e:
            print(f"Error loading instruments: {e}")
            return {}

    def _save_instruments(self):
        with open(self.json_file, "w") as file:
            json.dump(
                [inst.to_dict() for inst in self.instrument_offsets.values()],
                file,
                indent=4,
            )

    def add_instrument(
        self, name: str, offset: Union[Coordinates, Tuple[float, float, float]]
    ):
        if not isinstance(name, str):
            try:
                name = name.value
            except AttributeError:
                raise ValueError("Invalid instrument name") from None
        if isinstance(offset, tuple):
            offset = Coordinates(*offset)

        if name in self.instrument_offsets:
            self.update_instrument(name, offset)
        else:
            self.instrument_offsets[name] = InstrumentOffset(name=name, offset=offset)

        self._save_instruments()

    def get_instrument(self, name: str) -> InstrumentOffset:
        if not isinstance(name, str):
            try:
                name = name.value
            except AttributeError:
                raise ValueError("Invalid instrument name") from None
        return self.instrument_offsets.get(name)

    def get_offset(self, name: str) -> Coordinates:
        if not isinstance(name, str):
            try:
                name = name.value
            except AttributeError:
                raise ValueError("Invalid instrument name") from None
        return self.instrument_offsets.get(name).offset

    def update_instrument(self, name: str, offset: Coordinates):
        if not isinstance(name, str):
            try:
                name = name.value
            except AttributeError:
                raise ValueError("Invalid instrument name") from None
        if isinstance(offset, tuple):
            offset = Coordinates(*offset)
        if name in self.instrument_offsets:
            self.instrument_offsets[name].offset = offset
            self._save_instruments()
        else:
            raise ValueError(f"Instrument '{name}' not found")

    def delete_instrument(self, name: str):
        if name in self.instrument_offsets:
            del self.instrument_offsets[name]
            self._save_instruments()
        else:
            raise ValueError(f"Instrument '{name}' not found")

    def _default_instrument(self):
        return InstrumentOffset(name="center", offset=Coordinates(0, 0, 0))


DEFAULT_INSTRUMENT_DATA = [
    {"name": "center", "x": 0.0, "y": 0.0, "z": 0.0},
    {"name": "pipette", "x": 0.0, "y": 0.0, "z": 0.0},
    {"name": "electrode", "x": 0.0, "y": 0.0, "z": 0.0},
    {"name": "decapper", "x": 0.0, "y": 0.0, "z": 0.0},
    {"name": "lens", "x": 0.0, "y": 0.0, "z": 0.0},
]
