"""Protocol commands package.

Importing this package triggers all @protocol_command decorators,
populating the CommandRegistry.
"""

from . import move  # noqa: F401 -- side-effect import for registration

__all__ = ["move"]
