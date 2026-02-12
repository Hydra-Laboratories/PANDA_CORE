from __future__ import annotations

from pathlib import Path
from pprint import pprint

from src.deck import DeckLoaderError, load_labware_from_deck_yaml_safe


def main() -> None:
    deck_path = Path("configs/deck.sample.yaml")
    try:
        labware_map = load_labware_from_deck_yaml_safe(deck_path)
    except DeckLoaderError as exc:
        print(str(exc))
        return

    print(f"Loaded {len(labware_map)} labware objects from {deck_path}")
    for key, obj in labware_map.items():
        print(f"\n[{key}] -> {obj.__class__.__name__}")
        pprint(obj.model_dump())


if __name__ == "__main__":
    main()

