"""Verify all implementations satisfy their Protocol contracts.

These tests ensure that every class claiming to implement a contract
actually provides all required methods and attributes. If a contract
test fails, it means someone changed a class or contract without
keeping them in sync.
"""

import pytest

from src.contracts import (
    DataStoreInterface,
    DeckInterface,
    FilmetricsInterface,
    GantryInterface,
    InstrumentInterface,
    PipetteInterface,
    UVVisCCSInterface,
)


class TestGantryContract:
    """Gantry and OfflineGantry must satisfy GantryInterface."""

    def test_offline_gantry_satisfies_contract(self):
        from src.gantry.offline import OfflineGantry

        gantry = OfflineGantry()
        assert isinstance(gantry, GantryInterface)

    def test_gantry_class_satisfies_contract(self):
        from src.gantry.gantry import Gantry

        gantry = Gantry()
        assert isinstance(gantry, GantryInterface)


class TestInstrumentContracts:
    """All instrument drivers and mocks must satisfy InstrumentInterface."""

    def test_mock_pipette_satisfies_instrument_interface(self):
        from instruments.pipette.mock import MockPipette

        pipette = MockPipette()
        assert isinstance(pipette, InstrumentInterface)

    def test_mock_filmetrics_satisfies_instrument_interface(self):
        from instruments.filmetrics.mock import MockFilmetrics

        fm = MockFilmetrics()
        assert isinstance(fm, InstrumentInterface)

    def test_mock_uvvis_satisfies_instrument_interface(self):
        from instruments.uvvis_ccs.mock import MockUVVisCCS

        uvvis = MockUVVisCCS()
        assert isinstance(uvvis, InstrumentInterface)


class TestPipetteContract:
    """Pipette and MockPipette must satisfy PipetteInterface."""

    def test_mock_pipette_satisfies_pipette_interface(self):
        from instruments.pipette.mock import MockPipette

        pipette = MockPipette()
        assert isinstance(pipette, PipetteInterface)


class TestFilmetricsContract:
    """Filmetrics and MockFilmetrics must satisfy FilmetricsInterface."""

    def test_mock_filmetrics_satisfies_filmetrics_interface(self):
        from instruments.filmetrics.mock import MockFilmetrics

        fm = MockFilmetrics()
        assert isinstance(fm, FilmetricsInterface)


class TestUVVisCCSContract:
    """UVVisCCS and MockUVVisCCS must satisfy UVVisCCSInterface."""

    def test_mock_uvvis_satisfies_uvvis_interface(self):
        from instruments.uvvis_ccs.mock import MockUVVisCCS

        uvvis = MockUVVisCCS()
        assert isinstance(uvvis, UVVisCCSInterface)


class TestDeckContract:
    """Deck must satisfy DeckInterface."""

    def test_deck_satisfies_deck_interface(self):
        from src.deck.deck import Deck

        deck = Deck(labware={})
        assert isinstance(deck, DeckInterface)


class TestDataStoreContract:
    """DataStore must satisfy DataStoreInterface."""

    def test_data_store_satisfies_data_store_interface(self):
        from data.data_store import DataStore

        store = DataStore(db_path=":memory:")
        try:
            assert isinstance(store, DataStoreInterface)
        finally:
            store.close()
