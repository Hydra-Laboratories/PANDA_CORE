from typing import Optional

from src.instruments.base_instrument import BaseInstrument
from src.instruments.uvvis_ccs.models import NUM_PIXELS, UVVisSpectrum


def _synthetic_spectrum(
    integration_time_s: float = 0.24,
    n_pixels: int = NUM_PIXELS,
) -> UVVisSpectrum:
    """Generate a flat synthetic spectrum for testing."""
    step = 600.0 / (n_pixels - 1)  # 200–800 nm range
    wavelengths = tuple(200.0 + i * step for i in range(n_pixels))
    intensities = tuple(0.5 for _ in range(n_pixels))
    return UVVisSpectrum(
        wavelengths=wavelengths,
        intensities=intensities,
        integration_time_s=integration_time_s,
    )


class MockUVVisCCS(BaseInstrument):
    """In-memory mock of the Thorlabs CCS spectrometer for testing."""

    def __init__(
        self,
        default_result: Optional[UVVisSpectrum] = None,
        name: Optional[str] = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        depth: float = 0.0,
    ):
        super().__init__(name=name, offset_x=offset_x, offset_y=offset_y, depth=depth)
        self._connected = False
        self._integration_time_s = 0.24
        self._default_result = default_result or _synthetic_spectrum()
        self.command_history: list[str] = []

    # ── BaseInstrument interface ──────────────────────────────────────────

    def connect(self) -> None:
        self._connected = True
        self.logger.info("MockUVVisCCS connected")

    def disconnect(self) -> None:
        self._connected = False
        self.logger.info("MockUVVisCCS disconnected")

    def health_check(self) -> bool:
        return self._connected

    # ── UVVis-specific commands ───────────────────────────────────────────

    def set_integration_time(self, seconds: float) -> None:
        self._integration_time_s = seconds
        self.command_history.append(f"set_integration_time {seconds}")

    def get_integration_time(self) -> float:
        self.command_history.append("get_integration_time")
        return self._integration_time_s

    def measure(self) -> UVVisSpectrum:
        self.command_history.append("measure")
        return self._default_result

    def get_device_info(self) -> list[str]:
        self.command_history.append("get_device_info")
        return [
            "Thorlabs", "CCS100", "MOCK_SERIAL", "1.0.0", "MockDriver",
        ]
