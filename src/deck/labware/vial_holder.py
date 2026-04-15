from __future__ import annotations

from typing import Dict

from pydantic import ConfigDict, Field, PrivateAttr, field_validator, model_validator

from .holder import _SEAT_Z_TOLERANCE_MM, HolderLabware
from .labware import Coordinate3D, Labware
from .vial import Vial


class VialHolder(HolderLabware):
    """Holder for a fixed-count set of vial slots."""

    model_config = ConfigDict(
        extra="forbid", protected_namespaces=(), validate_assignment=True
    )

    model_name: str = "9VialHolder20mL_TightFit"
    length_mm: float = 36.2
    width_mm: float = 300.2
    height_mm: float = 35.1
    labware_support_height_mm: float = 35.1
    labware_seat_height_from_bottom_mm: float = 18.0
    slot_count: int = Field(default=9, description="Maximum number of supported vial slots.")
    vials: Dict[str, Vial] = Field(
        default_factory=dict,
        description="Vials held by this holder, keyed by vial name.",
    )

    # Tracks the set of vials this holder owned at the end of the most
    # recent successful validator run, so that reassignment to `vials` can
    # clear `.holder` back-references on any vials that were removed.
    _prev_vials: Dict[str, Vial] = PrivateAttr(default_factory=dict)

    @field_validator("slot_count")
    def _validate_slot_count(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("slot_count must be positive.")
        return value

    @model_validator(mode="after")
    def _validate_holder_state(self) -> "VialHolder":
        if len(self.slots) > self.slot_count:
            raise ValueError("slots count must be <= slot_count.")
        if len(self.vials) > self.slot_count:
            raise ValueError("vials count must be <= slot_count.")

        # VialHolder narrows labware_seat_height_from_bottom_mm to a
        # non-optional float at the field level, so it is always set here.
        expected_z = self.location.z + self.labware_seat_height_from_bottom_mm

        # Two passes: validate every vial fully before any mutation, so a
        # failure at vial #N doesn't leave vials #1..N-1 with stale
        # `.holder` back-references pointing at a holder that got rejected.
        for vial_name, vial in self.vials.items():
            if vial.name != vial_name:
                raise ValueError(
                    f"VialHolder.vials key '{vial_name}' must match vial.name '{vial.name}'."
                )
            if vial.holder is not None and vial.holder is not self:
                raise ValueError(
                    f"vial '{vial_name}' is already held by another VialHolder "
                    f"('{vial.holder.name}'); each vial may belong to at most one holder."
                )
            if abs(vial.location.z - expected_z) > _SEAT_Z_TOLERANCE_MM:
                raise ValueError(
                    f"vial '{vial_name}' z={vial.location.z} is inconsistent with "
                    f"VialHolder '{self.name}' seat z={expected_z} "
                    f"(holder.location.z + labware_seat_height_from_bottom_mm)."
                )

        # Clear back-references on vials that were previously owned but are
        # no longer in `self.vials` — otherwise `old_vial.holder` would
        # silently dangle, pointing at this holder even though we no longer
        # list it.
        current_identities = {id(v) for v in self.vials.values()}
        for old_vial in self._prev_vials.values():
            if id(old_vial) not in current_identities and old_vial.holder is self:
                old_vial.holder = None

        # Commit: now wire up back-references and snapshot for the next pass.
        for vial in self.vials.values():
            vial.holder = self
        self._prev_vials = dict(self.vials)
        return self

    def _iter_contained_labware(self) -> Dict[str, Labware]:
        return dict(self.vials)

    def get_vial_slot(self, slot_id: str) -> Coordinate3D:
        return self.get_slot(slot_id)

    def get_vial_top_z(self, vial_name: str) -> float:
        """Return the absolute deck Z of the top (rim) of the named vial.

        Raises:
            KeyError: if ``vial_name`` is not held by this holder. The message
                lists the vial names that are present.
        """
        try:
            vial = self.vials[vial_name]
        except KeyError as exc:
            raise KeyError(
                f"VialHolder '{self.name}' does not contain vial '{vial_name}'. "
                f"Known vials: {sorted(self.vials)}."
            ) from exc
        return vial.get_top_center().z
