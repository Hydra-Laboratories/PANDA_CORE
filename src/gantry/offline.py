"""Offline gantry stub for validation and testing without hardware."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator


class OfflineGantry:
    """Stub gantry for offline validation and testing.

    Provides the same interface as Gantry but does nothing—no serial
    connection, no hardware movement.  Used by ``setup_protocol()``
    when no real gantry is provided, and by mock/dry-run modes in
    downstream projects like ASMI_new.
    """

    def __init__(self):
        self._coords = {"x": 0.0, "y": 0.0, "z": 0.0}

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def is_healthy(self) -> bool:
        return True

    def home(self) -> None:
        pass

    def safe_home(self) -> None:
        self.home()

    def unlock(self) -> None:
        pass

    def move_to(self, x: float, y: float, z: float) -> None:
        self._coords = {"x": x, "y": y, "z": z}

    def get_coordinates(self) -> dict[str, float]:
        return dict(self._coords)

    def get_status(self) -> str:
        return "Idle"

    @contextmanager
    def temporary_grbl_setting(
        self,
        setting: str,
        value: float | int | bool,
    ) -> Iterator[None]:
        yield

    def recover_from_limit_alarm(
        self,
        delta: dict[str, float],
        *,
        pull_off_mm: float,
        feed_rate: float,
    ) -> dict[str, float]:
        return self.get_coordinates()

    def stop(self) -> None:
        pass
