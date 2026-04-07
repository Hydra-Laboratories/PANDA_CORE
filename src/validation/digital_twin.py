"""Digital-twin pre-validation for protocol reachability and overlap analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Literal, Optional

from board.board import Board
from deck.deck import Deck
from deck.labware.vial import Vial
from deck.labware.well_plate import WellPlate
from gantry.gantry_config import GantryConfig
from protocol_engine.protocol import Protocol, ProtocolContext


LabwareKind = Literal["vial", "well_plate", "unknown"]


@dataclass(frozen=True)
class AABB:
    """Axis-aligned 3D bounds."""

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float

    def contains(self, x: float, y: float, z: float) -> bool:
        return (
            self.x_min <= x <= self.x_max
            and self.y_min <= y <= self.y_max
            and self.z_min <= z <= self.z_max
        )

    def intersect(self, other: "AABB") -> Optional["AABB"]:
        x_min = max(self.x_min, other.x_min)
        x_max = min(self.x_max, other.x_max)
        y_min = max(self.y_min, other.y_min)
        y_max = min(self.y_max, other.y_max)
        z_min = max(self.z_min, other.z_min)
        z_max = min(self.z_max, other.z_max)
        if x_min > x_max or y_min > y_max or z_min > z_max:
            return None
        return AABB(x_min, x_max, y_min, y_max, z_min, z_max)


@dataclass(frozen=True)
class TwinViolation:
    step_index: int
    command: str
    instrument: str
    message: str
    suggestion: str
    target: Optional[str] = None


@dataclass
class TwinValidationResult:
    passed: bool
    violations: list[TwinViolation]
    step_trace: list[dict[str, Any]]
    instrument_workspaces: dict[str, AABB]
    overlap: dict[str, Any]
    image_path: Optional[str]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": [asdict(v) for v in self.violations],
            "step_trace": self.step_trace,
            "instrument_workspaces": {
                name: asdict(bounds)
                for name, bounds in self.instrument_workspaces.items()
            },
            "overlap": self.overlap,
            "image_path": self.image_path,
        }


def _workspace_for_instrument(gantry: GantryConfig, instrument: Any) -> AABB:
    vol = gantry.working_volume
    return AABB(
        x_min=vol.x_min + instrument.offset_x,
        x_max=vol.x_max + instrument.offset_x,
        y_min=vol.y_min + instrument.offset_y,
        y_max=vol.y_max + instrument.offset_y,
        z_min=vol.z_min + instrument.depth,
        z_max=vol.z_max + instrument.depth,
    )


def _labware_kind_for_target(deck: Deck, target: str) -> LabwareKind:
    key = target.split(".", 1)[0]
    labware = deck[key]
    if isinstance(labware, Vial):
        return "vial"
    if isinstance(labware, WellPlate):
        return "well_plate"
    return "unknown"


def _resolve_target_xyz(context: ProtocolContext, step) -> tuple[Optional[tuple[float, float, float]], Optional[str], LabwareKind]:
    if step.command_name == "move":
        pos = step.args.get("position")
        if isinstance(pos, (list, tuple)):
            return (float(pos[0]), float(pos[1]), float(pos[2])), None, "unknown"
        if isinstance(pos, str) and pos in context.positions:
            named = context.positions[pos]
            return (float(named[0]), float(named[1]), float(named[2])), pos, "unknown"
        if isinstance(pos, str):
            xyz = context.deck.resolve(pos)
            return (float(xyz.x), float(xyz.y), float(xyz.z)), pos, _labware_kind_for_target(context.deck, pos)
    if step.command_name == "scan":
        plate = step.args["plate"]
        plate_obj = context.deck[plate]
        assert isinstance(plate_obj, WellPlate)
        a1 = plate_obj.get_well_center("A1")
        return (float(a1.x), float(a1.y), float(a1.z)), plate, "well_plate"
    return None, None, "unknown"


def _command_instrument(step) -> Optional[str]:
    if step.command_name in {"move", "scan"}:
        return step.args.get("instrument")
    return None


def _categorize_instruments(protocol: Protocol, context: ProtocolContext) -> tuple[set[str], set[str]]:
    vial_instruments: set[str] = set()
    plate_instruments: set[str] = set()
    for step in protocol.steps:
        instrument = _command_instrument(step)
        if not instrument:
            continue
        _, _, kind = _resolve_target_xyz(context, step)
        if kind == "vial":
            vial_instruments.add(instrument)
        elif kind == "well_plate":
            plate_instruments.add(instrument)
    return vial_instruments, plate_instruments


def _sample_union_flags(x: float, y: float, z: float, boxes: Iterable[AABB]) -> bool:
    return any(box.contains(x, y, z) for box in boxes)


def _overlap_summary(
    gantry: GantryConfig,
    workspace_by_instrument: dict[str, AABB],
    vial_instruments: set[str],
    plate_instruments: set[str],
    voxels_per_axis: int = 24,
) -> dict[str, Any]:
    vial_boxes = [workspace_by_instrument[k] for k in sorted(vial_instruments) if k in workspace_by_instrument]
    plate_boxes = [workspace_by_instrument[k] for k in sorted(plate_instruments) if k in workspace_by_instrument]

    vol = gantry.working_volume
    dx = (vol.x_max - vol.x_min) / voxels_per_axis
    dy = (vol.y_max - vol.y_min) / voxels_per_axis
    dz = (vol.z_max - vol.z_min) / voxels_per_axis
    cell_volume = dx * dy * dz

    vial_only = 0
    plate_only = 0
    shared = 0
    neither = 0

    for ix in range(voxels_per_axis):
        x = vol.x_min + (ix + 0.5) * dx
        for iy in range(voxels_per_axis):
            y = vol.y_min + (iy + 0.5) * dy
            for iz in range(voxels_per_axis):
                z = vol.z_min + (iz + 0.5) * dz
                vial_reach = _sample_union_flags(x, y, z, vial_boxes)
                plate_reach = _sample_union_flags(x, y, z, plate_boxes)
                if vial_reach and plate_reach:
                    shared += 1
                elif vial_reach:
                    vial_only += 1
                elif plate_reach:
                    plate_only += 1
                else:
                    neither += 1

    return {
        "vial_instruments": sorted(vial_instruments),
        "well_plate_instruments": sorted(plate_instruments),
        "volume_estimates_mm3": {
            "vial_only": vial_only * cell_volume,
            "well_plate_only": plate_only * cell_volume,
            "shared": shared * cell_volume,
            "neither": neither * cell_volume,
        },
    }


def _write_overlap_svg(
    path: Path,
    gantry: GantryConfig,
    workspace_by_instrument: dict[str, AABB],
    vial_instruments: set[str],
    plate_instruments: set[str],
    grid_px: int = 320,
) -> None:
    """Write a top-down XY occupancy SVG.

    Colors:
      - red: vial-only reachable
      - blue: well-plate-only reachable
      - purple: shared reachable
      - light gray: neither
    """
    vol = gantry.working_volume
    vial_boxes = [workspace_by_instrument[k] for k in sorted(vial_instruments) if k in workspace_by_instrument]
    plate_boxes = [workspace_by_instrument[k] for k in sorted(plate_instruments) if k in workspace_by_instrument]

    dx = (vol.x_max - vol.x_min) / grid_px
    dy = (vol.y_max - vol.y_min) / grid_px

    rects: list[str] = []
    for ix in range(grid_px):
        x = vol.x_min + (ix + 0.5) * dx
        for iy in range(grid_px):
            y = vol.y_min + (iy + 0.5) * dy
            vial_xy = any(box.x_min <= x <= box.x_max and box.y_min <= y <= box.y_max for box in vial_boxes)
            plate_xy = any(box.x_min <= x <= box.x_max and box.y_min <= y <= box.y_max for box in plate_boxes)
            if vial_xy and plate_xy:
                color = "#8e44ad"
            elif vial_xy:
                color = "#d35454"
            elif plate_xy:
                color = "#3498db"
            else:
                color = "#ecf0f1"
            svg_x = ix
            svg_y = grid_px - iy - 1
            rects.append(f'<rect x="{svg_x}" y="{svg_y}" width="1" height="1" fill="{color}" />')

    legend = """\
<rect x="12" y="12" width="10" height="10" fill="#d35454"/><text x="26" y="21" font-size="10">Vial-only</text>
<rect x="12" y="28" width="10" height="10" fill="#3498db"/><text x="26" y="37" font-size="10">Well-plate-only</text>
<rect x="12" y="44" width="10" height="10" fill="#8e44ad"/><text x="26" y="53" font-size="10">Shared</text>
<rect x="12" y="60" width="10" height="10" fill="#ecf0f1" stroke="#95a5a6"/><text x="26" y="69" font-size="10">Neither</text>
"""

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{grid_px}" height="{grid_px}" '
        f'viewBox="0 0 {grid_px} {grid_px}">\n'
        + "\n".join(rects)
        + "\n"
        + legend
        + "\n</svg>\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")


def run_digital_twin_validation(
    gantry: GantryConfig,
    deck: Deck,
    board: Board,
    protocol: Protocol,
    image_path: str | Path | None = None,
    json_path: str | Path | None = None,
) -> TwinValidationResult:
    """Run mock-backed protocol pre-validation and overlap analysis."""
    context = ProtocolContext(
        board=board,
        deck=deck,
        positions=protocol.positions,
        gantry=gantry,
    )
    workspace_by_instrument = {
        name: _workspace_for_instrument(gantry, instr)
        for name, instr in board.instruments.items()
    }

    violations: list[TwinViolation] = []
    step_trace: list[dict[str, Any]] = []

    for step in protocol.steps:
        if step.command_name not in {"move", "scan"}:
            violations.append(
                TwinViolation(
                    step_index=step.index,
                    command=step.command_name,
                    instrument="N/A",
                    target=None,
                    message=(
                        f"Command '{step.command_name}' is not simulated in digital twin v1."
                    ),
                    suggestion="TODO: add simulator coverage for this command.",
                )
            )
            step_trace.append({"step_index": step.index, "command": step.command_name, "status": "unsupported"})
            continue

        instrument = _command_instrument(step)
        if instrument not in workspace_by_instrument:
            violations.append(
                TwinViolation(
                    step_index=step.index,
                    command=step.command_name,
                    instrument=str(instrument),
                    message=f"Instrument '{instrument}' is not present on the board.",
                    suggestion="Use a board instrument key that exists in board YAML.",
                )
            )
            step_trace.append({"step_index": step.index, "command": step.command_name, "status": "failed"})
            continue

        target_xyz, target_label, _ = _resolve_target_xyz(context, step)
        if target_xyz is not None:
            x, y, z = target_xyz
            if step.command_name == "scan":
                instr = board.instruments[instrument]
                z = z + instr.measurement_height
            if not workspace_by_instrument[instrument].contains(x, y, z):
                violations.append(
                    TwinViolation(
                        step_index=step.index,
                        command=step.command_name,
                        instrument=instrument,
                        target=target_label,
                        message=(
                            f"Target ({x:.3f}, {y:.3f}, {z:.3f}) is outside reachable workspace "
                            f"for instrument '{instrument}'."
                        ),
                        suggestion="Adjust deck position, instrument offset, or gantry bounds.",
                    )
                )
                step_trace.append({"step_index": step.index, "command": step.command_name, "status": "failed"})
                continue

        try:
            step.execute(context)
            step_trace.append({"step_index": step.index, "command": step.command_name, "status": "passed"})
        except Exception as exc:
            violations.append(
                TwinViolation(
                    step_index=step.index,
                    command=step.command_name,
                    instrument=instrument,
                    target=target_label,
                    message=f"Mock execution failed: {exc}",
                    suggestion="Check command args and instrument mock behavior.",
                )
            )
            step_trace.append({"step_index": step.index, "command": step.command_name, "status": "failed"})

    vial_instruments, plate_instruments = _categorize_instruments(protocol, context)
    overlap = _overlap_summary(
        gantry=gantry,
        workspace_by_instrument=workspace_by_instrument,
        vial_instruments=vial_instruments,
        plate_instruments=plate_instruments,
    )

    image_path_str: Optional[str] = None
    if image_path is not None:
        image_out = Path(image_path)
        _write_overlap_svg(
            path=image_out,
            gantry=gantry,
            workspace_by_instrument=workspace_by_instrument,
            vial_instruments=vial_instruments,
            plate_instruments=plate_instruments,
        )
        image_path_str = str(image_out)

    result = TwinValidationResult(
        passed=not violations,
        violations=violations,
        step_trace=step_trace,
        instrument_workspaces=workspace_by_instrument,
        overlap=overlap,
        image_path=image_path_str,
    )

    if json_path is not None:
        out = Path(json_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result.to_json_dict(), indent=2), encoding="utf-8")

    return result
