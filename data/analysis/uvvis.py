"""UV-Vis specific data retrieval and analysis helpers.

Operates on the uvvis_measurements SQLite table. Provides BLOB unpacking,
spectrum loading, and common spectral analysis functions.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import List, Optional, Tuple

from data.data_reader import DataReader


@dataclass(frozen=True)
class UVVisRecord:
    """Unpacked UV-Vis spectrum with metadata."""

    measurement_id: int
    experiment_id: int
    wavelengths: tuple[float, ...]
    intensities: tuple[float, ...]
    integration_time_s: float
    well_id: Optional[str] = None
    labware_name: Optional[str] = None


# ── BLOB unpacking ────────────────────────────────────────────────────────────


def _unpack_floats(blob: bytes) -> tuple[float, ...]:
    """Unpack a little-endian float64 BLOB into a tuple of floats."""
    if len(blob) == 0:
        return ()
    count = len(blob) // 8
    return struct.unpack(f"<{count}d", blob)


def unpack_spectrum(
    wavelengths_blob: bytes,
    intensities_blob: bytes,
    integration_time_s: float,
    experiment_id: int,
    measurement_id: int,
    well_id: Optional[str] = None,
    labware_name: Optional[str] = None,
) -> UVVisRecord:
    """Unpack raw BLOB data from the database into a UVVisRecord."""
    return UVVisRecord(
        measurement_id=measurement_id,
        experiment_id=experiment_id,
        wavelengths=_unpack_floats(wavelengths_blob),
        intensities=_unpack_floats(intensities_blob),
        integration_time_s=integration_time_s,
        well_id=well_id,
        labware_name=labware_name,
    )


# ── Load from DB ──────────────────────────────────────────────────────────────


def load_uvvis_by_experiment(
    reader: DataReader,
    experiment_id: int,
) -> List[UVVisRecord]:
    """Load all UV-Vis spectra for a given experiment."""
    rows = reader.get_measurements(experiment_id, table="uvvis_measurements")
    return [
        unpack_spectrum(
            wavelengths_blob=row["wavelengths"],
            intensities_blob=row["intensities"],
            integration_time_s=row["integration_time_s"],
            experiment_id=row["experiment_id"],
            measurement_id=row["id"],
        )
        for row in rows
    ]


def load_uvvis_by_campaign(
    reader: DataReader,
    campaign_id: int,
) -> List[UVVisRecord]:
    """Load all UV-Vis spectra for a campaign, with well/labware metadata."""
    rows = reader.get_measurements_by_campaign(
        campaign_id, table="uvvis_measurements",
    )
    return [
        unpack_spectrum(
            wavelengths_blob=row["wavelengths"],
            intensities_blob=row["intensities"],
            integration_time_s=row["integration_time_s"],
            experiment_id=row["experiment_id"],
            measurement_id=row["id"],
            well_id=row.get("well_id"),
            labware_name=row.get("labware_name"),
        )
        for row in rows
    ]


# ── Analysis helpers ──────────────────────────────────────────────────────────


def peak_wavelength(record: UVVisRecord) -> Tuple[float, float]:
    """Return (wavelength, intensity) at the maximum intensity.

    Raises:
        ValueError: If the spectrum is empty.
    """
    if len(record.intensities) == 0:
        raise ValueError("Cannot find peak of an empty spectrum")
    max_idx = max(range(len(record.intensities)), key=record.intensities.__getitem__)
    return record.wavelengths[max_idx], record.intensities[max_idx]


def absorbance(
    sample: UVVisRecord,
    reference: UVVisRecord,
    dark: Optional[UVVisRecord] = None,
) -> UVVisRecord:
    """Compute absorbance: A = -log10((sample - dark) / (reference - dark)).

    If *dark* is not provided, it is treated as zero.

    Returns:
        A new UVVisRecord with absorbance values in the intensities field.

    Raises:
        ValueError: If sample and reference have different lengths.
    """
    if len(sample.intensities) != len(reference.intensities):
        raise ValueError(
            f"Sample and reference must have the same length. "
            f"Got {len(sample.intensities)} and {len(reference.intensities)}."
        )
    if dark is not None and len(dark.intensities) != len(sample.intensities):
        raise ValueError(
            f"Dark spectrum must have the same length as sample. "
            f"Got {len(dark.intensities)} and {len(sample.intensities)}."
        )

    dark_values = dark.intensities if dark is not None else (0.0,) * len(sample.intensities)

    abs_values: list[float] = []
    for s, r, d in zip(sample.intensities, reference.intensities, dark_values):
        ratio = (s - d) / (r - d)
        ratio = max(ratio, 1e-10)  # clamp to avoid log10(0)
        abs_values.append(-math.log10(ratio))

    return UVVisRecord(
        measurement_id=sample.measurement_id,
        experiment_id=sample.experiment_id,
        wavelengths=sample.wavelengths,
        intensities=tuple(abs_values),
        integration_time_s=sample.integration_time_s,
        well_id=sample.well_id,
        labware_name=sample.labware_name,
    )


def slice_wavelength_range(
    record: UVVisRecord,
    wl_min: float,
    wl_max: float,
) -> UVVisRecord:
    """Return a new UVVisRecord containing only wavelengths in [wl_min, wl_max]."""
    indices = [
        i for i, wl in enumerate(record.wavelengths)
        if wl_min <= wl <= wl_max
    ]
    return UVVisRecord(
        measurement_id=record.measurement_id,
        experiment_id=record.experiment_id,
        wavelengths=tuple(record.wavelengths[i] for i in indices),
        intensities=tuple(record.intensities[i] for i in indices),
        integration_time_s=record.integration_time_s,
        well_id=record.well_id,
        labware_name=record.labware_name,
    )
