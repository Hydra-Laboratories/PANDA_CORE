"""Repository-level checks for the panda deck YAML fixture."""

from __future__ import annotations

import pytest

from deck import TipRack, VialHolder, WellPlateHolder
from deck.loader import load_deck_from_yaml


def test_repository_panda_deck_yaml_loads_with_expected_reference_points():
    deck = load_deck_from_yaml("configs/deck/panda_deck.yaml")

    assert isinstance(deck["tip_rack_a"], TipRack)
    assert deck.resolve("tip_rack_a.A1").x == pytest.approx(111.9)
    # O2 is the last tip (row O = 15th row, column 2) under the
    # 2-column × 15-row ursa layout — physically the same tip that the
    # old rows=2,cols=15 schema called B15.
    assert deck.resolve("tip_rack_a.O2").y == pytest.approx(121.7)
    assert deck.resolve("tip_rack_a.O2").x == pytest.approx(120.4)

    assert isinstance(deck["well_plate_holder"], WellPlateHolder)
    assert deck.resolve("well_plate_holder.plate.A1") == pytest.approx(
        deck.resolve("well_plate_holder.plate")
    )
    assert deck.resolve("well_plate_holder.plate.A1").z == pytest.approx(202.35)
    assert deck.resolve("well_plate_holder.plate.B1").y == pytest.approx(87.5)

    assert isinstance(deck["vial_holder"], VialHolder)
    assert deck.resolve("vial_holder.vial_1").z == pytest.approx(239.0)
    assert deck.resolve("vial_holder.vial_9").y == pytest.approx(264.9)
