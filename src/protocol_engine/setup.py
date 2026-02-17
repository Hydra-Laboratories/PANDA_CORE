"""Protocol setup: load all configs, validate, and return a ready-to-run protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple
from unittest.mock import MagicMock

from src.board.errors import BoardLoaderError
from src.board.loader import load_board_from_yaml
from src.deck.errors import DeckLoaderError
from src.deck.loader import load_deck_from_yaml
from src.gantry import Gantry
from src.gantry.errors import GantryLoaderError
from src.gantry.loader import load_gantry_from_yaml
from src.protocol_engine.errors import ProtocolLoaderError
from src.protocol_engine.loader import load_protocol_from_yaml
from src.protocol_engine.protocol import Protocol, ProtocolContext
from src.validation.bounds import validate_deck_positions, validate_gantry_positions
from src.validation.errors import SetupValidationError


def _default_mock_gantry() -> MagicMock:
    """Create a mock gantry for offline validation and testing."""
    gantry = MagicMock(spec=Gantry)
    gantry.get_coordinates.return_value = {"x": 0.0, "y": 0.0, "z": 0.0}
    return gantry


def setup_protocol(
    gantry_path: str | Path,
    deck_path: str | Path,
    board_path: str | Path,
    protocol_path: str | Path,
    gantry: Gantry | None = None,
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
        gantry: Optional Gantry instance. If None, a mock is used for offline validation.

    Returns:
        Tuple of (Protocol, ProtocolContext) ready for ``protocol.run(context)``.

    Raises:
        GantryLoaderError: If gantry YAML is invalid or missing.
        DeckLoaderError: If deck YAML is invalid or missing.
        BoardLoaderError: If board YAML is invalid or missing.
        ProtocolLoaderError: If protocol YAML is invalid or missing.
        SetupValidationError: If any positions violate gantry bounds.
    """
    gantry_config = _load_gantry(gantry_path)
    deck = _load_deck(deck_path)

    if gantry is None:
        gantry = _default_mock_gantry()
    board = _load_board(board_path, gantry)

    protocol = _load_protocol(protocol_path)

    violations = validate_deck_positions(gantry_config, deck)
    violations.extend(validate_gantry_positions(gantry_config, deck, board))
    if violations:
        raise SetupValidationError(violations)

    context = ProtocolContext(board=board, deck=deck, gantry=gantry_config)
    return protocol, context


def _load_gantry(path: str | Path):
    """Load gantry config with user-friendly errors."""
    try:
        return load_gantry_from_yaml(path)
    except Exception as exc:
        if isinstance(exc, GantryLoaderError):
            raise
        raise GantryLoaderError(str(exc)) from exc


def _load_deck(path: str | Path):
    """Load deck with user-friendly errors."""
    try:
        return load_deck_from_yaml(path)
    except Exception as exc:
        if isinstance(exc, DeckLoaderError):
            raise
        raise DeckLoaderError(str(exc)) from exc


def _load_board(path: str | Path, gantry):
    """Load board with user-friendly errors."""
    try:
        return load_board_from_yaml(path, gantry)
    except Exception as exc:
        if isinstance(exc, BoardLoaderError):
            raise
        raise BoardLoaderError(str(exc)) from exc


def _load_protocol(path: str | Path):
    """Load protocol with user-friendly errors."""
    try:
        return load_protocol_from_yaml(path)
    except Exception as exc:
        if isinstance(exc, ProtocolLoaderError):
            raise
        raise ProtocolLoaderError(str(exc)) from exc
