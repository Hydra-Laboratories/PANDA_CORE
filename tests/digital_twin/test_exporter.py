import json
from pathlib import Path

from digital_twin.exporter import export_bundle, export_bundle_to_path


ROOT = Path(__file__).resolve().parents[2]


def test_export_bundle_builds_expected_move_trace():
    bundle = export_bundle(
        gantry_path=ROOT / "configs/gantry/cubos.yaml",
        deck_path=ROOT / "configs/deck/mofcat_deck.yaml",
        board_path=ROOT / "configs/board/mock_mofcat_board.yaml",
        protocol_path=ROOT / "configs/protocol/move.yaml",
    )

    assert bundle["summary"]["step_count"] == 1
    assert bundle["summary"]["timeline_event_count"] == 2
    assert [event["phase"] for event in bundle["timeline"]] == [
        "traverse_xy",
        "descend_z",
    ]
    assert bundle["timeline"][0]["instrument_id"] == "uvvis"
    assert bundle["timeline"][0]["target_label"] == "plate_1.A1"
    assert bundle["timeline"][-1]["end_tip_pose"] == {
        "x": 17.88,
        "y": 42.23,
        "z": 70.0,
    }


def test_export_bundle_reflects_offset_tip_pose(tmp_path):
    board_path = tmp_path / "board.yaml"
    board_path.write_text(
        """
instruments:
  uvvis:
    type: uvvis_ccs
    vendor: thorlabs
    offset_x: 10.0
    offset_y: -5.0
    depth: 7.0
    measurement_height: 3.0
""".strip()
        + "\n"
    )

    bundle = export_bundle(
        gantry_path=ROOT / "configs/gantry/cubos.yaml",
        deck_path=ROOT / "configs/deck/mofcat_deck.yaml",
        board_path=board_path,
        protocol_path=ROOT / "configs/protocol/move.yaml",
    )

    final_event = bundle["timeline"][-1]
    assert final_event["end_gantry_pose"] != final_event["end_tip_pose"]
    assert final_event["end_gantry_pose"] == {
        "x": 7.88,
        "y": 47.23,
        "z": 63.0,
    }
    assert final_event["end_tip_pose"] == {
        "x": 17.88,
        "y": 42.23,
        "z": 70.0,
    }


def test_export_bundle_to_path_writes_json(tmp_path):
    output_path = tmp_path / "bundle.json"
    export_bundle_to_path(
        gantry_path=ROOT / "configs/gantry/cubos.yaml",
        deck_path=ROOT / "configs/deck/mofcat_deck.yaml",
        board_path=ROOT / "configs/board/mock_mofcat_board.yaml",
        protocol_path=ROOT / "configs/protocol/move.yaml",
        output_path=output_path,
    )

    saved = json.loads(output_path.read_text())
    assert saved["summary"]["timeline_event_count"] == 2


def test_export_bundle_supports_scan_protocol():
    bundle = export_bundle(
        gantry_path=ROOT / "configs/gantry/cubos.yaml",
        deck_path=ROOT / "configs/deck/mofcat_deck.yaml",
        board_path=ROOT / "configs/board/mock_mofcat_board.yaml",
        protocol_path=ROOT / "configs/protocol/cubos_scan_test.yaml",
    )

    motion_events = [event for event in bundle["timeline"] if event["type"] == "motion"]
    action_events = [event for event in bundle["timeline"] if event["type"] == "action"]

    assert bundle["summary"]["step_count"] == 2
    assert len(action_events) == 96
    assert motion_events[0]["target_label"] == "plate_1.A1"
    assert action_events[0]["target_label"] == "plate_1.A1"
    assert action_events[1]["target_label"] == "plate_1.A2"
    assert action_events[-1]["target_label"] == "plate_1.H12"
    assert all(event["kind"] == "measure" for event in action_events)


def test_export_bundle_can_skip_validation_for_visualization_combo():
    bundle = export_bundle(
        gantry_path=ROOT / "configs/gantry/cubos_xl.yaml",
        deck_path=ROOT / "configs/deck/panda_deck.yaml",
        board_path=ROOT / "configs/board/asmi_board.yaml",
        protocol_path=ROOT / "configs/protocol/asmi_panda_deck_test.yaml",
        skip_validation=True,
    )

    assert bundle["summary"]["validation_skipped"] is True
    assert bundle["summary"]["validation_violation_count"] == 0
    assert bundle["timeline"][0]["target_label"] == "well_plate_holder.plate.A1"


def test_export_bundle_supports_two_instrument_visualization_protocol():
    bundle = export_bundle(
        gantry_path=ROOT / "configs/gantry/cubos_xl.yaml",
        deck_path=ROOT / "configs/deck/two_instrument_deck.yaml",
        board_path=ROOT / "configs/board/two_instrument_board.yaml",
        protocol_path=ROOT / "configs/protocol/two_instrument_visualization_test.yaml",
    )

    motion_events = [event for event in bundle["timeline"] if event["type"] == "motion"]
    assert bundle["summary"]["step_count"] == 9
    assert bundle["summary"]["timeline_event_count"] >= 9
    assert motion_events[0]["instrument_id"] == "liquid_handler"
    assert motion_events[0]["target_label"] == "tip_rack.A1"
    assert any(event["instrument_id"] == "potentiostat" for event in motion_events)
    assert motion_events[-1]["target_label"] == "tip_disposal"
