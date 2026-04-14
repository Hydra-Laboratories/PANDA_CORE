from gantry.motion_planning import MotionPose, plan_safe_move_segments


def test_plan_safe_move_segments_traverses_when_already_safe():
    segments = plan_safe_move_segments(
        current_pose=MotionPose(0.0, 0.0, 5.0),
        target_pose=MotionPose(12.0, 8.0, 70.0),
    )

    assert [segment.phase for segment in segments] == ["traverse_xy", "descend_z"]
    assert segments[0].start_pose == MotionPose(0.0, 0.0, 5.0)
    assert segments[0].end_pose == MotionPose(12.0, 8.0, 5.0)
    assert segments[1].end_pose == MotionPose(12.0, 8.0, 70.0)


def test_plan_safe_move_segments_lifts_before_xy_when_below_safe():
    segments = plan_safe_move_segments(
        current_pose=MotionPose(0.0, 0.0, 20.0),
        target_pose=MotionPose(12.0, 8.0, 70.0),
    )

    assert [segment.phase for segment in segments] == [
        "lift_to_safe_z",
        "traverse_xy",
        "descend_z",
    ]
    assert segments[0].end_pose == MotionPose(0.0, 0.0, 0.0)
    assert segments[1].start_pose == MotionPose(0.0, 0.0, 0.0)
    assert segments[1].end_pose == MotionPose(12.0, 8.0, 0.0)


def test_plan_safe_move_segments_handles_z_only_move():
    segments = plan_safe_move_segments(
        current_pose=MotionPose(10.0, 10.0, 20.0),
        target_pose=MotionPose(10.0, 10.0, 60.0),
    )

    assert [segment.phase for segment in segments] == ["descend_z"]
    assert segments[0].start_pose == MotionPose(10.0, 10.0, 20.0)
    assert segments[0].end_pose == MotionPose(10.0, 10.0, 60.0)


def test_plan_safe_move_segments_does_not_lift_without_lateral_motion():
    segments = plan_safe_move_segments(
        current_pose=MotionPose(10.0, 10.0, 22.0),
        target_pose=MotionPose(10.0, 10.0, 30.0),
    )

    assert [segment.phase for segment in segments] == ["descend_z"]
