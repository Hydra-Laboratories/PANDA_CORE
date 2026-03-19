from instruments.base_instrument import InstrumentError


class UVCuringError(InstrumentError):
    """Base exception for all UV curing instrument errors."""


class UVCuringConnectionError(UVCuringError):
    """Raised when the UV LED controller cannot be found or opened."""


class UVCuringCommandError(UVCuringError):
    """Raised when a UV command fails (e.g. serial write error)."""


class UVCuringTimeoutError(UVCuringError):
    """Raised when the UV controller does not respond within the timeout."""
