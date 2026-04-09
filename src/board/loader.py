"""Load board YAML into a Board containing instruments."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, TYPE_CHECKING

import yaml
from pydantic import ValidationError

from instruments.base_instrument import BaseInstrument
from instruments.registry import get_instrument_class, validate_instrument

from .board import Board
from .errors import BoardLoaderError
from .yaml_schema import BoardYamlSchema

if TYPE_CHECKING:
    from gantry import Gantry


def _format_loader_exception(path: Path, error: Exception) -> str:
    """Return a concise, actionable error message."""
    detail = str(error)

    if isinstance(error, ValidationError):
        first = error.errors()[0] if error.errors() else {}
        detail = first.get("msg", detail)
        location = ".".join(str(part) for part in first.get("loc", []))
        error_type = first.get("type", "")

        if "missing" in error_type or "Field required" in detail:
            guidance = "Add the missing required YAML field shown in the error location."
        elif "extra_forbidden" in error_type or "Extra inputs are not permitted" in detail:
            guidance = "Remove unknown YAML fields; only 'instruments' is allowed at root."
        else:
            guidance = "Review the YAML values against the board schema."

        prefix = f" at `{location}`" if location else ""
        return f"Board YAML error{prefix}: {detail}\nHow to fix: {guidance}"

    if isinstance(error, yaml.YAMLError):
        return (
            f"Board YAML parse error in `{path}`.\n"
            "How to fix: Check YAML indentation, colons, and structure."
        )

    if isinstance(error, ValueError):
        return (
            f"Instrument validation error in `{path}`: {detail}\n"
            f"How to fix: Check type and vendor against the instrument registry."
        )

    return (
        f"Board loader error in `{path}`: {detail}\n"
        "How to fix: Verify the file path and board YAML contents."
    )


def load_board_from_yaml(
    path: str | Path, gantry: Gantry, mock_mode: bool = False,
) -> Board:
    """Load a board YAML file and return a Board with instruments.

    Args:
        path: Path to the board YAML file.
        gantry: The Gantry instance to attach to the Board.
        mock_mode: If True, all instruments are created with offline=True.

    Returns:
        Board with all instruments instantiated from the YAML config.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
        ValidationError: If the YAML does not match the schema.
        ValueError: If an instrument type or vendor is invalid.
    """
    path = Path(path)
    with path.open() as f:
        raw = yaml.safe_load(f)
    if raw is None:
        raw = {}

    schema = BoardYamlSchema.model_validate(raw)

    instruments: Dict[str, BaseInstrument] = {}
    for name, entry in schema.instruments.items():
        kwargs = entry.model_dump()
        type_key = kwargs.pop("type")
        vendor = kwargs.pop("vendor")
        validate_instrument(type_key, vendor)
        if mock_mode:
            kwargs["offline"] = True
        cls = get_instrument_class(type_key)
        kwargs["vendor"] = vendor
        instruments[name] = cls(**kwargs)

    return Board(gantry=gantry, instruments=instruments)


def load_board_from_yaml_safe(
    path: str | Path, gantry: Gantry, mock_mode: bool = False,
) -> Board:
    """Load board YAML with user-friendly exception formatting."""
    resolved = Path(path)
    try:
        return load_board_from_yaml(resolved, gantry, mock_mode=mock_mode)
    except Exception as exc:
        raise BoardLoaderError(_format_loader_exception(resolved, exc)) from exc
