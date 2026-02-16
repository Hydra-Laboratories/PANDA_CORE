"""Strict Pydantic schemas for protocol YAML."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, model_validator

from .registry import CommandRegistry


class ProtocolStepSchema(BaseModel):
    """One step in a protocol: a single command name with its arguments.

    YAML format::

        - move:
            instrument: pipette
            position: plate_1.A1

    Parsed as ``{"move": {"instrument": "pipette", "position": "plate_1.A1"}}``,
    then normalised to ``{"command": "move", "args": {...}}``.
    """

    model_config = ConfigDict(extra="forbid")

    command: str
    args: Dict[str, Any]

    @model_validator(mode="before")
    @classmethod
    def _parse_command_dict(cls, data: Any) -> Any:
        """Convert ``{command_name: {args}}`` to ``{command: name, args: {…}}``."""
        if isinstance(data, dict) and "command" not in data:
            if len(data) != 1:
                raise ValueError(
                    f"Each protocol step must have exactly one command, "
                    f"got {len(data)} keys: {list(data.keys())}. "
                    "Write each command as a separate list item."
                )
            command_name = next(iter(data))
            args = data[command_name]
            if args is None:
                args = {}
            if not isinstance(args, dict):
                raise ValueError(
                    f"Arguments for command '{command_name}' must be a mapping "
                    f"(key: value), got {type(args).__name__}."
                )
            return {"command": command_name, "args": args}
        return data

    @model_validator(mode="after")
    def _validate_command_registered(self) -> "ProtocolStepSchema":
        """Ensure the command is registered and args match its schema."""
        registry = CommandRegistry.instance()
        try:
            registered = registry.get(self.command)
        except KeyError as exc:
            raise ValueError(str(exc)) from exc
        registered.schema.model_validate(self.args)
        return self


class ProtocolYamlSchema(BaseModel):
    """Root protocol YAML schema: top-level ``protocol`` key with list of steps."""

    model_config = ConfigDict(extra="forbid")

    protocol: List[ProtocolStepSchema]
