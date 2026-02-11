"""Class of the instruments used on the CNC mill."""

import json
from enum import Enum
from pathlib import Path
from typing import Dict, Tuple, Union

from .types import JSONSerializable, ToolInfo


# NOTE these are not mill agnostic, so they should be implemented by whichever
# project is using this library.


class Instruments(Enum):
    """Class for naming of the mill instruments."""

    CENTER = "center"
    PIPETTE = "pipette"
    ELECTRODE = "electrode"
    LENS = "lens"
    DECAPPER = "decapper"


Tools = Instruments


class Coordinates:
    """Class for storing coordinates."""

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


class ToolOffset(JSONSerializable):
    def __init__(self, name: str, offset: Coordinates):
        self.name: str = name
        self.offset: Coordinates = offset

    @classmethod
    def from_dict(cls, data: ToolInfo):
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


class ToolManager:
    """
    Class for managing the tools used on the CNC mill.
    On initialization, the class will load the tools from a default JSON file located locally to the module.
    If the file does not exist, the class will create a default tool called "center" with an offset of (0, 0, 0).

    You can provide a different JSON file path to the class on initialization.

    The class provides methods for adding, getting, updating, and deleting tools.

    Attributes:
        json_file (str): The path to the JSON file containing the tools.
        tool_offsets (dict): A dictionary of the tool offsets.
    """

    def __init__(self, json_file: str = Path(__file__).parent / "tools.json"):
        self.json_file = json_file
        self.tool_offsets: Dict[str, ToolOffset] = self.load_tools()

        if self.tool_offsets == {}:
            self.tool_offsets = {self.__default_tool().name: self.__default_tool()}
            self.save_tools()

    def load_tools(self) -> Dict[str, ToolOffset]:
        try:
            with open(self.json_file, "r") as file:
                data = json.load(file)
                return {item["name"]: ToolOffset.from_dict(item) for item in data}
        except (FileNotFoundError, json.JSONDecodeError):
            with open(self.json_file, "w") as file:
                json.dump(default_tool_json, file, indent=4)
            return {
                item["name"]: ToolOffset.from_dict(item) for item in default_tool_json
            }
        except Exception as e:
            print(f"Error loading tools: {e}")
            return {}

    def save_tools(self):
        with open(self.json_file, "w") as file:
            json.dump(
                [tool.to_dict() for tool in self.tool_offsets.values()], file, indent=4
            )

    def add_tool(
        self, name: str, offset: Union[Coordinates, Tuple[float, float, float]]
    ):
        if not isinstance(name, str):
            try:
                name = name.value
            except AttributeError:
                raise ValueError("Invalid tool") from None
        if isinstance(offset, tuple):
            offset = Coordinates(*offset)

        if name in self.tool_offsets:
            self.update_tool(name, offset)
        else:
            self.tool_offsets[name] = ToolOffset(name=name, offset=offset)

        self.save_tools()

    def get_tool(self, name: str) -> ToolOffset:
        if not isinstance(name, str):
            try:
                name = name.value
            except AttributeError:
                raise ValueError("Invalid tool") from None
        return self.tool_offsets.get(name)

    def get_offset(self, name: str) -> Coordinates:
        if not isinstance(name, str):
            try:
                name = name.value
            except AttributeError:
                raise ValueError("Invalid tool") from None
        return self.tool_offsets.get(name).offset

    def update_tool(self, name: str, offset: Coordinates):
        if not isinstance(name, str):
            try:
                name = name.value
            except AttributeError:
                raise ValueError("Invalid tool") from None
        if isinstance(offset, tuple):
            offset = Coordinates(*offset)
        if name in self.tool_offsets:
            self.tool_offsets[name].offset = offset
            self.save_tools()
        else:
            raise ValueError(f"Tool {name} not found")

    def delete_tool(self, name: str):
        if name in self.tool_offsets:
            del self.tool_offsets[name]
            self.save_tools()
        else:
            raise ValueError(f"Tool {name} not found")

    def __default_tool(self):
        return ToolOffset(name="center", offset=Coordinates(0, 0, 0))


default_tool_json = [
    {"name": "center", "x": 0.0, "y": 0.0, "z": 0.0},
    {"name": "pipette", "x": 0.0, "y": 0.0, "z": 0.0},
    {"name": "electrode", "x": 0.0, "y": 0.0, "z": 0.0},
    {"name": "decapper", "x": 0.0, "y": 0.0, "z": 0.0},
    {"name": "lens", "x": 0.0, "y": 0.0, "z": 0.0},
]
