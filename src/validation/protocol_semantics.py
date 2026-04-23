"""Semantic validation for protocol runtime movement assumptions."""

from __future__ import annotations

import math
from typing import Any

from deck.labware.well_plate import WellPlate
from protocol_engine.protocol import Protocol
from board.board import Board
from deck.deck import Deck

from .errors import ProtocolSemanticViolation


def _method_kwargs(args: dict[str, Any]) -> dict[str, Any]:
    value = args.get("method_kwargs")
    return value if isinstance(value, dict) else {}


def _validate_scan_travel_heights(
    *,
    step_index: int,
    args: dict[str, Any],
    board: Board,
    deck: Deck,
) -> list[ProtocolSemanticViolation]:
    violations: list[ProtocolSemanticViolation] = []
    instrument = args.get("instrument")
    plate = args.get("plate")

    if instrument not in board.instruments:
        return violations
    if plate not in deck:
        return violations

    plate_obj = deck[plate]
    if not isinstance(plate_obj, WellPlate):
        return violations

    instr = board.instruments[instrument]
    travel_fields = (
        ("entry_travel_z", args.get("entry_travel_z")),
        ("safe_approach_height", args.get("safe_approach_height")),
    )
    for field_name, travel_z in travel_fields:
        if travel_z is None:
            continue
        if not math.isfinite(float(travel_z)):
            violations.append(ProtocolSemanticViolation(
                step_index,
                "scan",
                f"{field_name} must be finite, got {travel_z!r}.",
            ))
            continue
        for well_id, well in plate_obj.wells.items():
            action_z = well.z - instr.measurement_height
            if travel_z > action_z:
                violations.append(ProtocolSemanticViolation(
                    step_index,
                    "scan",
                    f"{field_name} ({travel_z}) is below action_z ({action_z}) "
                    f"for {plate}.{well_id} under the current positive-down "
                    "convention.",
                ))
                break

    return violations


def _validate_asmi_indentation(
    *,
    step_index: int,
    args: dict[str, Any],
) -> list[ProtocolSemanticViolation]:
    violations: list[ProtocolSemanticViolation] = []
    if args.get("instrument") != "asmi" or args.get("method") != "indentation":
        return violations

    kwargs = _method_kwargs(args)
    measurement_height = kwargs.get("measurement_height")
    z_limit = kwargs.get("z_limit")
    step_size = kwargs.get("step_size")

    if step_size is not None and step_size <= 0:
        violations.append(ProtocolSemanticViolation(
            step_index,
            "scan",
            f"ASMI step_size must be positive, got {step_size}.",
        ))

    if measurement_height is None or z_limit is None:
        return violations

    if z_limit <= measurement_height:
        violations.append(ProtocolSemanticViolation(
            step_index,
            "scan",
            "ASMI z_limit must be greater than measurement_height under the "
            f"current positive-down convention; got measurement_height="
            f"{measurement_height}, z_limit={z_limit}.",
        ))

    return violations


def validate_protocol_semantics(
    protocol: Protocol,
    board: Board,
    deck: Deck,
) -> list[ProtocolSemanticViolation]:
    """Return protocol semantic violations that static bounds checks miss."""
    violations: list[ProtocolSemanticViolation] = []
    for step in protocol.steps:
        if step.command_name != "scan":
            continue
        violations.extend(_validate_scan_travel_heights(
            step_index=step.index,
            args=step.args,
            board=board,
            deck=deck,
        ))
        violations.extend(_validate_asmi_indentation(
            step_index=step.index,
            args=step.args,
        ))
    return violations
