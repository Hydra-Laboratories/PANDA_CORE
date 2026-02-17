"""Load board YAML into a Board containing instruments."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, TYPE_CHECKING, Type

import yaml
from pydantic import ValidationError

try:
    from instruments.base_instrument import BaseInstrument
    from instruments.filmetrics.driver import Filmetrics
    from instruments.filmetrics.mock import MockFilmetrics
    from instruments.pipette.driver import Pipette
    from instruments.pipette.mock import MockPipette
    from instruments.uvvis_ccs.driver import UVVisCCS
    from instruments.uvvis_ccs.mock import MockUVVisCCS
except ModuleNotFoundError:  # pragma: no cover - compatibility path for setup scripts
    from src.instruments.base_instrument import BaseInstrument
    from src.instruments.filmetrics.driver import Filmetrics
    from src.instruments.filmetrics.mock import MockFilmetrics
    from src.instruments.pipette.driver import Pipette
    from src.instruments.pipette.mock import MockPipette
    from src.instruments.uvvis_ccs.driver import UVVisCCS
    from src.instruments.uvvis_ccs.mock import MockUVVisCCS

from .board import Board

from .errors import BoardLoaderError
from .yaml_schema import BoardYamlSchema

if TYPE_CHECKING:
    try:
        from gantry import Gantry
    except ModuleNotFoundError:  # pragma: no cover - compatibility path for setup scripts
        from src.gantry import Gantry

INSTRUMENT_REGISTRY: Dict[str, Type[BaseInstrument]] = {
    "uvvis_ccs": UVVisCCS,
    "mock_uvvis_ccs": MockUVVisCCS,
    "pipette": Pipette,
    "mock_pipette": MockPipette,
    "filmetrics": Filmetrics,
    "mock_filmetrics": MockFilmetrics,
}


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

    if isinstance(error, KeyError):
        return (
            f"Unknown instrument type in `{path}`: {detail}\n"
            f"How to fix: Use one of {sorted(INSTRUMENT_REGISTRY.keys())}."
        )

    return (
        f"Board loader error in `{path}`: {detail}\n"
        "How to fix: Verify the file path and board YAML contents."
    )


def load_board_from_yaml(path: str | Path, gantry: Gantry) -> Board:
    """Load a board YAML file and return a Board with instruments.

    Args:
        path: Path to the board YAML file.
        gantry: The Gantry instance to attach to the Board.

    Returns:
        Board with all instruments instantiated from the YAML config.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
        ValidationError: If the YAML does not match the schema.
        KeyError: If an instrument type is not in the registry.
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
        if type_key not in INSTRUMENT_REGISTRY:
            raise KeyError(type_key)
        cls = INSTRUMENT_REGISTRY[type_key]
        instruments[name] = cls(**kwargs)

    return Board(gantry=gantry, instruments=instruments)


def load_board_from_yaml_safe(path: str | Path, gantry: Gantry) -> Board:
    """Load board YAML with user-friendly exception formatting.

    Raises:
        BoardLoaderError: Concise, actionable message intended for CLI output.
    """
    resolved = Path(path)
    try:
        return load_board_from_yaml(resolved, gantry)
    except Exception as exc:
        raise BoardLoaderError(_format_loader_exception(resolved, exc)) from exc
