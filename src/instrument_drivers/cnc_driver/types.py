from typing import Dict, Tuple, TypedDict, Any, Protocol
import json

# Tool related types
class ToolInfo(TypedDict):
    """TypedDict for tool information"""

    name: str
    x: float
    y: float
    z: float


# Protocol for JSON serialization
class JSONSerializable(Protocol):
    """Protocol for objects that can be serialized to JSON"""

    def to_dict(self) -> Dict[str, Any]:
        """Convert object to dictionary for JSON serialization"""
        ...
