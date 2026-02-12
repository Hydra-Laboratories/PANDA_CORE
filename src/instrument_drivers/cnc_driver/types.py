from typing import Dict, Tuple, TypedDict, Any, Protocol
import json


class InstrumentInfo(TypedDict):
    """TypedDict for instrument offset information."""

    name: str
    x: float
    y: float
    z: float


class JSONSerializable(Protocol):
    """Protocol for objects that can be serialized to JSON."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert object to dictionary for JSON serialization."""
        ...
