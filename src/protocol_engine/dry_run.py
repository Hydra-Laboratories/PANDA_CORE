"""Dry-run simulation for protocol volume validation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from .errors import OverflowVolumeError, UnderflowVolumeError
from .protocol import Protocol, ProtocolContext, ProtocolStep
from .volume_tracker import VolumeTracker

logger = logging.getLogger(__name__)


@dataclass
class DepletionEvent:
    """Record of a volume error detected during dry-run simulation."""

    step_index: int
    command_name: str
    labware_key: str
    well_id: str | None
    event_type: str  # "underflow" or "overflow"
    shortfall: float
    message: str


@dataclass
class DryRunResult:
    """Result of a dry-run simulation."""

    success: bool
    depletions: list[DepletionEvent] = field(default_factory=list)
    final_volumes: dict[tuple[str, Optional[str]], float] = field(
        default_factory=dict,
    )


def _clone_tracker(tracker: VolumeTracker) -> VolumeTracker:
    """Create a deep copy of a VolumeTracker without modifying the original."""
    clone = VolumeTracker()
    clone._volumes = dict(tracker._volumes)
    clone._capacities = dict(tracker._capacities)
    clone._dead_volumes = dict(tracker._dead_volumes)
    return clone


def _parse_position(position: str) -> tuple[str, Optional[str]]:
    """Split 'plate_1.A1' into ('plate_1', 'A1') or 'vial_1' into ('vial_1', None)."""
    parts = position.split(".", 1)
    if len(parts) == 2:
        return (parts[0], parts[1])
    return (parts[0], None)


def dry_run(protocol: Protocol, context: ProtocolContext) -> DryRunResult:
    """Simulate a protocol to find all volume errors without executing commands.

    Returns a DryRunResult with all detected depletions and final volumes.
    Does not modify the original context or its volume tracker.
    """
    if context.volume_tracker is None:
        return DryRunResult(success=True)

    tracker = _clone_tracker(context.volume_tracker)
    depletions: list[DepletionEvent] = []

    for step in protocol.steps:
        _simulate_step(step, tracker, context, depletions)

    final_volumes = dict(tracker._volumes)
    return DryRunResult(
        success=len(depletions) == 0,
        depletions=depletions,
        final_volumes=final_volumes,
    )


def _simulate_step(step, tracker, context, depletions):
    """Simulate a single step, catching volume errors as DepletionEvents."""
    command = step.command_name
    args = step.args

    if command == "aspirate":
        _simulate_aspirate(step, tracker, depletions, args)
    elif command == "transfer":
        _simulate_transfer(step, tracker, depletions, args)
    elif command == "mix":
        _simulate_mix(step, tracker, depletions, args)
    elif command == "serial_transfer":
        _simulate_serial_transfer(step, tracker, context, depletions, args)
    # All other commands are skipped (move, blowout, pick_up_tip, etc.)


def _simulate_aspirate(step, tracker, depletions, args):
    """Simulate an aspirate command."""
    labware_key, well_id = _parse_position(args["position"])
    volume_ul = args["volume_ul"]
    try:
        tracker.record_aspirate(labware_key, well_id, volume_ul)
    except UnderflowVolumeError as exc:
        depletions.append(DepletionEvent(
            step_index=step.index,
            command_name=step.command_name,
            labware_key=labware_key,
            well_id=well_id,
            event_type="underflow",
            shortfall=exc.requested_ul - (exc.current_volume_ul - exc.dead_volume_ul),
            message=str(exc),
        ))
        # Reset volume to dead volume so simulation can continue
        dead = tracker._dead_volumes.get((labware_key, well_id), 0.0)
        tracker._volumes[(labware_key, well_id)] = dead


def _simulate_dispense(step, tracker, depletions, labware_key, well_id, volume_ul):
    """Simulate a dispense operation."""
    try:
        tracker.record_dispense(labware_key, well_id, volume_ul)
    except OverflowVolumeError as exc:
        depletions.append(DepletionEvent(
            step_index=step.index,
            command_name=step.command_name,
            labware_key=labware_key,
            well_id=well_id,
            event_type="overflow",
            shortfall=exc.current_volume_ul + exc.requested_ul - exc.capacity_ul,
            message=str(exc),
        ))
        # Cap at capacity so simulation continues
        tracker._volumes[(labware_key, well_id)] = tracker._capacities[
            (labware_key, well_id)
        ]


def _simulate_transfer(step, tracker, depletions, args):
    """Simulate a transfer (aspirate from source, dispense to dest)."""
    source_key, source_well = _parse_position(args["source"])
    dest_key, dest_well = _parse_position(args["destination"])
    volume_ul = args["volume_ul"]

    try:
        tracker.record_aspirate(source_key, source_well, volume_ul)
    except UnderflowVolumeError as exc:
        depletions.append(DepletionEvent(
            step_index=step.index,
            command_name=step.command_name,
            labware_key=source_key,
            well_id=source_well,
            event_type="underflow",
            shortfall=exc.requested_ul - (exc.current_volume_ul - exc.dead_volume_ul),
            message=str(exc),
        ))
        dead = tracker._dead_volumes.get((source_key, source_well), 0.0)
        tracker._volumes[(source_key, source_well)] = dead

    _simulate_dispense(step, tracker, depletions, dest_key, dest_well, volume_ul)


def _simulate_mix(step, tracker, depletions, args):
    """Simulate a mix command (just validate aspirate is possible)."""
    labware_key, well_id = _parse_position(args["position"])
    volume_ul = args["volume_ul"]
    try:
        tracker.validate_aspirate(labware_key, well_id, volume_ul)
    except UnderflowVolumeError as exc:
        depletions.append(DepletionEvent(
            step_index=step.index,
            command_name=step.command_name,
            labware_key=labware_key,
            well_id=well_id,
            event_type="underflow",
            shortfall=exc.requested_ul - (exc.current_volume_ul - exc.dead_volume_ul),
            message=str(exc),
        ))


def _simulate_serial_transfer(step, tracker, context, depletions, args):
    """Simulate a serial transfer across wells."""
    from deck.labware.well_plate import WellPlate

    source_key, source_well = _parse_position(args["source"])
    plate_key = args["plate"]
    axis = args["axis"]

    try:
        plate_obj = context.deck[plate_key]
    except (KeyError, TypeError):
        logger.warning(
            "Dry run: cannot resolve plate '%s' for serial_transfer at step %d",
            plate_key, step.index,
        )
        return

    if not isinstance(plate_obj, WellPlate):
        return

    well_ids = _wells_for_axis(plate_obj, axis)
    if not well_ids:
        return

    volumes = args.get("volumes")
    volume_range = args.get("volume_range")

    if volumes is None and volume_range is not None:
        volumes = _linspace(volume_range[0], volume_range[1], len(well_ids))

    if volumes is None or len(volumes) != len(well_ids):
        return

    for well_id, vol in zip(well_ids, volumes):
        # Simulate aspirate from source
        try:
            tracker.record_aspirate(source_key, source_well, vol)
        except UnderflowVolumeError as exc:
            depletions.append(DepletionEvent(
                step_index=step.index,
                command_name=step.command_name,
                labware_key=source_key,
                well_id=source_well,
                event_type="underflow",
                shortfall=exc.requested_ul - (exc.current_volume_ul - exc.dead_volume_ul),
                message=str(exc),
            ))
            dead = tracker._dead_volumes.get((source_key, source_well), 0.0)
            tracker._volumes[(source_key, source_well)] = dead

        # Simulate dispense to well
        _simulate_dispense(
            step, tracker, depletions, plate_key, well_id, vol,
        )


def inject_pauses(
    protocol: Protocol, depletions: list[DepletionEvent],
) -> Protocol:
    """Insert pause steps before each depletion point in the protocol.

    Returns a new Protocol with pause steps inserted and all steps re-indexed.
    """
    from .commands.pause import pause as pause_handler

    steps = list(protocol.steps)

    # Sort by step_index descending to insert from back (avoids index shifts)
    sorted_depletions = sorted(depletions, key=lambda d: d.step_index, reverse=True)

    for depletion in sorted_depletions:
        pause_step = ProtocolStep(
            index=0,  # Will be re-indexed
            command_name="pause",
            handler=pause_handler,
            args={
                "message": f"Refill needed: {depletion.message}",
                "reason": "refill",
                "labware_key": depletion.labware_key,
            },
        )
        steps.insert(depletion.step_index, pause_step)

    # Re-index all steps
    for i, step in enumerate(steps):
        step.index = i

    return Protocol(steps=steps, source_path=protocol.source_path)


def _wells_for_axis(plate, axis: str) -> list:
    """Return well IDs along an axis in natural order."""
    if axis.isalpha():
        wells = [w for w in plate.wells if w[0] == axis.upper()]
    else:
        wells = [w for w in plate.wells if w[1:] == axis]
    return sorted(wells, key=lambda w: (w[0], int(w[1:])))


def _linspace(start: float, end: float, n: int) -> list:
    """Return n evenly spaced values from start to end inclusive."""
    if n == 1:
        return [start]
    step = (end - start) / (n - 1)
    return [start + i * step for i in range(n)]
