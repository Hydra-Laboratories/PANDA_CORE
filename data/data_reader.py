"""Read-only query layer for the PANDA SQLite database.

Used after experiments for analysis — the write-side counterpart is DataStore.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


_VALID_MEASUREMENT_TABLES = frozenset({
    "uvvis_measurements",
    "filmetrics_measurements",
    "camera_measurements",
    "asmi_measurements"
})


@dataclass(frozen=True)
class CampaignRecord:
    """Read-only view of a campaign row."""

    id: int
    description: str
    deck_config: Optional[str]
    board_config: Optional[str]
    gantry_config: Optional[str]
    protocol_config: Optional[str]
    created_at: str
    status: str


@dataclass(frozen=True)
class ExperimentRecord:
    """Read-only view of an experiment row."""

    id: int
    campaign_id: int
    labware_name: str
    well_id: Optional[str]
    contents: Optional[str]
    created_at: str


@dataclass(frozen=True)
class LabwareRecord:
    """Read-only view of a labware row."""

    id: int
    campaign_id: int
    labware_key: str
    labware_type: str
    well_id: Optional[str]
    total_volume_ul: float
    working_volume_ul: float
    current_volume_ul: float
    contents: Optional[str]


class DataReader:
    """Read-only query interface for the PANDA SQLite database."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        connection: Optional[sqlite3.Connection] = None,
    ) -> None:
        if connection is not None:
            self._conn = connection
        elif db_path is not None:
            self._conn = sqlite3.connect(db_path)
        else:
            raise ValueError("Either db_path or connection must be provided")
        self._conn.row_factory = sqlite3.Row
        self._owns_connection = connection is None

    # ── Campaign queries ──────────────────────────────────────────────────

    def get_campaign(self, campaign_id: int) -> Optional[CampaignRecord]:
        row = self._conn.execute(
            "SELECT id, description, deck_config, board_config, "
            "gantry_config, protocol_config, created_at, status "
            "FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        if row is None:
            return None
        return CampaignRecord(**dict(row))

    def list_campaigns(self) -> List[CampaignRecord]:
        rows = self._conn.execute(
            "SELECT id, description, deck_config, board_config, "
            "gantry_config, protocol_config, created_at, status "
            "FROM campaigns ORDER BY id",
        ).fetchall()
        return [CampaignRecord(**dict(r)) for r in rows]

    # ── Experiment queries ────────────────────────────────────────────────

    def get_experiments(
        self,
        campaign_id: int,
        labware_name: Optional[str] = None,
        well_id: Optional[str] = None,
    ) -> List[ExperimentRecord]:
        query = (
            "SELECT id, campaign_id, labware_name, well_id, contents, created_at "
            "FROM experiments WHERE campaign_id = ?"
        )
        params: list[Any] = [campaign_id]

        if labware_name is not None:
            query += " AND labware_name = ?"
            params.append(labware_name)
        if well_id is not None:
            query += " AND well_id = ?"
            params.append(well_id)

        query += " ORDER BY id"
        rows = self._conn.execute(query, params).fetchall()
        return [ExperimentRecord(**dict(r)) for r in rows]

    # ── Labware queries ───────────────────────────────────────────────────

    def get_labware(
        self,
        campaign_id: int,
        labware_key: Optional[str] = None,
    ) -> List[LabwareRecord]:
        query = (
            "SELECT id, campaign_id, labware_key, labware_type, well_id, "
            "total_volume_ul, working_volume_ul, current_volume_ul, contents "
            "FROM labware WHERE campaign_id = ?"
        )
        params: list[Any] = [campaign_id]

        if labware_key is not None:
            query += " AND labware_key = ?"
            params.append(labware_key)

        query += " ORDER BY id"
        rows = self._conn.execute(query, params).fetchall()
        return [LabwareRecord(**dict(r)) for r in rows]

    # ── Measurement queries (generic) ─────────────────────────────────────

    def get_measurements(
        self,
        experiment_id: int,
        table: str,
    ) -> List[Dict[str, Any]]:
        if table not in _VALID_MEASUREMENT_TABLES:
            raise ValueError(
                f"'{table}' is not a valid measurement table. "
                f"Valid tables: {', '.join(sorted(_VALID_MEASUREMENT_TABLES))}"
            )
        rows = self._conn.execute(
            f"SELECT * FROM {table} WHERE experiment_id = ? ORDER BY id",
            (experiment_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_measurements_by_campaign(
        self,
        campaign_id: int,
        table: str,
    ) -> List[Dict[str, Any]]:
        if table not in _VALID_MEASUREMENT_TABLES:
            raise ValueError(
                f"'{table}' is not a valid measurement table. "
                f"Valid tables: {', '.join(sorted(_VALID_MEASUREMENT_TABLES))}"
            )
        rows = self._conn.execute(
            f"SELECT m.*, e.well_id, e.labware_name "
            f"FROM {table} m "
            f"JOIN experiments e ON m.experiment_id = e.id "
            f"WHERE e.campaign_id = ? ORDER BY m.id",
            (campaign_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Lifecycle ─────────────────────────────────────────────────────────

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        if self._owns_connection:
            self._conn.close()

    def __enter__(self) -> DataReader:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
