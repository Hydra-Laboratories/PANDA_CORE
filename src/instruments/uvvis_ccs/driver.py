import ctypes as C
import time
from typing import Optional

from instruments.base_instrument import BaseInstrument
from instruments.uvvis_ccs.exceptions import (
    UVVisCCSConnectionError,
    UVVisCCSMeasurementError,
    UVVisCCSTimeoutError,
)
from instruments.uvvis_ccs.models import NUM_PIXELS, UVVisSpectrum

# Status bitmask flags returned by tlccs_getDeviceStatus
_STATUS_IDLE = 0x0002
_STATUS_SCAN_READY = 0x0010

_IDLE_TIMEOUT_S = 5.0
_POLL_INTERVAL_S = 0.05


class UVVisCCS(BaseInstrument):
    """Driver for the Thorlabs CCS-series compact spectrometer.

    Communicates with the instrument through the Thorlabs TLCCS DLL via ctypes.
    Designed for the CCS100/CCS175/CCS200 family (3648-pixel linear CCD).
    """

    def __init__(
        self,
        serial_number: str,
        dll_path: str = "TLCCS_64.dll",
        default_integration_time_s: float = 0.24,
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
        self._serial_number = serial_number
        self._dll_path = dll_path
        self._default_integration_time_s = default_integration_time_s

        self._dll = None
        self._handle: Optional[C.c_uint32] = None
        self._wavelengths: Optional[tuple[float, ...]] = None

    # ── BaseInstrument interface ──────────────────────────────────────────

    def connect(self) -> None:
        try:
            self._dll = C.cdll.LoadLibrary(self._dll_path)
        except OSError as exc:
            raise UVVisCCSConnectionError(
                f"Failed to load DLL: {self._dll_path}"
            ) from exc

        self._configure_dll_prototypes()

        resource = (
            f"USB0::0x1313::0x8081::{self._serial_number}::RAW"
        ).encode("ascii")
        self._handle = C.c_uint32()

        rc = self._dll.tlccs_init(
            resource, True, True, C.byref(self._handle)
        )
        if rc != 0:
            raise UVVisCCSConnectionError(
                f"tlccs_init failed with code {rc} for serial {self._serial_number}"
            )

        self._load_wavelength_data()
        self.set_integration_time(self._default_integration_time_s)
        self.logger.info(
            "Connected to CCS spectrometer (serial=%s)", self._serial_number
        )

    def disconnect(self) -> None:
        if self._handle is None:
            return
        try:
            self._dll.tlccs_close(self._handle)
        except OSError:
            pass
        finally:
            self.logger.info("Disconnected from CCS spectrometer")
            self._handle = None

    def health_check(self) -> bool:
        if self._handle is None:
            return False
        try:
            self._get_status()
            return True
        except Exception:
            return False

    # ── UVVis-specific commands ───────────────────────────────────────────

    def set_integration_time(self, seconds: float) -> None:
        self._dll.tlccs_setIntegrationTime(self._handle, seconds)

    def get_integration_time(self) -> float:
        t = C.c_double()
        self._dll.tlccs_getIntegrationTime(self._handle, C.byref(t))
        return t.value

    def measure(self) -> UVVisSpectrum:
        """Trigger a scan and return the spectrum.

        Waits for the spectrometer to become idle, starts a scan, polls
        until data is ready, then reads and returns the result.
        """
        self._wait_for_idle()

        self._dll.tlccs_startScan(self._handle)

        integration_time = self.get_integration_time()
        self._wait_for_scan_ready(integration_time)

        data = (NUM_PIXELS * C.c_double)()
        rc = self._dll.tlccs_getScanData(self._handle, data)
        if rc != 0:
            raise UVVisCCSMeasurementError(
                f"tlccs_getScanData failed with code {rc}"
            )

        intensities = tuple(data)
        return UVVisSpectrum(
            wavelengths=self._wavelengths,
            intensities=intensities,
            integration_time_s=integration_time,
        )

    def get_device_info(self) -> list[str]:
        """Return identification strings [manufacturer, device, serial, firmware, driver]."""
        buffers = [(256 * C.c_char)() for _ in range(5)]
        self._dll.tlccs_identificationQuery(self._handle, *buffers)
        return [buf.value.decode() for buf in buffers]

    # ── Private helpers ───────────────────────────────────────────────────

    def _configure_dll_prototypes(self) -> None:
        """Set argtypes and restype for each DLL function we use."""
        dll = self._dll

        dll.tlccs_init.argtypes = [
            C.c_char_p, C.c_bool, C.c_bool, C.POINTER(C.c_uint32),
        ]
        dll.tlccs_init.restype = C.c_int

        dll.tlccs_identificationQuery.argtypes = [
            C.c_uint32, C.c_char_p, C.c_char_p,
            C.c_char_p, C.c_char_p, C.c_char_p,
        ]
        dll.tlccs_identificationQuery.restype = C.c_int

        dll.tlccs_getWavelengthData.argtypes = [
            C.c_uint32, C.c_int16,
            C.POINTER(C.c_double), C.POINTER(C.c_double), C.POINTER(C.c_double),
        ]
        dll.tlccs_getWavelengthData.restype = C.c_int

        dll.tlccs_getDeviceStatus.argtypes = [
            C.c_uint32, C.POINTER(C.c_int32),
        ]
        dll.tlccs_getDeviceStatus.restype = C.c_int

        dll.tlccs_setIntegrationTime.argtypes = [C.c_uint32, C.c_double]
        dll.tlccs_setIntegrationTime.restype = C.c_int

        dll.tlccs_getIntegrationTime.argtypes = [
            C.c_uint32, C.POINTER(C.c_double),
        ]
        dll.tlccs_getIntegrationTime.restype = C.c_int

        dll.tlccs_startScan.argtypes = [C.c_uint32]
        dll.tlccs_startScan.restype = C.c_int

        dll.tlccs_getScanData.argtypes = [C.c_uint32, C.POINTER(C.c_double)]
        dll.tlccs_getScanData.restype = C.c_int

        dll.tlccs_close.argtypes = [C.c_uint32]
        dll.tlccs_close.restype = C.c_int

    def _load_wavelength_data(self) -> None:
        """Pre-load the wavelength calibration array from the device."""
        data = (NUM_PIXELS * C.c_double)()
        wmin = C.c_double()
        wmax = C.c_double()

        rc = self._dll.tlccs_getWavelengthData(
            self._handle, 0, data, C.byref(wmin), C.byref(wmax),
        )
        if rc != 0:
            raise UVVisCCSConnectionError(
                f"tlccs_getWavelengthData failed with code {rc}"
            )

        self._wavelengths = tuple(data)

    def _get_status(self) -> tuple[bool, bool]:
        """Query device status flags.

        Returns:
            (idle, scan_ready) booleans.
        """
        status = C.c_int32()
        self._dll.tlccs_getDeviceStatus(self._handle, C.byref(status))
        idle = bool(status.value & _STATUS_IDLE)
        scan_ready = bool(status.value & _STATUS_SCAN_READY)
        return idle, scan_ready

    def _wait_for_idle(self) -> None:
        """Block until the spectrometer reports idle."""
        deadline = time.monotonic() + _IDLE_TIMEOUT_S
        while time.monotonic() < deadline:
            idle, _ = self._get_status()
            if idle:
                return
            time.sleep(_POLL_INTERVAL_S)
        raise UVVisCCSTimeoutError(
            f"Spectrometer not idle after {_IDLE_TIMEOUT_S}s"
        )

    def _wait_for_scan_ready(self, integration_time: float) -> None:
        """Block until scan data is available."""
        poll = max(integration_time / 10, _POLL_INTERVAL_S)
        deadline = time.monotonic() + _IDLE_TIMEOUT_S
        while time.monotonic() < deadline:
            _, scan_ready = self._get_status()
            if scan_ready:
                return
            time.sleep(poll)
        raise UVVisCCSTimeoutError(
            f"Scan not ready after {_IDLE_TIMEOUT_S}s"
        )
