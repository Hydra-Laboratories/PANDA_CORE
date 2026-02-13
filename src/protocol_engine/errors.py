"""Protocol engine exception types."""


class ProtocolLoaderError(Exception):
    """Human-friendly protocol loader error intended for CLI output."""


class ProtocolExecutionError(Exception):
    """Error raised during protocol step execution."""
