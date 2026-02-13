"""Deck: runtime container for loaded labware with target resolution."""

from __future__ import annotations

from typing import Dict, Iterator, Union

from .labware.labware import Coordinate3D, Labware
from .labware.vial import Vial
from .labware.well_plate import WellPlate


class Deck:
    """
    Runtime container holding labware loaded from a deck YAML.

    Provides dict-like access to labware by key, and a resolve() method
    that translates target strings (e.g. 'plate_1.A1') into absolute
    deck coordinates.
    """

    def __init__(self, labware: Dict[str, Union[WellPlate, Vial]]) -> None:
        self._labware = dict(labware)

    @property
    def labware(self) -> Dict[str, Union[WellPlate, Vial]]:
        return self._labware

    def resolve(self, target: str) -> Coordinate3D:
        """
        Resolve a target string to an absolute deck coordinate.

        Formats:
            'plate_1.A1'  -> well A1 on plate_1
            'vial_1'      -> vial center (initial position)
            'plate_1'     -> plate initial position (A1)
        """
        if "." in target:
            labware_key, location_id = target.split(".", 1)
            return self._get_labware(labware_key).get_location(location_id)
        return self._get_labware(target).get_initial_position()

    def _get_labware(self, key: str) -> Union[WellPlate, Vial]:
        try:
            return self._labware[key]
        except KeyError:
            raise KeyError(f"No labware '{key}' on deck.") from None

    def __getitem__(self, key: str) -> Union[WellPlate, Vial]:
        return self._get_labware(key)

    def __contains__(self, key: object) -> bool:
        return key in self._labware

    def __len__(self) -> int:
        return len(self._labware)

    def __iter__(self) -> Iterator[str]:
        return iter(self._labware)

    def __repr__(self) -> str:
        keys = ", ".join(self._labware.keys())
        return f"Deck([{keys}])"
