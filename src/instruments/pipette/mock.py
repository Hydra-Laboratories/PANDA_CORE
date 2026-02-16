from typing import Optional

from src.instruments.base_instrument import BaseInstrument
from src.instruments.pipette.exceptions import PipetteConfigError
from src.instruments.pipette.models import (
    AspirateResult,
    MixResult,
    PipetteConfig,
    PipetteStatus,
    PIPETTE_MODELS,
)


class MockPipette(BaseInstrument):
    """In-memory mock of the Pipette instrument for testing."""

    def __init__(
        self,
        pipette_model: str = "p300_single_gen2",
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
        if pipette_model not in PIPETTE_MODELS:
            raise PipetteConfigError(
                f"Unknown pipette model '{pipette_model}'. "
                f"Available: {', '.join(sorted(PIPETTE_MODELS.keys()))}"
            )
        self._config: PipetteConfig = PIPETTE_MODELS[pipette_model]
        self._connected = False
        self._has_tip = False
        self._position_mm = 0.0
        self._is_homed = False
        self._is_primed = False
        self.command_history: list[str] = []

    @property
    def config(self) -> PipetteConfig:
        return self._config

    # ── BaseInstrument interface ──────────────────────────────────────────

    def connect(self) -> None:
        self._connected = True
        self.logger.info("MockPipette connected")

    def disconnect(self) -> None:
        self._connected = False
        self.logger.info("MockPipette disconnected")

    def health_check(self) -> bool:
        return self._connected

    def warm_up(self) -> None:
        self.home()
        self.prime()

    # ── Pipette-specific commands ─────────────────────────────────────────

    def home(self) -> None:
        self.command_history.append("home")
        self._position_mm = self._config.zero_position
        self._is_homed = True

    def prime(self, speed: float = 50.0) -> None:
        self.command_history.append(f"prime speed={speed}")
        self._position_mm = self._config.prime_position
        self._is_primed = True

    def aspirate(self, volume_ul: float, speed: float = 50.0) -> AspirateResult:
        self.command_history.append(f"aspirate {volume_ul}uL speed={speed}")
        mm_travel = volume_ul * self._config.mm_to_ul
        self._position_mm += mm_travel
        return AspirateResult(
            success=True, volume_ul=volume_ul, position_mm=self._position_mm
        )

    def dispense(self, volume_ul: float, speed: float = 50.0) -> AspirateResult:
        self.command_history.append(f"dispense {volume_ul}uL speed={speed}")
        mm_travel = volume_ul * self._config.mm_to_ul
        self._position_mm -= mm_travel
        return AspirateResult(
            success=True, volume_ul=volume_ul, position_mm=self._position_mm
        )

    def blowout(self, speed: float = 50.0) -> None:
        self.command_history.append(f"blowout speed={speed}")
        self._position_mm = self._config.blowout_position

    def mix(
        self, volume_ul: float, repetitions: int = 3, speed: float = 50.0
    ) -> MixResult:
        self.command_history.append(
            f"mix {volume_ul}uL reps={repetitions} speed={speed}"
        )
        return MixResult(
            success=True, volume_ul=volume_ul, repetitions=repetitions
        )

    def pick_up_tip(self, speed: float = 50.0) -> None:
        self.command_history.append("pick_up_tip")
        self._has_tip = True

    def drop_tip(self, speed: float = 50.0) -> None:
        self.command_history.append("drop_tip")
        self._has_tip = False
        self._position_mm = self._config.drop_tip_position

    def get_status(self) -> PipetteStatus:
        self.command_history.append("get_status")
        return PipetteStatus(
            is_homed=self._is_homed,
            position_mm=self._position_mm,
            max_volume=self._config.max_volume,
            has_tip=self._has_tip,
            is_primed=self._is_primed,
        )

    def drip_stop(self, volume_ul: float = 5.0, speed: float = 50.0) -> None:
        self.command_history.append(f"drip_stop {volume_ul}uL speed={speed}")
