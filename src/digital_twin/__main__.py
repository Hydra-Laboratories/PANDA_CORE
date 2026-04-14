"""CLI entrypoint for digital twin export."""

from __future__ import annotations

import argparse

from .exporter import export_bundle_to_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export a CubOS protocol trace for the browser digital twin.",
    )
    parser.add_argument("--gantry", required=True, help="Path to gantry YAML.")
    parser.add_argument("--deck", required=True, help="Path to deck YAML.")
    parser.add_argument("--board", required=True, help="Path to board YAML.")
    parser.add_argument("--protocol", required=True, help="Path to protocol YAML.")
    parser.add_argument("--out", required=True, help="Path to output JSON bundle.")
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Export even when gantry/deck/board bounds validation fails.",
    )
    args = parser.parse_args()

    export_bundle_to_path(
        gantry_path=args.gantry,
        deck_path=args.deck,
        board_path=args.board,
        protocol_path=args.protocol,
        output_path=args.out,
        skip_validation=args.skip_validation,
    )


if __name__ == "__main__":
    main()
