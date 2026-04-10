"""Protocol setup: load all configs, validate, and return a ready-to-run protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Tuple

from board.board import Board
from board.loader import load_board_from_yaml_safe
from deck.deck import Deck
from deck.loader import load_deck_from_yaml_safe
from gantry.gantry import Gantry
from gantry.gantry_config import GantryConfig
from gantry.loader import load_gantry_from_yaml_safe
from protocol_engine.loader import load_protocol_from_yaml_safe
from protocol_engine.protocol import Protocol, ProtocolContext
from validation.bounds import validate_deck_positions, validate_gantry_positions
from validation.collision import (
    CollisionSettings,
    CollisionValidationMode,
    validate_collision_safety,
)
from validation.errors import CollisionValidationError, SetupValidationError


def setup_protocol(
    gantry_path: str | Path,
    deck_path: str | Path,
    board_path: str | Path,
    protocol_path: str | Path,
    gantry=None,
    mock_mode: bool = False,
    collision_validation: bool = False,
    collision_mode: str = "strict",
    collision_clearance_mm: float = 2.0,
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
        gantry: Optional Gantry instance. If None, an offline Gantry is used
            for validation.
        mock_mode: If True, instantiate real driver classes in offline mode.
        collision_validation: If True, run opt-in static collision validation.
        collision_mode: 'strict' blocks setup on missing geometry; 'report_only'
            records missing geometry as warnings.
        collision_clearance_mm: Required Z clearance for static envelope checks.

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
        gantry = Gantry(offline=True)
    board: Board = load_board_from_yaml_safe(
        board_path, gantry, mock_mode=mock_mode,
    )

    protocol: Protocol = load_protocol_from_yaml_safe(protocol_path)

    violations = validate_deck_positions(gantry_config, deck)
    violations.extend(validate_gantry_positions(gantry_config, deck, board))
    if violations:
        raise SetupValidationError(violations)

    context = ProtocolContext(board=board, deck=deck, positions=protocol.positions, gantry=gantry_config)
    if collision_validation:
        settings = CollisionSettings(
            mode=CollisionValidationMode(collision_mode),
            clearance_mm=collision_clearance_mm,
        )
        collision_report = validate_collision_safety(
            protocol,
            context,
            gantry_config,
            settings=settings,
        )
        context.collision_report = collision_report
        if collision_report.errors:
            raise CollisionValidationError(collision_report.issues)
    return protocol, context


def run_protocol(
    gantry_path: str | Path,
    deck_path: str | Path,
    board_path: str | Path,
    protocol_path: str | Path,
    gantry=None,
    mock_mode: bool = False,
    collision_validation: bool = False,
    collision_mode: str = "strict",
    collision_clearance_mm: float = 2.0,
) -> List[Any]:
    """Load configs, validate, and execute the protocol in one call.

    Connects instruments before running and disconnects them afterwards,
    even if the protocol raises an exception.

    Returns:
        List of step results from protocol execution.
    """
    protocol, context = setup_protocol(
        gantry_path, deck_path, board_path, protocol_path,
        gantry=gantry, mock_mode=mock_mode,
        collision_validation=collision_validation,
        collision_mode=collision_mode,
        collision_clearance_mm=collision_clearance_mm,
    )
    context.board.connect_instruments()
    try:
        return protocol.run(context)
    finally:
        context.board.disconnect_instruments()
