"""Offline gantry stub for validation and testing without hardware."""

from __future__ import annotations


class OfflineGantry:
    """Stub gantry for offline validation and testing.

    Provides the same interface as Gantry but does nothing—no serial
    connection, no hardware movement.  Used by ``setup_protocol()``
    when no real gantry is provided.
    """

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def is_healthy(self) -> bool:
        return True

    def home(self) -> None:
        pass

    def move_to(self, x: float, y: float, z: float) -> None:
        pass

    def get_coordinates(self) -> dict[str, float]:
        return {"x": 0.0, "y": 0.0, "z": 0.0}

    def get_status(self) -> str:
        return "Offline"

    def stop(self) -> None:
        pass
