"""Tests for initial_volume_ul on Vial model and YAML schema."""

import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from deck.labware.labware import Coordinate3D
from deck.labware.vial import Vial
from deck.loader import load_deck_from_yaml
from deck.yaml_schema import VialYamlEntry


# ── Vial model tests ─────────────────────────────────────────────────────────


class TestVialInitialVolume:

    def test_default_initial_volume_is_zero(self):
        vial = Vial(
            name="vial_1",
            model_name="test_vial",
            height_mm=66.75,
            diameter_mm=28.0,
            location=Coordinate3D(x=0.0, y=0.0, z=0.0),
            capacity_ul=1500.0,
            working_volume_ul=1200.0,
        )
        assert vial.initial_volume_ul == 0.0

    def test_explicit_initial_volume(self):
        vial = Vial(
            name="vial_1",
            model_name="test_vial",
            height_mm=66.75,
            diameter_mm=28.0,
            location=Coordinate3D(x=0.0, y=0.0, z=0.0),
            capacity_ul=1500.0,
            working_volume_ul=1200.0,
            initial_volume_ul=500.0,
        )
        assert vial.initial_volume_ul == 500.0

    def test_initial_volume_at_capacity(self):
        vial = Vial(
            name="vial_1",
            model_name="test_vial",
            height_mm=66.75,
            diameter_mm=28.0,
            location=Coordinate3D(x=0.0, y=0.0, z=0.0),
            capacity_ul=1500.0,
            working_volume_ul=1200.0,
            initial_volume_ul=1500.0,
        )
        assert vial.initial_volume_ul == 1500.0

    def test_initial_volume_exceeding_capacity_raises(self):
        with pytest.raises(ValidationError, match="initial_volume_ul"):
            Vial(
                name="vial_1",
                model_name="test_vial",
                height_mm=66.75,
                diameter_mm=28.0,
                location=Coordinate3D(x=0.0, y=0.0, z=0.0),
                capacity_ul=1500.0,
                working_volume_ul=1200.0,
                initial_volume_ul=2000.0,
            )

    def test_negative_initial_volume_raises(self):
        with pytest.raises(ValidationError, match="initial_volume_ul"):
            Vial(
                name="vial_1",
                model_name="test_vial",
                height_mm=66.75,
                diameter_mm=28.0,
                location=Coordinate3D(x=0.0, y=0.0, z=0.0),
                capacity_ul=1500.0,
                working_volume_ul=1200.0,
                initial_volume_ul=-10.0,
            )


# ── YAML schema tests ────────────────────────────────────────────────────────


class TestVialYamlEntryInitialVolume:

    def test_default_initial_volume_is_zero(self):
        entry = VialYamlEntry(
            type="vial",
            name="v",
            model_name="m",
            height_mm=50.0,
            diameter_mm=20.0,
            location={"x": 0.0, "y": 0.0, "z": 0.0},
            capacity_ul=1500.0,
            working_volume_ul=1200.0,
        )
        assert entry.initial_volume_ul == 0.0

    def test_explicit_initial_volume(self):
        entry = VialYamlEntry(
            type="vial",
            name="v",
            model_name="m",
            height_mm=50.0,
            diameter_mm=20.0,
            location={"x": 0.0, "y": 0.0, "z": 0.0},
            capacity_ul=1500.0,
            working_volume_ul=1200.0,
            initial_volume_ul=800.0,
        )
        assert entry.initial_volume_ul == 800.0

    def test_initial_volume_exceeding_capacity_raises(self):
        with pytest.raises(ValidationError, match="initial_volume_ul"):
            VialYamlEntry(
                type="vial",
                name="v",
                model_name="m",
                height_mm=50.0,
                diameter_mm=20.0,
                location={"x": 0.0, "y": 0.0, "z": 0.0},
                capacity_ul=1500.0,
                working_volume_ul=1200.0,
                initial_volume_ul=2000.0,
            )


# ── Deck loader integration ──────────────────────────────────────────────────


YAML_VIAL_WITH_INITIAL_VOLUME = """\
labware:
  reagent_vial:
    type: vial
    name: reagent_vial
    model_name: standard_vial
    height_mm: 66.75
    diameter_mm: 28.0
    location:
      x: -30.0
      y: -40.0
      z: -20.0
    capacity_ul: 5000.0
    working_volume_ul: 4000.0
    initial_volume_ul: 3000.0
"""

YAML_VIAL_NO_INITIAL_VOLUME = """\
labware:
  reagent_vial:
    type: vial
    name: reagent_vial
    model_name: standard_vial
    height_mm: 66.75
    diameter_mm: 28.0
    location:
      x: -30.0
      y: -40.0
      z: -20.0
    capacity_ul: 5000.0
    working_volume_ul: 4000.0
"""


class TestDeckLoaderInitialVolume:

    def test_vial_with_initial_volume_loaded(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(YAML_VIAL_WITH_INITIAL_VOLUME)
            f.flush()
            deck = load_deck_from_yaml(f.name)

        vial = deck["reagent_vial"]
        assert isinstance(vial, Vial)
        assert vial.initial_volume_ul == 3000.0

    def test_vial_without_initial_volume_defaults_to_zero(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(YAML_VIAL_NO_INITIAL_VOLUME)
            f.flush()
            deck = load_deck_from_yaml(f.name)

        vial = deck["reagent_vial"]
        assert isinstance(vial, Vial)
        assert vial.initial_volume_ul == 0.0
