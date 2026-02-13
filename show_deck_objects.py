from __future__ import annotations

from pathlib import Path
from pprint import pprint

from src.deck import DeckLoaderError, load_deck_from_yaml_safe


def main() -> None:
    deck_path = Path("configs/deck.sample.yaml")
    try:
        deck = load_deck_from_yaml_safe(deck_path)
    except DeckLoaderError as exc:
        print(str(exc))
        return

    print(f"Loaded {len(deck)} labware objects from {deck_path}")
    for key, obj in deck.labware.items():
        print(f"\n[{key}] -> {obj.__class__.__name__}")
        pprint(obj.model_dump())


if __name__ == "__main__":
    main()

