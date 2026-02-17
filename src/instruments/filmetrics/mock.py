from typing import Optional

from instruments.base_instrument import BaseInstrument
from instruments.filmetrics.models import MeasurementResult


class MockFilmetrics(BaseInstrument):
    """In-memory mock of the Filmetrics instrument for testing."""

    def __init__(
        self,
        default_result: Optional[MeasurementResult] = None,
        name: Optional[str] = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        depth: float = 0.0,
        measurement_height: float = 0.0,
    ):
        super().__init__(
            name=name, offset_x=offset_x, offset_y=offset_y,
            depth=depth, measurement_height=measurement_height,
        )
        self._connected = False
        self._default_result = default_result or MeasurementResult(
            thickness_nm=150.0, goodness_of_fit=0.95,
        )
        self.command_history: list[str] = []

    # ── BaseInstrument interface ──────────────────────────────────────────

    def connect(self) -> None:
        self._connected = True
        self.logger.info("MockFilmetrics connected")

    def disconnect(self) -> None:
        self._connected = False
        self.logger.info("MockFilmetrics disconnected")

    def health_check(self) -> bool:
        return self._connected

    # ── Filmetrics-specific commands ──────────────────────────────────────

    def acquire_sample(self) -> None:
        self.command_history.append("sample")

    def acquire_reference(self, reference_standard: str) -> None:
        self.command_history.append(f"reference {reference_standard}")

    def acquire_background(self) -> None:
        self.command_history.append("background")

    def commit_baseline(self) -> None:
        self.command_history.append("commit")

    def measure(self) -> MeasurementResult:
        self.command_history.append("measure")
        return self._default_result

    def save_spectrum(self, identifier: str) -> None:
        self.command_history.append(f"save {identifier}")
