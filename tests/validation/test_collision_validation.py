from __future__ import annotations

from unittest.mock import MagicMock

from board.board import Board
from deck.deck import Deck
from deck.labware.labware import Coordinate3D
from deck.labware.vial import Vial
from deck.labware.well_plate import WellPlate
from gantry.gantry_config import GantryConfig, HomingStrategy, WorkingVolume
from protocol_engine.protocol import Protocol, ProtocolContext, ProtocolStep
from validation.collision import (
    CollisionBox,
    CollisionSettings,
    CollisionValidationMode,
    build_labware_envelopes,
    compute_required_safe_z,
    extract_collision_poses,
    instrument_envelope_at,
    validate_collision_safety,
)


def _gantry(z_min: float = 0.0, z_max: float = 100.0) -> GantryConfig:
    return GantryConfig(
        serial_port="/dev/null",
        homing_strategy=HomingStrategy.STANDARD,
        total_z_height=120.0,
        working_volume=WorkingVolume(0, 200, 0, 200, z_min, z_max),
    )


def _vial(name: str = "vial_1", x: float = 50.0, y: float = 50.0, z: float = 20.0) -> Vial:
    return Vial(
        name=name,
        model_name="vial",
        height_mm=10.0,
        diameter_mm=10.0,
        location=Coordinate3D(x=x, y=y, z=z),
        capacity_ul=1000.0,
        working_volume_ul=800.0,
    )


def _plate() -> WellPlate:
    wells = {
        "A1": Coordinate3D(x=20.0, y=20.0, z=5.0),
        "A2": Coordinate3D(x=30.0, y=20.0, z=5.0),
        "B1": Coordinate3D(x=20.0, y=30.0, z=5.0),
        "B2": Coordinate3D(x=30.0, y=30.0, z=5.0),
    }
    return WellPlate(
        name="plate",
        model_name="plate",
        length_mm=30.0,
        width_mm=30.0,
        height_mm=8.0,
        rows=2,
        columns=2,
        wells=wells,
    )


def _instrument(
    *,
    name: str,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    depth: float = 0.0,
    measurement_height: float = 0.0,
    origin_z: float = -12.0,
    size_x: float = 4.0,
    size_y: float = 4.0,
    size_z: float = 4.0,
):
    instrument = MagicMock()
    instrument.name = name
    instrument.offset_x = offset_x
    instrument.offset_y = offset_y
    instrument.depth = depth
    instrument.measurement_height = measurement_height
    instrument.collision_geometry = {
        "kind": "box",
        "size": {"x": size_x, "y": size_y, "z": size_z},
        "origin_offset": {"x": -size_x / 2, "y": -size_y / 2, "z": origin_z},
    }
    return instrument


def _context(
    *,
    deck: Deck | None = None,
    instruments: dict | None = None,
    positions: dict | None = None,
) -> ProtocolContext:
    board = Board(gantry=MagicMock(), instruments=instruments or {
        "pipette": _instrument(name="pipette"),
    })
    return ProtocolContext(
        board=board,
        deck=deck or Deck({"vial_1": _vial()}),
        positions=positions or {},
        gantry=_gantry(),
    )


def _protocol(*steps: ProtocolStep) -> Protocol:
    return Protocol(list(steps))


def _step(index: int, command: str, args: dict) -> ProtocolStep:
    return ProtocolStep(index=index, command_name=command, handler=lambda *_args, **_kwargs: None, args=args)


def test_vial_envelope_uses_diameter_and_height() -> None:
    envelopes, report = build_labware_envelopes(Deck({"vial_1": _vial()}))

    assert report.ok
    assert envelopes[0].box == CollisionBox(45, 55, 45, 55, 20, 30)


def test_well_plate_envelope_uses_well_spread_and_dimensions() -> None:
    envelopes, report = build_labware_envelopes(Deck({"plate": _plate()}))

    assert report.ok
    assert envelopes[0].box == CollisionBox(10, 40, 10, 40, 5, 13)


def test_missing_labware_geometry_warns_in_report_only() -> None:
    plate = _plate()
    plate.length_mm = None
    plate.geometry.length_mm = None

    _, report = build_labware_envelopes(
        Deck({"plate": plate}),
        settings=CollisionSettings(mode=CollisionValidationMode.REPORT_ONLY),
    )

    assert not report.errors
    assert report.warnings[0].code == "missing_labware_geometry"


def test_instrument_envelope_uses_board_offsets_and_depth() -> None:
    instr = _instrument(
        name="camera",
        offset_x=10,
        offset_y=20,
        depth=5,
        origin_z=1,
        size_x=2,
        size_y=4,
        size_z=6,
    )

    envelope = instrument_envelope_at(
        instrument_name="camera",
        instrument=instr,
        gantry_x=100,
        gantry_y=50,
        gantry_z=10,
    )

    assert envelope is not None
    assert envelope.box == CollisionBox(109, 111, 68, 72, 16, 22)


def test_move_pose_resolves_named_raw_and_deck_targets() -> None:
    context = _context(positions={"safe": [1, 2, 3]})
    protocol = _protocol(
        _step(0, "move", {"instrument": "pipette", "position": "safe"}),
        _step(1, "move", {"instrument": "pipette", "position": [4, 5, 6]}),
        _step(2, "move", {"instrument": "pipette", "position": "vial_1"}),
    )

    poses, report = extract_collision_poses(protocol, context)

    assert report.ok
    assert [(p.target.x, p.target.y, p.target.z, p.target_key) for p in poses] == [
        (1, 2, 3, None),
        (4, 5, 6, None),
        (50, 50, 20, "vial_1"),
    ]


def test_scan_and_measure_preserve_existing_measurement_height_signs() -> None:
    plate = _plate()
    context = _context(
        deck=Deck({"plate": plate}),
        instruments={"sensor": _instrument(name="sensor", measurement_height=2.0)},
    )
    protocol = _protocol(
        _step(0, "scan", {"plate": "plate", "instrument": "sensor", "method": "measure"}),
        _step(1, "measure", {"position": "plate.A1", "instrument": "sensor", "method": "measure"}),
    )

    poses, report = extract_collision_poses(protocol, context)

    assert report.ok
    assert [pose.target.z for pose in poses[:4]] == [3.0, 3.0, 3.0, 3.0]
    assert poses[4].target.z == 7.0


def test_transfer_extracts_source_and_destination() -> None:
    context = _context(deck=Deck({"source": _vial("source", x=10), "dest": _vial("dest", x=90)}))
    protocol = _protocol(_step(0, "transfer", {
        "source": "source",
        "destination": "dest",
        "volume_ul": 10,
    }))

    poses, report = extract_collision_poses(protocol, context)

    assert report.ok
    assert [(pose.purpose, pose.target_key) for pose in poses] == [
        ("source", "source"),
        ("destination", "dest"),
    ]


def test_home_pause_and_breakpoint_are_collision_noops() -> None:
    context = _context()
    protocol = _protocol(
        _step(0, "home", {}),
        _step(1, "pause", {"seconds": 1}),
        _step(2, "breakpoint", {}),
    )

    poses, report = extract_collision_poses(protocol, context)

    assert poses == []
    assert report.ok


def test_strict_validation_fails_missing_instrument_geometry() -> None:
    instr = _instrument(name="pipette")
    instr.collision_geometry = None
    context = _context(instruments={"pipette": instr})
    protocol = _protocol(_step(0, "move", {"instrument": "pipette", "position": "vial_1"}))

    report = validate_collision_safety(protocol, context, _gantry())

    assert any(issue.code == "missing_instrument_geometry" for issue in report.errors)


def test_report_only_missing_instrument_geometry_warns() -> None:
    instr = _instrument(name="pipette")
    instr.collision_geometry = None
    context = _context(instruments={"pipette": instr})
    protocol = _protocol(_step(0, "move", {"instrument": "pipette", "position": "vial_1"}))

    report = validate_collision_safety(
        protocol,
        context,
        _gantry(),
        settings=CollisionSettings(mode=CollisionValidationMode.REPORT_ONLY),
    )

    assert not report.errors
    assert any(issue.code == "missing_instrument_geometry" for issue in report.warnings)


def test_non_active_side_mounted_instrument_collision_fails() -> None:
    context = _context(instruments={
        "pipette": _instrument(name="pipette", origin_z=12),
        "camera": _instrument(name="camera", origin_z=0, size_x=12, size_y=12, size_z=5),
    })
    protocol = _protocol(_step(0, "move", {"instrument": "pipette", "position": "vial_1"}))

    report = validate_collision_safety(protocol, context, _gantry())

    assert any(
        issue.code == "instrument_labware_collision"
        and issue.body_a == "camera"
        and issue.body_b == "vial_1"
        for issue in report.errors
    )


def test_report_only_downgrades_collisions_to_warnings() -> None:
    context = _context(instruments={
        "pipette": _instrument(name="pipette", origin_z=-12),
        "camera": _instrument(name="camera", origin_z=0, size_x=12, size_y=12, size_z=5),
    })
    protocol = _protocol(_step(0, "move", {"instrument": "pipette", "position": "vial_1"}))

    report = validate_collision_safety(
        protocol,
        context,
        _gantry(),
        settings=CollisionSettings(mode=CollisionValidationMode.REPORT_ONLY),
    )

    assert report.ok
    assert any(issue.code == "instrument_labware_collision" for issue in report.warnings)


def test_xy_overlap_with_sufficient_z_clearance_passes() -> None:
    context = _context(instruments={
        "pipette": _instrument(name="pipette", origin_z=-12),
        "camera": _instrument(name="camera", origin_z=-20, size_x=12, size_y=12, size_z=5),
    })
    protocol = _protocol(_step(0, "move", {"instrument": "pipette", "position": "vial_1"}))

    report = validate_collision_safety(protocol, context, _gantry())

    assert report.ok


def test_required_safe_z_above_working_volume_fails() -> None:
    context = _context(deck=Deck({"vial_1": _vial(z=1)}))
    protocol = _protocol(_step(0, "move", {"instrument": "pipette", "position": "vial_1"}))

    report = validate_collision_safety(protocol, context, _gantry(z_max=100))

    assert compute_required_safe_z(build_labware_envelopes(context.deck)[0], clearance_mm=2) == -1
    assert any(issue.code == "safe_z_out_of_volume" for issue in report.errors)


def test_active_nested_target_does_not_exempt_parent_holder() -> None:
    from deck.labware.vial_holder import VialHolder

    child = _vial("vial_1", x=50.0, y=50.0, z=25.0)
    holder = VialHolder(
        name="holder",
        model_name="holder",
        location=Coordinate3D(x=50.0, y=50.0, z=20.0),
        contained_labware={"vial_1": child},
    )
    context = _context(
        deck=Deck({"holder": holder}),
        instruments={"pipette": _instrument(name="pipette", origin_z=20, size_x=20, size_y=20, size_z=5)},
    )
    protocol = _protocol(_step(0, "move", {
        "instrument": "pipette",
        "position": "holder.vial_1",
    }))

    report = validate_collision_safety(protocol, context, _gantry())

    assert any(
        issue.code == "instrument_labware_collision"
        and issue.body_a == "pipette"
        and issue.body_b == "holder"
        for issue in report.errors
    )


def test_active_nested_well_target_allows_child_plate_not_parent_holder() -> None:
    from deck.labware.well_plate_holder import WellPlateHolder

    holder = WellPlateHolder(
        name="holder",
        model_name="holder",
        location=Coordinate3D(x=25.0, y=25.0, z=20.0),
        contained_labware={"plate": _plate()},
    )
    context = _context(
        deck=Deck({"holder": holder}),
        instruments={"pipette": _instrument(name="pipette", origin_z=20, size_x=20, size_y=20, size_z=5)},
    )
    protocol = _protocol(_step(0, "move", {
        "instrument": "pipette",
        "position": "holder.plate.A1",
    }))

    report = validate_collision_safety(protocol, context, _gantry())

    assert any(
        issue.code == "instrument_labware_collision"
        and issue.body_a == "pipette"
        and issue.body_b == "holder"
        for issue in report.errors
    )
    assert not any(
        issue.code == "instrument_labware_collision"
        and issue.body_a == "pipette"
        and issue.body_b == "holder.plate"
        for issue in report.errors
    )
