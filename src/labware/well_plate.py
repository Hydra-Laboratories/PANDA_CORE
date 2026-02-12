from __future__ import annotations

from typing import Dict, List

from pydantic import ConfigDict, Field, field_validator, model_validator

from .labware import Labware, Coordinate3D


class WellPlate(Labware):
    """
    Labware representing a multi-well plate (e.g. SBS 96-well).

    Coordinates for each well are expressed as absolute deck coordinates.
    """

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    name: str = Field(..., description="Unique well plate name.")
    model_name: str = Field(..., description="Well plate model identifier.")
    length_mm: float = Field(..., description="Overall plate length in millimeters.")
    width_mm: float = Field(..., description="Overall plate width in millimeters.")
    height_mm: float = Field(..., description="Overall plate height in millimeters.")
    rows: int = Field(..., description="Number of well rows (e.g. 8 for 96-well).")
    columns: int = Field(..., description="Number of well columns (e.g. 12 for 96-well).")
    wells: Dict[str, Coordinate3D] = Field(
        ...,
        description="Mapping from well ID (e.g. 'A1') to absolute XYZ centers.",
    )
    capacity_ul: float = Field(..., description="Well capacity in microliters.")
    working_volume_ul: float = Field(..., description="Working volume per well in microliters.")

    @field_validator("name", "model_name")
    def _validate_non_empty_text(cls, value: str) -> str:
        return Labware.validate_name(value)

    @field_validator("capacity_ul", "working_volume_ul")
    def _validate_positive_volume(cls, value: float, info):  # type: ignore[override]
        if value <= 0:
            raise ValueError(f"{info.field_name} must be positive.")
        return value

    @model_validator(mode="after")
    def _validate_working_le_capacity(self) -> "WellPlate":
        if self.working_volume_ul > self.capacity_ul:
            raise ValueError("working_volume_ul must be <= capacity_ul.")
        return self

    @field_validator("length_mm", "width_mm", "height_mm")
    def _validate_positive_dimension(cls, value: float, info):  # type: ignore[override]
        if value <= 0:
            raise ValueError(f"{info.field_name} must be positive.")
        return value

    @field_validator("rows", "columns")
    def _validate_positive_grid_size(cls, value: int, info):  # type: ignore[override]
        if value <= 0:
            raise ValueError(f"{info.field_name} must be a positive integer.")
        return value

    @model_validator(mode="before")
    def _validate_wells(cls, data):
        wells: Dict[str, Coordinate3D] = data.get("wells") or {}
        if not wells:
            raise ValueError("WellPlate must define at least one well.")

        # Ensure the anchor well A1 exists so we can use it as the initial position.
        if "A1" not in wells:
            raise ValueError("WellPlate must define an 'A1' well for anchoring.")

        return data

    def get_location(self, location_id: str | None = None) -> Coordinate3D:
        if location_id is None:
            raise KeyError("WellPlate location_id is required, e.g. 'A1'.")
        return self.get_well_center(location_id)

    def get_well_center(self, well_id: str) -> Coordinate3D:
        """
        Convenience wrapper to fetch a well center by ID.
        """
        try:
            return self.wells[well_id]
        except KeyError as exc:
            raise KeyError(f"Unknown well ID '{well_id}'") from exc

    def get_initial_position(self) -> Coordinate3D:
        """
        Initial position for a well plate: the A1 well.
        """
        # By construction, 'A1' must exist in `wells`.
        return self.get_well_center("A1")


def generate_wells_from_offsets(
    *,
    row_labels: List[str],
    column_indices: List[int],
    a1_center: Coordinate3D,
    x_offset_mm: float,
    y_offset_mm: float,
    rounding_decimals: int = 3,
) -> Dict[str, Coordinate3D]:
    """
    Generate a complete well-position mapping from an A1 anchor and per-step offsets.

    This mirrors the classic well-to-XY logic:
      - row index is derived from row_labels (e.g. ['A','B',...])
      - column index is derived from column_indices (e.g. [1,2,...,12])
      - each step in X/Y applies the configured offsets
    """
    wells: Dict[str, Coordinate3D] = {}

    for row_idx, row_label in enumerate(row_labels):
        for col_idx, col_num in enumerate(column_indices):
            well_id = f"{row_label}{col_num}"

            x = a1_center.x + x_offset_mm * col_idx
            y = a1_center.y + y_offset_mm * row_idx
            z = a1_center.z

            wells[well_id] = Coordinate3D(
                x=round(x, rounding_decimals),
                y=round(y, rounding_decimals),
                z=round(z, rounding_decimals),
            )

    return wells

