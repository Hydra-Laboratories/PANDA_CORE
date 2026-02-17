"""Mock-run helpers for previewing protocol move coordinates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.deck import load_deck_from_yaml_safe
from src.deck.labware.labware import Coordinate3D

from .loader import load_protocol_from_yaml_safe
from .protocol import ProtocolStep


@dataclass(frozen=True)
class MovePreviewStep:
    """Resolved preview for one move step in a protocol."""

    step_index: int
    instrument: str
    target: str
    coordinate: Coordinate3D


def _is_move_step(step: ProtocolStep) -> bool:
    return step.command_name == "move" and "position" in step.args and "instrument" in step.args


def preview_protocol_moves(
    deck_path: str | Path,
    protocol_path: str | Path,
) -> list[MovePreviewStep]:
    """Resolve all protocol move targets into absolute deck coordinates."""
    deck = load_deck_from_yaml_safe(deck_path)
    protocol = load_protocol_from_yaml_safe(protocol_path)

    preview_steps: list[MovePreviewStep] = []
    for step in protocol.steps:
        if not _is_move_step(step):
            continue
        target = str(step.args["position"])
        instrument = str(step.args["instrument"])
        coordinate = deck.resolve(target)
        preview_steps.append(
            MovePreviewStep(
                step_index=step.index,
                instrument=instrument,
                target=target,
                coordinate=coordinate,
            )
        )
    return preview_steps


def format_move_preview(steps: Iterable[MovePreviewStep]) -> str:
    """Render preview steps as terminal-friendly text output."""
    rows = list(steps)
    lines = [
        "MOCK RUN ONLY - no hardware commands are sent.",
        "",
        "Step | Instrument | Target     | X       | Y       | Z",
        "-----+------------+------------+---------+---------+--------",
    ]
    for row in rows:
        coord = row.coordinate
        lines.append(
            f"{row.step_index:>4} | "
            f"{row.instrument:<10} | "
            f"{row.target:<10} | "
            f"{coord.x:>7.3f} | "
            f"{coord.y:>7.3f} | "
            f"{coord.z:>6.3f}"
        )

    if not rows:
        lines.append("No move steps were found in the protocol.")
    return "\n".join(lines)
