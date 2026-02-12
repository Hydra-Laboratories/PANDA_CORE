import threading
import time
from typing import Optional

import serial

from src.instruments.base_instrument import BaseInstrument
from src.instruments.pipette.exceptions import (
    PipetteCommandError,
    PipetteConfigError,
    PipetteConnectionError,
    PipetteTimeoutError,
)
from src.instruments.pipette.models import (
    AspirateResult,
    MixResult,
    PipetteConfig,
    PipetteStatus,
    PIPETTE_MODELS,
)

# Pawduino command codes
_CMD_HOME = 10
_CMD_MOVE_TO = 11
_CMD_ASPIRATE = 12
_CMD_DISPENSE = 13
_CMD_STATUS = 14
_CMD_MIX = 15
_CMD_DRIP_STOP = 28

_ARDUINO_SETTLE_TIME = 2.0


class Pipette(BaseInstrument):
    """Driver for Opentrons pipettes via Arduino serial (Pawduino firmware).

    Supports OT-2 and Flex pipette models. The pipette model determines
    plunger positions and volume conversion factors.
    """

    def __init__(
        self,
        pipette_model: str,
        port: str,
        baud_rate: int = 115200,
        command_timeout: float = 30.0,
        name: Optional[str] = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        depth: float = 0.0,
    ):
        super().__init__(name=name, offset_x=offset_x, offset_y=offset_y, depth=depth)
        if pipette_model not in PIPETTE_MODELS:
            raise PipetteConfigError(
                f"Unknown pipette model '{pipette_model}'. "
                f"Available: {', '.join(sorted(PIPETTE_MODELS.keys()))}"
            )
        self._config: PipetteConfig = PIPETTE_MODELS[pipette_model]
        self._port = port
        self._baud_rate = baud_rate
        self._command_timeout = command_timeout
        self._serial: Optional[serial.Serial] = None
        self._lock = threading.Lock()
        self._has_tip = False

    @property
    def config(self) -> PipetteConfig:
        return self._config

    # ── BaseInstrument interface ──────────────────────────────────────────

    def connect(self) -> None:
        try:
            self._serial = serial.Serial(
                port=self._port,
                baudrate=self._baud_rate,
                timeout=self._command_timeout,
            )
        except serial.SerialException as exc:
            raise PipetteConnectionError(
                f"Cannot open serial port {self._port}: {exc}"
            ) from exc

        time.sleep(_ARDUINO_SETTLE_TIME)

        try:
            self.get_status()
        except (PipetteCommandError, PipetteTimeoutError) as exc:
            self._close_serial()
            raise PipetteConnectionError(
                f"Arduino did not respond after connect: {exc}"
            ) from exc

        self.logger.info(
            "Connected to %s on %s", self._config.name, self._port
        )

    def disconnect(self) -> None:
        self._close_serial()
        self.logger.info("Disconnected from pipette")

    def health_check(self) -> bool:
        if self._serial is None or not self._serial.is_open:
            return False
        try:
            self.get_status()
            return True
        except (PipetteCommandError, PipetteTimeoutError):
            return False

    def warm_up(self) -> None:
        self.home()
        self.prime()

    # ── Pipette-specific commands ─────────────────────────────────────────

    def home(self) -> None:
        """Home plunger to zero position."""
        self._send_command(_CMD_HOME)
        self.logger.debug("Plunger homed")

    def prime(self, speed: float = 50.0) -> None:
        """Move plunger to prime position."""
        self._send_command(_CMD_MOVE_TO, self._config.prime_position, speed)
        self.logger.debug("Plunger primed to %.1f mm", self._config.prime_position)

    def aspirate(self, volume_ul: float, speed: float = 50.0) -> AspirateResult:
        """Aspirate a volume of liquid.

        Sends the aspirate command with the volume converted to mm of
        plunger travel via the mm_to_ul conversion factor.
        """
        mm_travel = volume_ul * self._config.mm_to_ul
        response = self._send_command(_CMD_ASPIRATE, mm_travel, speed)
        position = self._parse_position(response)
        return AspirateResult(
            success=True, volume_ul=volume_ul, position_mm=position
        )

    def dispense(self, volume_ul: float, speed: float = 50.0) -> AspirateResult:
        """Dispense a volume of liquid."""
        mm_travel = volume_ul * self._config.mm_to_ul
        response = self._send_command(_CMD_DISPENSE, mm_travel, speed)
        position = self._parse_position(response)
        return AspirateResult(
            success=True, volume_ul=volume_ul, position_mm=position
        )

    def blowout(self, speed: float = 50.0) -> None:
        """Move plunger to blowout position to expel remaining liquid."""
        self._send_command(_CMD_MOVE_TO, self._config.blowout_position, speed)
        self.logger.debug("Blowout to %.1f mm", self._config.blowout_position)

    def mix(
        self, volume_ul: float, repetitions: int = 3, speed: float = 50.0
    ) -> MixResult:
        """Perform repeated aspirate/dispense cycles."""
        mm_travel = volume_ul * self._config.mm_to_ul
        self._send_command(_CMD_MIX, mm_travel, repetitions, speed)
        return MixResult(
            success=True, volume_ul=volume_ul, repetitions=repetitions
        )

    def pick_up_tip(self, speed: float = 50.0) -> None:
        """Seat pipette into a tip."""
        self._send_command(_CMD_MOVE_TO, self._config.zero_position, speed)
        self._has_tip = True
        self.logger.debug("Tip picked up")

    def drop_tip(self, speed: float = 50.0) -> None:
        """Eject the current tip."""
        self._send_command(_CMD_MOVE_TO, self._config.drop_tip_position, speed)
        self._has_tip = False
        self.logger.debug("Tip dropped")

    def get_status(self) -> PipetteStatus:
        """Query Arduino for current pipette state."""
        response = self._send_command(_CMD_STATUS)
        parsed = self._parse_key_value(response)
        return PipetteStatus(
            is_homed=parsed.get("homed", 0) == 1,
            position_mm=float(parsed.get("pos", 0.0)),
            max_volume=float(parsed.get("max_vol", self._config.max_volume)),
            has_tip=self._has_tip,
            is_primed=parsed.get("primed", 0) == 1,
        )

    def drip_stop(self, volume_ul: float = 5.0, speed: float = 50.0) -> None:
        """Small relative aspirate (air) to prevent dripping after dispense."""
        mm_travel = volume_ul * self._config.mm_to_ul
        self._send_command(_CMD_DRIP_STOP, mm_travel, speed)
        self.logger.debug("Drip stop: %.1f uL air aspirated", volume_ul)

    # ── Private helpers ───────────────────────────────────────────────────

    def _send_command(self, code: int, *args: float) -> str:
        """Send a command to the Arduino and return the response.

        Protocol: sends ``"code,arg1,arg2\\n"``
        Expects response starting with ``"OK:{...}"`` or ``"ERR:..."``
        Thread-safe via lock.
        """
        if self._serial is None or not self._serial.is_open:
            raise PipetteCommandError("Not connected to Arduino")

        parts = [str(code)] + [str(a) for a in args]
        message = ",".join(parts) + "\n"

        with self._lock:
            try:
                self._serial.write(message.encode())
                self._serial.flush()
            except serial.SerialException as exc:
                raise PipetteCommandError(
                    f"Failed to send command {code}: {exc}"
                ) from exc

            deadline = time.monotonic() + self._command_timeout
            while time.monotonic() < deadline:
                try:
                    line = self._serial.readline().decode().strip()
                except serial.SerialException as exc:
                    raise PipetteCommandError(
                        f"Serial read error for command {code}: {exc}"
                    ) from exc

                if not line:
                    continue

                if line.startswith("OK:"):
                    return line

                if line.startswith("ERR:"):
                    raise PipetteCommandError(
                        f"Command {code} failed: {line}"
                    )

            raise PipetteTimeoutError(
                f"Timed out ({self._command_timeout}s) waiting for "
                f"response to command {code}"
            )

    @staticmethod
    def _parse_key_value(response: str) -> dict[str, float]:
        """Parse ``OK:{key1:val1,key2:val2}`` into a dict of floats.

        The Pawduino firmware returns a custom key:value format (not JSON).
        Example: ``OK:{homed:1,pos:10.5,max_vol:200}``
        """
        result: dict[str, float] = {}
        body = response.removeprefix("OK:").strip()
        if body.startswith("{") and body.endswith("}"):
            body = body[1:-1]
        for pair in body.split(","):
            if ":" not in pair:
                continue
            key, _, val = pair.partition(":")
            try:
                result[key.strip()] = float(val.strip())
            except ValueError:
                continue
        return result

    @staticmethod
    def _parse_position(response: str) -> float:
        """Extract position_mm from an OK response."""
        parsed = Pipette._parse_key_value(response)
        return float(parsed.get("pos", 0.0))

    def _close_serial(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except serial.SerialException:
                pass
            self._serial = None
