"""ASMI-specific data retrieval helpers.

Operates on the ``asmi_measurements`` SQLite table. Provides BLOB unpacking,
typed records, and convenience loaders for experiment/campaign/well access.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import List, Optional

from data.data_reader import DataReader


@dataclass(frozen=True)
class ASMIRecord:
    """Unpacked ASMI indentation measurement with metadata."""

    measurement_id: int
    experiment_id: int
    z_positions: tuple[float, ...]
    raw_forces: tuple[float, ...]
    corrected_forces: tuple[float, ...]
    baseline_avg: float
    baseline_std: float
    force_exceeded: bool
    data_points: int
    step_size_mm: Optional[float] = None
    z_target_mm: Optional[float] = None
    force_limit_n: Optional[float] = None
    timestamp: Optional[str] = None
    well_id: Optional[str] = None
    labware_name: Optional[str] = None


def _unpack_floats(blob: bytes) -> tuple[float, ...]:
    """Unpack a little-endian float64 BLOB into a tuple of floats."""
    if len(blob) == 0:
        return ()
    count = len(blob) // 8
    return struct.unpack(f"<{count}d", blob)


def unpack_asmi_measurement(
    *,
    z_positions_blob: bytes,
    raw_forces_blob: bytes,
    corrected_forces_blob: bytes,
    baseline_avg: float,
    baseline_std: float,
    force_exceeded: bool | int,
    data_points: int,
    experiment_id: int,
    measurement_id: int,
    step_size_mm: Optional[float] = None,
    z_target_mm: Optional[float] = None,
    force_limit_n: Optional[float] = None,
    timestamp: Optional[str] = None,
    well_id: Optional[str] = None,
    labware_name: Optional[str] = None,
) -> ASMIRecord:
    """Unpack raw DB fields into an :class:`ASMIRecord`."""
    return ASMIRecord(
        measurement_id=measurement_id,
        experiment_id=experiment_id,
        z_positions=_unpack_floats(z_positions_blob),
        raw_forces=_unpack_floats(raw_forces_blob),
        corrected_forces=_unpack_floats(corrected_forces_blob),
        baseline_avg=baseline_avg,
        baseline_std=baseline_std,
        force_exceeded=bool(force_exceeded),
        data_points=data_points,
        step_size_mm=step_size_mm,
        z_target_mm=z_target_mm,
        force_limit_n=force_limit_n,
        timestamp=timestamp,
        well_id=well_id,
        labware_name=labware_name,
    )


def load_asmi_by_experiment(
    reader: DataReader,
    experiment_id: int,
) -> List[ASMIRecord]:
    """Load all ASMI measurements for a given experiment."""
    rows = reader.get_measurements(experiment_id, table="asmi_measurements")
    return [
        unpack_asmi_measurement(
            z_positions_blob=row["z_positions"],
            raw_forces_blob=row["raw_forces"],
            corrected_forces_blob=row["corrected_forces"],
            baseline_avg=row["baseline_avg"],
            baseline_std=row["baseline_std"],
            force_exceeded=row["force_exceeded"],
            data_points=row["data_points"],
            step_size_mm=row.get("step_size_mm"),
            z_target_mm=row.get("z_target_mm"),
            force_limit_n=row.get("force_limit_n"),
            timestamp=row.get("timestamp"),
            experiment_id=row["experiment_id"],
            measurement_id=row["id"],
        )
        for row in rows
    ]


def load_asmi_by_campaign(
    reader: DataReader,
    campaign_id: int,
) -> List[ASMIRecord]:
    """Load all ASMI measurements for a campaign, with well/labware metadata."""
    rows = reader.get_measurements_by_campaign(
        campaign_id,
        table="asmi_measurements",
    )
    return [
        unpack_asmi_measurement(
            z_positions_blob=row["z_positions"],
            raw_forces_blob=row["raw_forces"],
            corrected_forces_blob=row["corrected_forces"],
            baseline_avg=row["baseline_avg"],
            baseline_std=row["baseline_std"],
            force_exceeded=row["force_exceeded"],
            data_points=row["data_points"],
            step_size_mm=row.get("step_size_mm"),
            z_target_mm=row.get("z_target_mm"),
            force_limit_n=row.get("force_limit_n"),
            timestamp=row.get("timestamp"),
            experiment_id=row["experiment_id"],
            measurement_id=row["id"],
            well_id=row.get("well_id"),
            labware_name=row.get("labware_name"),
        )
        for row in rows
    ]


def load_asmi_by_well(
    reader: DataReader,
    campaign_id: int,
    well_id: str,
    labware_name: Optional[str] = None,
) -> List[ASMIRecord]:
    """Load ASMI measurements for one well within a campaign."""
    target_well = well_id.upper()
    records = load_asmi_by_campaign(reader, campaign_id=campaign_id)
    return [
        record for record in records
        if record.well_id == target_well
        and (labware_name is None or record.labware_name == labware_name)
    ]
