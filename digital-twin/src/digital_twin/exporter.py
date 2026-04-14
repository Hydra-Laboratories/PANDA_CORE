"""Export CubOS protocol traces into a browser-friendly digital twin bundle."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import yaml

from board import Board, BoardYamlSchema, load_board_from_yaml_safe
from deck import (
    Deck,
    NestedVialYamlEntry,
    NestedWellPlateYamlEntry,
    PlateOrientation,
    TipRack,
    TipRackYamlEntry,
    Vial,
    VialHolder,
    VialHolderYamlEntry,
    VialYamlEntry,
    WellPlate,
    WellPlateHolder,
    WellPlateHolderYamlEntry,
    WellPlateYamlEntry,
    load_deck_from_yaml_safe,
    load_deck_render_schema,
    resolve_definition_asset_path,
    resolve_plate_orientation,
)
from gantry import (
    DEFAULT_FEED_RATE,
    DEFAULT_USER_MAX_Z_HEIGHT,
    DEFAULT_USER_SAFE_Z_HEIGHT,
    GantryConfig,
    MotionPose,
    MotionSegmentPlan,
    coerce_motion_pose,
    load_gantry_from_yaml_safe,
    plan_safe_move_segments,
    resolve_gantry_target,
    resolve_instrument_tip_pose,
)
from protocol_engine import Protocol, ProtocolContext, ProtocolStep, load_protocol_from_yaml_safe
from validation import SetupValidationError, validate_deck_positions, validate_gantry_positions


_SUPPORTED_PHASE_ONE_COMMANDS = {"move", "scan"}
def _load_yaml(path: str | Path) -> dict[str, Any]:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Expected YAML mapping at {path}, got {type(raw).__name__}.")
    return raw


def _coord_dict(coord: Any) -> dict[str, float]:
    pose = coerce_motion_pose(coord)
    return pose.to_dict()


def _format_target_label(target: Any) -> str:
    if isinstance(target, str):
        return target
    if isinstance(target, (list, tuple)):
        return "[" + ", ".join(f"{float(value):.3f}" for value in target) + "]"
    return str(target)


def _event_base_duration(event: dict[str, Any]) -> float:
    if event["type"] == "motion":
        return max(float(event["real_duration_s"]), 0.05)
    return max(float(event.get("duration_s", 0.0)), 0.0)


class _TracingGantry:
    """Minimal gantry used during export playback."""

    def __init__(self, initial_pose: MotionPose | None = None) -> None:
        self._pose = initial_pose or MotionPose(
            x=0.0,
            y=0.0,
            z=DEFAULT_USER_MAX_Z_HEIGHT,
        )

    def move_to(self, x: float, y: float, z: float) -> None:
        self._pose = MotionPose(x=float(x), y=float(y), z=float(z))

    def get_coordinates(self) -> dict[str, float]:
        return self._pose.to_dict()

    def home(self) -> None:
        self._pose = MotionPose(x=0.0, y=0.0, z=DEFAULT_USER_MAX_Z_HEIGHT)

    def zero_coordinates(self) -> None:
        self._pose = MotionPose(x=0.0, y=0.0, z=DEFAULT_USER_MAX_Z_HEIGHT)

    def set_serial_timeout(self, _seconds: float) -> None:
        return None


class TracingBoard(Board):
    """Board that records atomic motion segments instead of teleporting."""

    def __init__(
        self,
        *,
        gantry: _TracingGantry,
        instruments: dict[str, Any],
        timeline: list[dict[str, Any]],
        deck: Deck | None = None,
        safe_z_height: float = DEFAULT_USER_SAFE_Z_HEIGHT,
        max_z_height: float = DEFAULT_USER_MAX_Z_HEIGHT,
        feed_rate: float = DEFAULT_FEED_RATE,
    ) -> None:
        super().__init__(gantry=gantry, instruments=instruments)
        self.timeline = timeline
        self.safe_z_height = safe_z_height
        self.max_z_height = max_z_height
        self.feed_rate = feed_rate
        self.deck = deck
        self._active_step: ProtocolStep | None = None
        self._last_target_label: str | None = None
        self._coordinate_lookup = self._build_coordinate_lookup(deck)
        self._xy_lookup = self._build_xy_lookup(deck)

    def set_active_step(self, step: ProtocolStep | None) -> None:
        self._active_step = step

    def append_action_event(
        self,
        *,
        kind: str,
        duration_s: float = 0.0,
        instrument_id: str | None = None,
        target_label: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if self._active_step is None:
            raise RuntimeError("TracingBoard step context must be set before recording events.")
        self.timeline.append(
            {
                "type": "action",
                "step_index": self._active_step.index,
                "command": self._active_step.command_name,
                "kind": kind,
                "instrument_id": instrument_id,
                "target_label": target_label,
                "duration_s": duration_s,
                "payload": payload or {},
            }
        )

    def append_dwell_event(self, *, duration_s: float, label: str) -> None:
        if self._active_step is None:
            raise RuntimeError("TracingBoard step context must be set before recording events.")
        self.timeline.append(
            {
                "type": "dwell",
                "step_index": self._active_step.index,
                "command": self._active_step.command_name,
                "duration_s": duration_s,
                "label": label,
            }
        )

    @property
    def last_target_label(self) -> str | None:
        return self._last_target_label

    def _build_coordinate_lookup(self, deck: Deck | None) -> dict[tuple[float, float, float], str]:
        if deck is None:
            return {}

        lookup: dict[tuple[float, float, float], str] = {}
        for deck_key, labware in deck.labware.items():
            for point_id, coord in labware.iter_positions().items():
                label = f"{deck_key}.{point_id}"
                lookup[self._coord_key(coord)] = label
            initial_key = self._coord_key(labware.get_initial_position())
            lookup.setdefault(initial_key, deck_key)
        return lookup

    def _build_xy_lookup(self, deck: Deck | None) -> dict[tuple[float, float], str]:
        if deck is None:
            return {}

        lookup: dict[tuple[float, float], str] = {}
        for deck_key, labware in deck.labware.items():
            for point_id, coord in labware.iter_positions().items():
                lookup[(round(float(coord.x), 6), round(float(coord.y), 6))] = f"{deck_key}.{point_id}"
            initial_pose = labware.get_initial_position()
            lookup.setdefault(
                (round(float(initial_pose.x), 6), round(float(initial_pose.y), 6)),
                deck_key,
            )
        return lookup

    @staticmethod
    def _coord_key(coord: Any) -> tuple[float, float, float]:
        pose = coerce_motion_pose(coord)
        return (round(pose.x, 6), round(pose.y, 6), round(pose.z, 6))

    def _target_label_for_position(self, position: Any) -> str:
        if self._active_step is not None and "position" in self._active_step.args:
            raw_position = self._active_step.args["position"]
            if isinstance(raw_position, str):
                return raw_position

        lookup_key = self._coord_key(position)
        if lookup_key in self._coordinate_lookup:
            return self._coordinate_lookup[lookup_key]

        pose = coerce_motion_pose(position)
        xy_key = (round(pose.x, 6), round(pose.y, 6))
        if xy_key in self._xy_lookup:
            return self._xy_lookup[xy_key]

        return _format_target_label(position)

    def move(
        self,
        instrument: str | Any,
        position: Any,
    ) -> None:
        instr = self._resolve_instrument(instrument)
        instrument_id = instrument if isinstance(instrument, str) else instr.name
        x, y, z = self._resolve_position(position)
        gantry_target = resolve_gantry_target(x, y, z, instr)
        current_pose = coerce_motion_pose(self.gantry.get_coordinates())
        motion_segments = plan_safe_move_segments(
            current_pose=current_pose,
            target_pose=gantry_target,
            safe_z_height=self.safe_z_height,
            max_z_height=self.max_z_height,
            feed_rate=self.feed_rate,
        )
        if self._active_step is None:
            raise RuntimeError("TracingBoard step context must be set before moves.")

        target_label = self._target_label_for_position(position)
        for segment in motion_segments:
            self.timeline.append(
                _motion_event_from_segment(
                    step=self._active_step,
                    instrument_id=instrument_id,
                    instrument=instr,
                    target_label=target_label,
                    segment=segment,
                )
            )
            self.gantry.move_to(
                segment.end_pose.x,
                segment.end_pose.y,
                segment.end_pose.z,
            )
        self._last_target_label = target_label


def _motion_event_from_segment(
    *,
    step: ProtocolStep,
    instrument_id: str,
    instrument: Any,
    target_label: str,
    segment: MotionSegmentPlan,
) -> dict[str, Any]:
    start_tip = resolve_instrument_tip_pose(segment.start_pose, instrument)
    end_tip = resolve_instrument_tip_pose(segment.end_pose, instrument)
    return {
        "type": "motion",
        "step_index": step.index,
        "command": step.command_name,
        "phase": segment.phase,
        "instrument_id": instrument_id,
        "target_label": target_label,
        "start_gantry_pose": segment.start_pose.to_dict(),
        "end_gantry_pose": segment.end_pose.to_dict(),
        "start_tip_pose": start_tip.to_dict(),
        "end_tip_pose": end_tip.to_dict(),
        "feed_rate": segment.feed_rate,
        "distance_mm": segment.distance_mm,
        "real_duration_s": segment.real_duration_s,
        "display_duration_s": max(segment.real_duration_s, 0.05),
    }


def _result_payload(result: Any) -> dict[str, Any]:
    payload = {"result_type": type(result).__name__}
    if hasattr(result, "is_valid"):
        payload["is_valid"] = bool(getattr(result, "is_valid"))
    return payload


def _install_action_wrappers(protocol: Protocol, board: TracingBoard) -> None:
    wrapped_methods: set[tuple[str, str]] = set()
    for step in protocol.steps:
        if step.command_name != "scan":
            continue

        instrument_id = step.args["instrument"]
        method_name = step.args["method"]
        wrapped_key = (instrument_id, method_name)
        if wrapped_key in wrapped_methods:
            continue

        instrument = board.instruments[instrument_id]
        original_method = getattr(instrument, method_name)

        def _wrapped_method(
            *args,
            __orig=original_method,
            __instrument_id=instrument_id,
            __method_name=method_name,
            **kwargs,
        ):
            result = __orig(*args, **kwargs)
            board.append_action_event(
                kind=__method_name,
                instrument_id=__instrument_id,
                target_label=board.last_target_label,
                payload=_result_payload(result),
            )
            return result

        setattr(instrument, method_name, _wrapped_method)
        wrapped_methods.add(wrapped_key)


def _resolve_asset_source(load_name: str | None) -> Path | None:
    if not load_name:
        return None
    try:
        return resolve_definition_asset_path(load_name)
    except ValueError:
        return None


def _select_render_kind(
    *,
    labware: Any,
    load_name: str | None,
) -> tuple[str, Path | None]:
    if load_name == "ursa_tip_rack":
        return ("tip_rack", None)
    asset_source = _resolve_asset_source(load_name)
    if asset_source is not None:
        return ("asset", asset_source)
    if isinstance(labware, WellPlate):
        return ("well_plate", None)
    if isinstance(labware, TipRack):
        return ("tip_rack", None)
    if isinstance(labware, Vial):
        return ("vial", None)
    return ("bounding_box", None)


def _points_payload(labware: Any) -> list[dict[str, Any]]:
    return [
        {"id": point_id, "position": _coord_dict(coord)}
        for point_id, coord in sorted(labware.iter_positions().items())
    ]


def _dimensions_payload(labware: Any) -> dict[str, float | None]:
    geometry = getattr(labware, "geometry", None)
    if geometry is None:
        return {"length_mm": None, "width_mm": None, "height_mm": None}
    return {
        "length_mm": getattr(geometry, "length_mm", None),
        "width_mm": getattr(geometry, "width_mm", None),
        "height_mm": getattr(geometry, "height_mm", None),
    }


def _well_plate_render_meta(
    entry: WellPlateYamlEntry | NestedWellPlateYamlEntry,
    labware: WellPlate,
) -> dict[str, Any]:
    orientation: PlateOrientation = resolve_plate_orientation(entry)
    return {
        "rows": entry.rows,
        "columns": entry.columns,
        "a1": _coord_dict(labware.get_location("A1")),
        "a2": _coord_dict(labware.get_location("A2")),
        "column_vector": {
            "x": orientation.col_delta_x,
            "y": orientation.col_delta_y,
        },
        "row_vector": {
            "x": orientation.row_delta_x,
            "y": orientation.row_delta_y,
        },
        "x_offset_mm": entry.x_offset_mm,
        "y_offset_mm": entry.y_offset_mm,
    }


def _tip_rack_render_meta(
    entry: TipRackYamlEntry,
    labware: TipRack,
) -> dict[str, Any]:
    orientation: PlateOrientation = resolve_plate_orientation(entry)
    return {
        "rows": entry.rows,
        "columns": entry.columns,
        "a1": _coord_dict(labware.get_location("A1")),
        "a2": _coord_dict(labware.get_location("A2")),
        "column_vector": {
            "x": orientation.col_delta_x,
            "y": orientation.col_delta_y,
        },
        "row_vector": {
            "x": orientation.row_delta_x,
            "y": orientation.row_delta_y,
        },
        "x_offset_mm": entry.x_offset_mm,
        "y_offset_mm": entry.y_offset_mm,
        "z_pickup": entry.z_pickup,
        "z_drop": entry.z_drop,
    }


def _scene_item_payload(
    *,
    item_id: str,
    labware: Any,
    entry: Any,
    load_name: str | None,
    parent_id: str | None = None,
) -> dict[str, Any]:
    render_kind, asset_source = _select_render_kind(labware=labware, load_name=load_name)
    item = {
        "id": item_id,
        "parent_id": parent_id,
        "type": getattr(entry, "type", labware.__class__.__name__.lower()),
        "name": getattr(labware, "name", item_id),
        "model_name": getattr(labware, "model_name", ""),
        "render_kind": render_kind,
        "asset_path": None,
        "asset_source_path": str(asset_source) if asset_source is not None else None,
        "primary_position": _coord_dict(labware.get_initial_position()),
        "dimensions": _dimensions_payload(labware),
        "points": _points_payload(labware),
        "render_meta": {},
    }
    if isinstance(entry, (WellPlateYamlEntry, NestedWellPlateYamlEntry)):
        item["render_meta"] = _well_plate_render_meta(entry, labware)
    elif isinstance(entry, TipRackYamlEntry):
        item["render_meta"] = _tip_rack_render_meta(entry, labware)
    elif isinstance(entry, (VialYamlEntry, NestedVialYamlEntry)):
        item["render_meta"] = {
            "diameter_mm": getattr(entry, "diameter_mm", None),
            "height_mm": getattr(entry, "height_mm", None),
        }
    elif isinstance(entry, (WellPlateHolderYamlEntry, VialHolderYamlEntry)):
        item["render_meta"] = {
            "location": _coord_dict(getattr(labware, "location", labware.get_initial_position())),
            "labware_support_height_mm": getattr(labware, "labware_support_height_mm", None),
            "labware_seat_height_from_bottom_mm": getattr(
                labware,
                "labware_seat_height_from_bottom_mm",
                None,
            ),
        }
    elif getattr(entry, "type", None) == "tip_disposal":
        item["render_meta"] = {
            "location": _coord_dict(getattr(labware, "location", labware.get_initial_position())),
        }
    return item


def _flatten_scene_items(
    *,
    deck: Deck,
    resolved_entries: dict[str, Any],
    original_entries: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for deck_key, labware in deck.labware.items():
        resolved_entry = resolved_entries[deck_key]
        original_entry = original_entries.get(deck_key, {})
        load_name = original_entry.get("load_name")
        items.append(
            _scene_item_payload(
                item_id=deck_key,
                labware=labware,
                entry=resolved_entry,
                load_name=load_name,
            )
        )
        if isinstance(labware, WellPlateHolder) and resolved_entry.well_plate is not None:
            child_labware = labware.contained_labware.get("plate")
            if child_labware is not None:
                items.append(
                    _scene_item_payload(
                        item_id=f"{deck_key}.plate",
                        labware=child_labware,
                        entry=resolved_entry.well_plate,
                        load_name=None,
                        parent_id=deck_key,
                    )
                )
        if isinstance(labware, VialHolder):
            for vial_key, vial_entry in resolved_entry.vials.items():
                child_labware = labware.contained_labware.get(vial_key)
                if child_labware is None:
                    continue
                items.append(
                    _scene_item_payload(
                        item_id=f"{deck_key}.{vial_key}",
                        labware=child_labware,
                        entry=vial_entry,
                        load_name=None,
                        parent_id=deck_key,
                    )
                )
    return items


def _copy_scene_assets(scene_items: list[dict[str, Any]], *, output_path: Path | None) -> None:
    if output_path is None:
        for item in scene_items:
            item["asset_path"] = item.pop("asset_source_path", None)
        return

    asset_dir = output_path.parent / "assets"
    copied: dict[Path, str] = {}
    for item in scene_items:
        source_path_value = item.pop("asset_source_path", None)
        if source_path_value is None:
            item["asset_path"] = None
            continue
        source_path = Path(source_path_value)
        if source_path not in copied:
            asset_dir.mkdir(parents=True, exist_ok=True)
            destination = asset_dir / source_path.name
            shutil.copy2(source_path, destination)
            copied[source_path] = str(Path("assets") / destination.name)
        item["asset_path"] = copied[source_path]


def _build_scene(
    *,
    gantry_config: GantryConfig,
    deck: Deck,
    board_schema: BoardYamlSchema,
    board: Board,
    deck_original: dict[str, Any],
    deck_resolved_schema: DeckYamlSchema,
    output_path: Path | None,
) -> dict[str, Any]:
    scene_items = _flatten_scene_items(
        deck=deck,
        resolved_entries=deck_resolved_schema.labware,
        original_entries=deck_original.get("labware", {}),
    )
    _copy_scene_assets(scene_items, output_path=output_path)
    instruments = []
    initial_gantry_pose = MotionPose(x=0.0, y=0.0, z=DEFAULT_USER_MAX_Z_HEIGHT)
    for instrument_id, entry in board_schema.instruments.items():
        instrument = board.instruments[instrument_id]
        instruments.append(
            {
                "id": instrument_id,
                "type": entry.type,
                "vendor": entry.vendor,
                "offset_x": instrument.offset_x,
                "offset_y": instrument.offset_y,
                "depth": instrument.depth,
                "measurement_height": instrument.measurement_height,
                "initial_tip_pose": resolve_instrument_tip_pose(
                    initial_gantry_pose,
                    instrument,
                ).to_dict(),
            }
        )

    return {
        "gantry": {
            "working_volume": {
                "x_min": gantry_config.working_volume.x_min,
                "x_max": gantry_config.working_volume.x_max,
                "y_min": gantry_config.working_volume.y_min,
                "y_max": gantry_config.working_volume.y_max,
                "z_min": gantry_config.working_volume.z_min,
                "z_max": gantry_config.working_volume.z_max,
            },
            "homing_strategy": gantry_config.homing_strategy.value,
            "y_axis_motion": gantry_config.y_axis_motion.value,
            "initial_gantry_pose": initial_gantry_pose.to_dict(),
            "safe_z_height": DEFAULT_USER_SAFE_Z_HEIGHT,
            "max_z_height": DEFAULT_USER_MAX_Z_HEIGHT,
        },
        "deck": scene_items,
        "instruments": instruments,
    }


def _ensure_supported_protocol(protocol: Protocol) -> None:
    unsupported = sorted(
        {
            step.command_name
            for step in protocol.steps
            if step.command_name not in _SUPPORTED_PHASE_ONE_COMMANDS
        }
    )
    if unsupported:
        raise NotImplementedError(
            "Phase 1 exporter currently supports only move commands. "
            f"Unsupported commands: {', '.join(unsupported)}"
        )


def _run_traced_protocol(protocol: Protocol, context: ProtocolContext, board: TracingBoard) -> None:
    _install_action_wrappers(protocol, board)
    board.connect_instruments()
    try:
        for step in protocol.steps:
            board.set_active_step(step)
            step.execute(context)
        board.set_active_step(None)
    finally:
        board.disconnect_instruments()


def export_bundle(
    *,
    gantry_path: str | Path,
    deck_path: str | Path,
    board_path: str | Path,
    protocol_path: str | Path,
    output_path: str | Path | None = None,
    skip_validation: bool = False,
) -> dict[str, Any]:
    """Build a digital twin bundle from CubOS config files."""

    resolved_output_path = Path(output_path) if output_path is not None else None
    gantry_config = load_gantry_from_yaml_safe(gantry_path)
    deck = load_deck_from_yaml_safe(deck_path, total_z_height=gantry_config.total_z_height)

    tracing_gantry = _TracingGantry()
    loaded_board = load_board_from_yaml_safe(board_path, tracing_gantry, mock_mode=True)
    timeline: list[dict[str, Any]] = []
    tracing_board = TracingBoard(
        gantry=tracing_gantry,
        instruments=loaded_board.instruments,
        timeline=timeline,
        deck=deck,
    )
    protocol = load_protocol_from_yaml_safe(protocol_path)
    _ensure_supported_protocol(protocol)

    violations = validate_deck_positions(gantry_config, deck)
    violations.extend(validate_gantry_positions(gantry_config, deck, tracing_board))
    if violations and not skip_validation:
        raise SetupValidationError(violations)

    board_schema = BoardYamlSchema.model_validate(_load_yaml(board_path))
    deck_original = _load_yaml(deck_path)
    deck_resolved_schema = load_deck_render_schema(deck_path)

    context = ProtocolContext(
        board=tracing_board,
        deck=deck,
        positions=protocol.positions,
        gantry=gantry_config,
    )
    _run_traced_protocol(protocol, context, tracing_board)

    bundle = {
        "scene": _build_scene(
            gantry_config=gantry_config,
            deck=deck,
            board_schema=board_schema,
            board=tracing_board,
            deck_original=deck_original,
            deck_resolved_schema=deck_resolved_schema,
            output_path=resolved_output_path,
        ),
        "timeline": timeline,
        "summary": {
            "step_count": len(protocol.steps),
            "timeline_event_count": len(timeline),
            "total_display_duration_s": sum(_event_base_duration(event) for event in timeline),
            "validation_skipped": skip_validation,
            "validation_violation_count": len(violations),
        },
    }
    return bundle


def export_bundle_to_path(
    *,
    gantry_path: str | Path,
    deck_path: str | Path,
    board_path: str | Path,
    protocol_path: str | Path,
    output_path: str | Path,
    skip_validation: bool = False,
) -> dict[str, Any]:
    """Build and write a digital twin bundle to disk."""

    resolved_output_path = Path(output_path)
    bundle = export_bundle(
        gantry_path=gantry_path,
        deck_path=deck_path,
        board_path=board_path,
        protocol_path=protocol_path,
        output_path=resolved_output_path,
        skip_validation=skip_validation,
    )
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(json.dumps(bundle, indent=2) + "\n")
    return bundle
