"""Protocol setup: load all configs, validate, and return a ready-to-run protocol."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional, Tuple

from board.board import Board
from board.loader import load_board_from_yaml_safe
from deck.deck import Deck
from deck.labware.vial import Vial
from deck.labware.well_plate import WellPlate
from deck.loader import load_deck_from_yaml_safe
from gantry.gantry_config import GantryConfig
from gantry.loader import load_gantry_from_yaml_safe
from gantry.offline import OfflineGantry
from protocol_engine.loader import load_protocol_from_yaml_safe
from protocol_engine.protocol import Protocol, ProtocolContext
from protocol_engine.volume_tracker import VolumeTracker
from validation.bounds import validate_deck_positions, validate_gantry_positions
from validation.errors import SetupValidationError

logger = logging.getLogger(__name__)


def _read_file_text(path: str | Path) -> str:
    """Read a file and return its text content."""
    return Path(path).read_text()


def _register_deck_labware(
    deck: Deck,
    tracker: VolumeTracker,
    data_store: Any,
    campaign_id: int,
) -> None:
    """Register all deck labware with both VolumeTracker and DataStore."""
    for key, labware in deck.labware.items():
        if isinstance(labware, Vial):
            initial = getattr(labware, "initial_volume_ul", 0.0)
            tracker.register_labware(key, labware, initial_volume_ul=initial)
        elif isinstance(labware, WellPlate):
            tracker.register_labware(key, labware)
        data_store.register_labware(campaign_id, key, labware)
        logger.info("Registered labware '%s' for tracking", key)


def setup_protocol(
    gantry_path: str | Path,
    deck_path: str | Path,
    board_path: str | Path,
    protocol_path: str | Path,
    gantry=None,
    db_path: Optional[str] = None,
) -> Tuple[Protocol, ProtocolContext]:
    """Load all configs, validate bounds, and return a ready-to-run protocol.

    Args:
        gantry_path: Path to gantry YAML config.
        deck_path: Path to deck YAML config.
        board_path: Path to board YAML config.
        protocol_path: Path to protocol YAML config.
        gantry: Optional Gantry instance. If None, an OfflineGantry is used.
        db_path: Optional SQLite database path. When provided, a DataStore
            and VolumeTracker are created and attached to the context.

    Returns:
        Tuple of (Protocol, ProtocolContext) ready for ``protocol.run(context)``.
    """
    gantry_config: GantryConfig = load_gantry_from_yaml_safe(gantry_path)
    deck: Deck = load_deck_from_yaml_safe(
        deck_path,
        total_z_height=gantry_config.total_z_height,
    )

    if gantry is None:
        gantry = OfflineGantry()
    board: Board = load_board_from_yaml_safe(board_path, gantry)

    protocol: Protocol = load_protocol_from_yaml_safe(protocol_path)

    violations = validate_deck_positions(gantry_config, deck)
    violations.extend(validate_gantry_positions(gantry_config, deck, board))
    if violations:
        raise SetupValidationError(violations)

    data_store = None
    campaign_id = None
    volume_tracker = None

    if db_path is not None:
        from data.data_store import DataStore

        data_store = DataStore(db_path)
        campaign_id = data_store.create_campaign(
            description=f"Protocol: {Path(protocol_path).name}",
            gantry_config=_read_file_text(gantry_path),
            deck_config=_read_file_text(deck_path),
            board_config=_read_file_text(board_path),
            protocol_config=_read_file_text(protocol_path),
        )
        volume_tracker = VolumeTracker()
        _register_deck_labware(deck, volume_tracker, data_store, campaign_id)
        logger.info("Campaign %d created with data tracking enabled", campaign_id)

    context = ProtocolContext(
        board=board,
        deck=deck,
        gantry=gantry_config,
        data_store=data_store,
        campaign_id=campaign_id,
        volume_tracker=volume_tracker,
    )
    return protocol, context


def run_protocol(
    gantry_path: str | Path,
    deck_path: str | Path,
    board_path: str | Path,
    protocol_path: str | Path,
    gantry=None,
    db_path: Optional[str] = None,
) -> List[Any]:
    """Load configs, validate, and execute the protocol in one call.

    Convenience wrapper around ``setup_protocol`` + ``protocol.run(context)``.

    Returns:
        List of step results from protocol execution.
    """
    protocol, context = setup_protocol(
        gantry_path, deck_path, board_path, protocol_path,
        gantry=gantry, db_path=db_path,
    )
    try:
        return protocol.run(context)
    finally:
        if context.data_store is not None:
            context.data_store.close()
