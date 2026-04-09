from __future__ import annotations

from typing import Dict

from pydantic import ConfigDict, Field, field_validator, model_validator

from .labware import BoundingBoxGeometry, Coordinate3D, Labware


class TipRack(Labware):
    """Labware representing a tip rack with exact pickup locations."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    name: str = Field(..., description="Unique tip rack name.")
    model_name: str = Field("", description="Tip rack model identifier.")
    rows: int = Field(..., gt=0, le=26, description="Number of rack rows.")
    columns: int = Field(..., gt=0, description="Number of rack columns.")
    z_pickup: float = Field(..., description="Default pickup Z for each tip.")
    z_drop: float | None = Field(default=None, description="Optional discard/park Z for tips.")
    tips: Dict[str, Coordinate3D] = Field(
        ...,
        description="Mapping from tip ID (e.g. 'A1') to absolute pickup coordinates.",
    )

    @field_validator("name")
    def _validate_non_empty_text(cls, value: str) -> str:
        return Labware.validate_name(value)

    @field_validator("z_pickup", "z_drop")
    def _validate_positive_z(cls, value: float | None, info):  # type: ignore[override]
        if value is not None and value <= 0:
            raise ValueError(f"{info.field_name} must be positive.")
        return value

    @model_validator(mode="before")
    def _validate_tips_present(cls, data):
        tips: Dict[str, Coordinate3D] = data.get("tips") or {}
        if not tips:
            raise ValueError("TipRack must define at least one tip.")
        if "A1" not in tips:
            raise ValueError("TipRack must define an 'A1' tip for anchoring.")
        return data

    @model_validator(mode="after")
    def _validate_tip_count(self) -> "TipRack":
        expected_tip_count = self.rows * self.columns
        if len(self.tips) != expected_tip_count:
            raise ValueError(
                f"TipRack tips count must equal rows*columns ({expected_tip_count}), got {len(self.tips)}."
            )
        xs = [coord.x for coord in self.tips.values()]
        ys = [coord.y for coord in self.tips.values()]
        derived_height = abs(self.z_pickup - self.z_drop) if self.z_drop is not None else None
        self.geometry = BoundingBoxGeometry(
            length_mm=round(max(xs) - min(xs), 3) if len(xs) > 1 else None,
            width_mm=round(max(ys) - min(ys), 3) if len(ys) > 1 else None,
            height_mm=round(derived_height, 3) if derived_height is not None else None,
        )
        return self

    def get_location(self, location_id: str | None = None) -> Coordinate3D:
        if location_id is None:
            raise KeyError("TipRack location_id is required, e.g. 'A1'.")
        try:
            return self.tips[location_id]
        except KeyError as exc:
            raise KeyError(f"Unknown tip ID '{location_id}'") from exc

    def get_tip_location(self, tip_id: str) -> Coordinate3D:
        return self.get_location(tip_id)

    def get_initial_position(self) -> Coordinate3D:
        return self.get_tip_location("A1")

    def iter_positions(self) -> dict[str, Coordinate3D]:
        return dict(self.tips)
