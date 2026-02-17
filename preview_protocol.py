"""Preview protocol move coordinates without touching hardware."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.protocol_engine.preview import format_move_preview, preview_protocol_moves


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parent
    default_deck = repo_root / "configs" / "deck.sample.yaml"
    default_protocol = repo_root / "experiments" / "sample_three_well_protocol.yaml"

    parser = argparse.ArgumentParser(
        description=(
            "Mock-run protocol preview: resolve target wells to exact XYZ coordinates "
            "without sending commands to CNC hardware."
        )
    )
    parser.add_argument(
        "--deck",
        type=Path,
        default=default_deck,
        help=f"Path to deck YAML (default: {default_deck})",
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=default_protocol,
        help=f"Path to protocol YAML (default: {default_protocol})",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    preview_steps = preview_protocol_moves(
        deck_path=args.deck,
        protocol_path=args.protocol,
    )
    print(format_move_preview(preview_steps))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
