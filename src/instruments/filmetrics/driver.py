import re
import subprocess
import time
from typing import Optional

from src.instruments.base_instrument import BaseInstrument
from src.instruments.filmetrics.exceptions import (
    FilmetricsConnectionError,
    FilmetricsCommandError,
)
from src.instruments.filmetrics.models import MeasurementResult

_SUCCESS_SENTINELS = ("complete", "successfully")
_ERROR_SENTINELS = ("error", "exception")


class Filmetrics(BaseInstrument):
    """Driver for the Filmetrics film thickness measurement system.

    Communicates with a C# console app (FilmetricsTool.exe) via stdin/stdout.
    """

    def __init__(
        self,
        exe_path: str,
        recipe_name: str,
        command_timeout: float = 30.0,
        name: Optional[str] = None,
    ):
        super().__init__(name=name)
        self._exe_path = exe_path
        self._recipe_name = recipe_name
        self._command_timeout = command_timeout
        self._process: Optional[subprocess.Popen] = None

    # ── BaseInstrument interface ──────────────────────────────────────────

    def connect(self) -> None:
        try:
            self._process = subprocess.Popen(
                [self._exe_path, self._recipe_name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError as exc:
            raise FilmetricsConnectionError(
                f"Filmetrics exe not found: {self._exe_path}"
            ) from exc

        self._wait_for_init()
        self.logger.info("Connected to Filmetrics (pid=%s)", self._process.pid)

    def disconnect(self) -> None:
        if self._process is None:
            return
        try:
            self._process.stdin.write("exit\n")
            self._process.stdin.flush()
        except OSError:
            pass
        finally:
            try:
                self._process.stdin.close()
                self._process.stdout.close()
            except OSError:
                pass
            self._process.wait()
            self.logger.info("Disconnected from Filmetrics")
            self._process = None

    def health_check(self) -> bool:
        return self._process is not None and self._process.poll() is None

    # ── Filmetrics-specific commands ──────────────────────────────────────

    def acquire_sample(self) -> None:
        self._send_command("sample")

    def acquire_reference(self, reference_standard: str) -> None:
        self._send_command(f"reference {reference_standard}")

    def acquire_background(self) -> None:
        self._send_command("background")

    def commit_baseline(self) -> None:
        self._send_command("commit")

    def measure(self) -> MeasurementResult:
        lines = self._send_command("measure")
        return MeasurementResult(
            thickness_nm=self._parse_thickness(lines),
            goodness_of_fit=self._parse_goodness_of_fit(lines),
        )

    def save_spectrum(self, identifier: str) -> None:
        """Placeholder — data saving will be a separate cross-instrument process."""
        self._send_command(f"save {identifier}")

    # ── Private helpers ───────────────────────────────────────────────────

    def _wait_for_init(self) -> None:
        """Read stdout until the C# app signals initialisation is complete.

        The C# app uses Console.Write (no newline) for init messages,
        so we read character-by-character instead of using readline().
        """
        buffer = ""
        deadline = time.monotonic() + self._command_timeout
        while time.monotonic() < deadline:
            char = self._process.stdout.read(1)
            if not char:
                raise FilmetricsConnectionError("Process exited during init")
            buffer += char
            if "complete" in buffer.lower():
                return
        raise FilmetricsConnectionError("Timed out waiting for init")

    def _send_command(self, command: str) -> list[str]:
        """Send a command string and collect output until a sentinel.

        Returns lines on success. Raises FilmetricsCommandError if the C#
        app responds with an error/exception message, times out, or the
        process exits.
        """
        self._process.stdin.write(command + "\n")
        self._process.stdin.flush()

        lines: list[str] = []
        deadline = time.monotonic() + self._command_timeout
        while time.monotonic() < deadline:
            line = self._process.stdout.readline()
            if not line:
                raise FilmetricsCommandError(
                    f"Process ended while waiting for response to '{command}'"
                )
            stripped = line.strip()
            lines.append(stripped)
            low = stripped.lower()
            if any(s in low for s in _SUCCESS_SENTINELS):
                return lines
            if any(s in low for s in _ERROR_SENTINELS):
                raise FilmetricsCommandError(
                    f"Command '{command}' failed: {stripped}"
                )

        raise FilmetricsCommandError(
            f"Timed out ({self._command_timeout}s) waiting for '{command}' to complete"
        )

    @staticmethod
    def _parse_thickness(lines: list[str]) -> Optional[float]:
        """Extract thickness in nm from Polyimide result lines."""
        thickness = None
        for line in lines:
            if "Polyimide" in line:
                matches = re.findall(r"([-+]?\d*\.?\d+)\s*nm", line, re.IGNORECASE)
                if matches:
                    try:
                        thickness = float(matches[-1])
                    except ValueError:
                        pass
        return thickness

    @staticmethod
    def _parse_goodness_of_fit(lines: list[str]) -> Optional[float]:
        """Extract Goodness of Fit value from output lines."""
        for line in lines:
            if "Goodness of fit" in line:
                match = re.search(r"[-+]?\d*\.?\d+|\d+", line)
                if match:
                    try:
                        return float(match.group())
                    except ValueError:
                        pass
        return None
