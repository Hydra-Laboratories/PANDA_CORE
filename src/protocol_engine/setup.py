"""Protocol setup: load all configs, validate, and return a ready-to-run protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from board.board import Board
from board.loader import load_board_from_yaml_safe
from deck.deck import Deck
from deck.loader import load_deck_from_yaml_safe
from gantry.gantry_config import GantryConfig
from gantry.loader import load_gantry_from_yaml_safe
from gantry.offline import OfflineGantry
from protocol_engine.loader import load_protocol_from_yaml_safe
from protocol_engine.protocol import Protocol, ProtocolContext
from validation.bounds import validate_deck_positions, validate_gantry_positions
from validation.errors import SetupValidationError


def setup_protocol(
    gantry_path: str | Path,
    deck_path: str | Path,
    board_path: str | Path,
    protocol_path: str | Path,
    gantry=None,
) -> Tuple[Protocol, ProtocolContext]:
    """Load all configs, validate bounds, and return a ready-to-run protocol.

    Steps:
        1. Load gantry config (working volume, homing strategy)
        2. Load deck (labware positions)
        3. Load board (instruments with offsets)
        4. Load protocol (command steps)
        5. Validate all deck positions within gantry bounds
        6. Validate all gantry positions within gantry bounds
        7. Return (Protocol, ProtocolContext)

    Args:
        gantry_path: Path to gantry YAML config.
        deck_path: Path to deck YAML config.
        board_path: Path to board YAML config.
        protocol_path: Path to protocol YAML config.
        gantry: Optional Gantry instance. If None, an OfflineGantry is used
            for offline validation.

    Returns:
        Tuple of (Protocol, ProtocolContext) ready for ``protocol.run(context)``.

    Raises:
        GantryLoaderError: If gantry YAML is invalid or missing.
        DeckLoaderError: If deck YAML is invalid or missing.
        BoardLoaderError: If board YAML is invalid or missing.
        ProtocolLoaderError: If protocol YAML is invalid or missing.
        SetupValidationError: If any positions violate gantry bounds.
    """
    gantry_config: GantryConfig = load_gantry_from_yaml_safe(gantry_path)
    deck: Deck = load_deck_from_yaml_safe(deck_path)

    if gantry is None:
        gantry = OfflineGantry()
    board: Board = load_board_from_yaml_safe(board_path, gantry)

    protocol: Protocol = load_protocol_from_yaml_safe(protocol_path)

    violations = validate_deck_positions(gantry_config, deck)
    violations.extend(validate_gantry_positions(gantry_config, deck, board))
    if violations:
        raise SetupValidationError(violations)

    context = ProtocolContext(board=board, deck=deck, gantry=gantry_config)
    return protocol, context
