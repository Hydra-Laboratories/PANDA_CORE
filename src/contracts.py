"""Cross-module contracts for PANDA_CORE.

These Protocol classes define the structural interfaces that cross module
boundaries. They use Python's typing.Protocol (PEP 544) for structural
subtyping — implementations satisfy them automatically without inheritance.

COORDINATION REQUIRED: Do not modify without checking BACKLOG.md.
Changes here affect every module. Contracts are additive-only —
removing methods requires coordinating with all agents.

Usage in tests:
    from src.contracts import GantryInterface
    assert isinstance(my_gantry, GantryInterface)
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


# ═══════════════════════════════════════════════════════════════════
# GANTRY CONTRACT
# ═══════════════════════════════════════════════════════════════════

@runtime_checkable
class GantryInterface(Protocol):
    """Contract for anything that behaves like a Gantry.

    Satisfied by: Gantry, OfflineGantry
    Used by: Board, validation, protocol_engine
    """

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def is_healthy(self) -> bool: ...
    def home(self) -> None: ...
    def move_to(self, x: float, y: float, z: float) -> None: ...
    def get_coordinates(self) -> dict[str, float]: ...
    def get_status(self) -> str: ...
    def stop(self) -> None: ...


# ═══════════════════════════════════════════════════════════════════
# INSTRUMENT CONTRACTS
# ═══════════════════════════════════════════════════════════════════

@runtime_checkable
class InstrumentInterface(Protocol):
    """Contract for anything that behaves like a BaseInstrument.

    Satisfied by: All instrument drivers and mocks
    Used by: Board (offset math), protocol_engine (command dispatch)
    """

    name: str
    offset_x: float
    offset_y: float
    depth: float
    measurement_height: float

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def health_check(self) -> bool: ...


@runtime_checkable
class PipetteInterface(Protocol):
    """Contract for anything that behaves like a Pipette.

    Satisfied by: Pipette, MockPipette
    Used by: protocol_engine commands (aspirate, dispense, mix, etc.)
    """

    name: str

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def health_check(self) -> bool: ...
    def home(self) -> None: ...
    def prime(self, speed: float = ...) -> None: ...
    def aspirate(self, volume_ul: float, speed: float = ...) -> Any: ...
    def dispense(self, volume_ul: float, speed: float = ...) -> Any: ...
    def blowout(self, speed: float = ...) -> None: ...
    def mix(self, volume_ul: float, repetitions: int = ..., speed: float = ...) -> Any: ...
    def pick_up_tip(self, speed: float = ...) -> None: ...
    def drop_tip(self, speed: float = ...) -> None: ...
    def get_status(self) -> Any: ...
    def drip_stop(self, volume_ul: float = ..., speed: float = ...) -> None: ...


@runtime_checkable
class FilmetricsInterface(Protocol):
    """Contract for anything that behaves like a Filmetrics instrument.

    Satisfied by: Filmetrics, MockFilmetrics
    Used by: protocol_engine scan command
    """

    name: str

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def health_check(self) -> bool: ...
    def acquire_sample(self) -> None: ...
    def acquire_reference(self, reference_standard: str) -> None: ...
    def acquire_background(self) -> None: ...
    def commit_baseline(self) -> None: ...
    def measure(self) -> Any: ...
    def save_spectrum(self, identifier: str) -> None: ...


@runtime_checkable
class UVVisCCSInterface(Protocol):
    """Contract for anything that behaves like a UV-Vis CCS spectrometer.

    Satisfied by: UVVisCCS, MockUVVisCCS
    Used by: protocol_engine scan command
    """

    name: str

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def health_check(self) -> bool: ...
    def set_integration_time(self, seconds: float) -> None: ...
    def get_integration_time(self) -> float: ...
    def measure(self) -> Any: ...
    def get_device_info(self) -> list[str]: ...


# ═══════════════════════════════════════════════════════════════════
# DECK CONTRACT
# ═══════════════════════════════════════════════════════════════════

@runtime_checkable
class DeckInterface(Protocol):
    """Contract for anything that behaves like a Deck.

    Satisfied by: Deck
    Used by: protocol_engine, validation
    """

    def resolve(self, target: str) -> Any: ...
    def __getitem__(self, key: str) -> Any: ...
    def __contains__(self, key: object) -> bool: ...
    def __iter__(self) -> Any: ...
    def __len__(self) -> int: ...


# ═══════════════════════════════════════════════════════════════════
# DATA STORE CONTRACT
# ═══════════════════════════════════════════════════════════════════

@runtime_checkable
class DataStoreInterface(Protocol):
    """Contract for anything that behaves like a DataStore.

    Satisfied by: DataStore
    Used by: protocol_engine (optional, via ProtocolContext.data_store)
    """

    def create_campaign(self, description: str, **kwargs: Any) -> int: ...
    def create_experiment(
        self, campaign_id: int, labware_name: str, well_id: str, **kwargs: Any,
    ) -> int: ...
    def log_measurement(self, experiment_id: int, result: Any) -> int: ...
    def close(self) -> None: ...
