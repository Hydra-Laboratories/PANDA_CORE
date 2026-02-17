"""Programmatic (non-YAML) protocol definitions for three-well runs."""

from __future__ import annotations

from src.protocol_engine.protocol import Protocol, ProtocolStep

# Side-effect import to ensure command registration and handler availability.
from .commands.move import move

SAMPLE_THREE_WELL_TARGETS: tuple[str, str, str] = (
    "plate_1.A1",
    "plate_1.C8",
    "plate_1.B1",
)


def build_three_well_protocol(instrument: str = "pipette") -> Protocol:
    """Build the same 3-move protocol as the sample YAML, in pure Python."""
    steps = [
        ProtocolStep(
            index=index,
            command_name="move",
            handler=move,
            args={"instrument": instrument, "position": target},
        )
        for index, target in enumerate(SAMPLE_THREE_WELL_TARGETS)
    ]
    return Protocol(steps=steps)
