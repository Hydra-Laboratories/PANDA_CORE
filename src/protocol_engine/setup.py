"""Protocol setup: load all configs, validate, and return a ready-to-run protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Tuple

from board.board import Board
from board.loader import (
    load_board_from_gantry_yaml_safe,
    load_board_from_yaml_safe,
)
from deck.deck import Deck
from deck.loader import load_deck_from_yaml_safe
from gantry.gantry import Gantry
from gantry.gantry_config import GantryConfig
from gantry.loader import load_gantry_from_yaml_safe
from protocol_engine.loader import load_protocol_from_yaml_safe
from protocol_engine.protocol import Protocol, ProtocolContext
from validation.bounds import validate_deck_positions, validate_gantry_positions
from validation.errors import ProtocolSemanticValidationError, SetupValidationError
from validation.protocol_semantics import validate_protocol_semantics


def _resolve_board_and_protocol_paths(
    gantry_path: str | Path,
    protocol_or_board_path: str | Path,
    legacy_protocol_path: str | Path | None,
) -> tuple[str | Path, str | Path, bool]:
    """Return board source, protocol path, and whether board is embedded."""
    if legacy_protocol_path is None:
        return gantry_path, protocol_or_board_path, True
    return protocol_or_board_path, legacy_protocol_path, False


def setup_protocol(
    gantry_path: str | Path,
    deck_path: str | Path,
    protocol_path: str | Path,
    legacy_protocol_path: str | Path | None = None,
    gantry: Gantry | None = None,
    mock_mode: bool = False,
) -> Tuple[Protocol, ProtocolContext]:
    """Load all configs, validate bounds, and return a ready-to-run protocol.

    Steps:
        1. Load gantry config (working volume, homing strategy, instruments)
        2. Load deck (labware positions)
        3. Load board from the gantry-embedded instruments
        4. Load protocol (command steps)
        5. Validate all deck positions within gantry bounds
        6. Validate all gantry positions within gantry bounds
        7. Return (Protocol, ProtocolContext)

    Args:
        gantry_path: Path to gantry YAML config.
        deck_path: Path to deck YAML config.
        protocol_path: Path to protocol YAML config. For legacy callers that
            still pass four positional paths, this may be a direct board YAML
            path and ``legacy_protocol_path`` carries the protocol YAML path.
        legacy_protocol_path: Optional protocol YAML path for the legacy
            four-path call shape.
        gantry: Optional Gantry instance. If None, an offline Gantry is used
            for validation.
        mock_mode: If True, instantiate real driver classes in offline mode.

    Returns:
        Tuple of (Protocol, ProtocolContext) ready for ``protocol.run(context)``.

    Raises:
        GantryLoaderError: If gantry YAML is invalid or missing.
        DeckLoaderError: If deck YAML is invalid or missing.
        BoardLoaderError: If embedded instrument config is invalid or missing.
        ProtocolLoaderError: If protocol YAML is invalid or missing.
        SetupValidationError: If any positions violate gantry bounds.
    """
    board_source_path, resolved_protocol_path, embedded_board = (
        _resolve_board_and_protocol_paths(
            gantry_path, protocol_path, legacy_protocol_path,
        )
    )
    gantry_config: GantryConfig = load_gantry_from_yaml_safe(gantry_path)
    deck: Deck = load_deck_from_yaml_safe(
        deck_path,
        total_z_height=gantry_config.total_z_height,
    )

    if gantry is None:
        gantry = Gantry(offline=True)
    if embedded_board:
        board: Board = load_board_from_gantry_yaml_safe(
            board_source_path, gantry, mock_mode=mock_mode,
        )
    else:
        board = load_board_from_yaml_safe(
            board_source_path, gantry, mock_mode=mock_mode,
        )

    protocol: Protocol = load_protocol_from_yaml_safe(resolved_protocol_path)

    violations = validate_deck_positions(gantry_config, deck)
    violations.extend(validate_gantry_positions(gantry_config, deck, board))
    if violations:
        raise SetupValidationError(violations)

    semantic_violations = validate_protocol_semantics(protocol, board, deck)
    if semantic_violations:
        raise ProtocolSemanticValidationError(semantic_violations)

    context = ProtocolContext(board=board, deck=deck, positions=protocol.positions, gantry=gantry_config)
    return protocol, context


def run_protocol(
    gantry_path: str | Path,
    deck_path: str | Path,
    protocol_path: str | Path,
    legacy_protocol_path: str | Path | None = None,
    gantry: Gantry | None = None,
    mock_mode: bool = False,
) -> List[Any]:
    """Load configs, validate, and execute the protocol in one call.

    Connects instruments before running and disconnects them afterwards,
    even if the protocol raises an exception.

    Returns:
        List of step results from protocol execution.
    """
    protocol, context = setup_protocol(
        gantry_path, deck_path, protocol_path, legacy_protocol_path,
        gantry=gantry, mock_mode=mock_mode,
    )
    context.board.connect_instruments()
    try:
        return protocol.run(context)
    finally:
        context.board.disconnect_instruments()
