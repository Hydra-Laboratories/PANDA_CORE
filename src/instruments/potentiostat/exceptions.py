from instruments.base_instrument import InstrumentError


class PotentiostatError(InstrumentError):
    """Base exception for all potentiostat errors."""


class PotentiostatConfigError(PotentiostatError):
    """Raised when the CubOS potentiostat configuration is invalid."""


class PotentiostatConnectionError(PotentiostatError):
    """Raised when the potentiostat cannot be connected."""


class PotentiostatMeasurementError(PotentiostatError):
    """Raised when an electrochemistry measurement fails."""


class PotentiostatTimeoutError(PotentiostatError):
    """Raised when a potentiostat operation does not complete in time."""


class PotentiostatPlatformError(PotentiostatError):
    """Raised when a vendor backend is unsupported on the current platform."""
