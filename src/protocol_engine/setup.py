"""Protocol setup: load all configs, validate, and return a ready-to-run protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Tuple

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
    mock_mode: bool = False,
) -> Tuple[Protocol, ProtocolContext]:
    """Load all configs, validate bounds, and return a ready-to-run protocol.

    Args:
        gantry_path: Path to gantry YAML config.
        deck_path: Path to deck YAML config.
        board_path: Path to board YAML config.
        protocol_path: Path to protocol YAML config.
        gantry: Optional Gantry instance. If None, an OfflineGantry is used.
        mock_mode: If True, instruments are created in offline/mock mode.

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
    deck: Deck = load_deck_from_yaml_safe(
        deck_path,
        total_z_height=gantry_config.total_z_height,
    )

    if gantry is None:
        gantry = OfflineGantry()
    board: Board = load_board_from_yaml_safe(
        board_path, gantry, mock_mode=mock_mode,
    )

    protocol: Protocol = load_protocol_from_yaml_safe(protocol_path)

    violations = validate_deck_positions(gantry_config, deck)
    violations.extend(validate_gantry_positions(gantry_config, deck, board))
    if violations:
        raise SetupValidationError(violations)

    context = ProtocolContext(board=board, deck=deck, gantry=gantry_config)
    return protocol, context


def run_protocol(
    gantry_path: str | Path,
    deck_path: str | Path,
    board_path: str | Path,
    protocol_path: str | Path,
    gantry=None,
) -> List[Any]:
    """Load configs, validate, and execute the protocol in one call.

    Convenience wrapper around ``setup_protocol`` + ``protocol.run(context)``.

    Returns:
        List of step results from protocol execution.
    """
    protocol, context = setup_protocol(
        gantry_path, deck_path, board_path, protocol_path, gantry=gantry,
    )
    return protocol.run(context)
