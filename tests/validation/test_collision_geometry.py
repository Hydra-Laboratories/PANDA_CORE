from __future__ import annotations

from validation.collision import CollisionBox
from gantry.gantry_config import WorkingVolume


def test_boxes_intersect_with_positive_overlap() -> None:
    a = CollisionBox(0, 10, 0, 10, 0, 10)
    b = CollisionBox(5, 15, 5, 15, 5, 15)

    assert a.intersects(b)
    assert b.intersects(a)


def test_touching_boundaries_do_not_intersect() -> None:
    a = CollisionBox(0, 10, 0, 10, 0, 10)
    b = CollisionBox(10, 20, 0, 10, 0, 10)

    assert not a.intersects(b)
    assert not a.overlaps_xy(b)


def test_xy_overlap_is_independent_of_z_overlap() -> None:
    a = CollisionBox(0, 10, 0, 10, 0, 10)
    b = CollisionBox(5, 15, 5, 15, 20, 30)

    assert a.overlaps_xy(b)
    assert not a.intersects(b)


def test_box_translation_preserves_size() -> None:
    box = CollisionBox(0, 10, 1, 11, 2, 12)

    moved = box.translated(3, 4, 5)

    assert moved == CollisionBox(3, 13, 5, 15, 7, 17)


def test_working_volume_containment() -> None:
    volume = WorkingVolume(0, 20, 0, 20, 0, 20)

    assert CollisionBox(1, 10, 1, 10, 1, 10).contained_by(volume)
    assert not CollisionBox(-1, 10, 1, 10, 1, 10).contained_by(volume)


def test_center_base_constructor_uses_base_z_and_xy_center() -> None:
    box = CollisionBox.from_center_base(
        center_x=10,
        center_y=20,
        base_z=5,
        size_x=4,
        size_y=6,
        size_z=8,
    )

    assert box == CollisionBox(8, 12, 17, 23, 5, 13)
