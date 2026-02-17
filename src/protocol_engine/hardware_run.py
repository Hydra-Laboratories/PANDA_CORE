"""Execute protocol steps on gantry hardware with mount offsets."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.deck import load_deck_from_yaml_safe
from src.gantry import Gantry

from .board import Board
from .loader import load_protocol_from_yaml_safe
from .protocol import ProtocolContext


@dataclass(frozen=True)
class MountedInstrument:
    """Minimal mounted tool model used by Board for offset math."""

    name: str
    offset_x: float = 0.0
    offset_y: float = 0.0
    depth: float = 0.0


@dataclass(frozen=True)
class HardwareRunOptions:
    """Options required for executing a protocol on gantry hardware."""

    deck_path: Path
    protocol_path: Path
    gantry_config_path: Path
    instrument_name: str = "pipette"
    instrument_offset_x: float = 0.0
    instrument_offset_y: float = 0.0
    instrument_depth: float = 0.0
    home_before_run: bool = True
    require_healthy: bool = True


def _load_gantry_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError("Gantry config must be a YAML mapping/object.")
    return loaded


def run_protocol_on_gantry(options: HardwareRunOptions) -> list[Any]:
    """Run protocol on connected gantry hardware using one mounted instrument."""
    config = _load_gantry_config(options.gantry_config_path)
    gantry = Gantry(config=config)

    mounted = MountedInstrument(
        name=options.instrument_name,
        offset_x=options.instrument_offset_x,
        offset_y=options.instrument_offset_y,
        depth=options.instrument_depth,
    )
    board = Board(gantry=gantry, instruments={options.instrument_name: mounted})

    deck = load_deck_from_yaml_safe(options.deck_path)
    protocol = load_protocol_from_yaml_safe(options.protocol_path)

    context = ProtocolContext(
        board=board,
        deck=deck,
        logger=logging.getLogger("protocol.hardware_run"),
    )

    gantry.connect()
    try:
        if options.require_healthy and not gantry.is_healthy():
            raise RuntimeError("Gantry health check failed after connect.")
        if options.home_before_run:
            gantry.home()
        return protocol.run(context)
    finally:
        gantry.disconnect()
