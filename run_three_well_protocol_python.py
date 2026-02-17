"""Run the three-well protocol defined directly in Python."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import yaml

from src.deck import load_deck_from_yaml_safe
from src.gantry import Gantry
from src.protocol_engine.board import Board
from src.protocol_engine.preview import MovePreviewStep, format_move_preview
from src.protocol_engine.programmatic_three_well import build_three_well_protocol
from src.protocol_engine.protocol import ProtocolContext


class MountedInstrument:
    """Minimal mounted tool model used by Board for offset math."""

    def __init__(self, name: str, offset_x: float, offset_y: float, depth: float) -> None:
        self.name = name
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.depth = depth


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError("Config file must be a YAML mapping/object.")
    return loaded


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parent
    default_deck = repo_root / "configs" / "deck.sample.yaml"
    default_gantry = repo_root / "configs" / "genmitsu_3018_PROver_v2.yaml"

    parser = argparse.ArgumentParser(
        description=(
            "Run the 3-well protocol defined directly in Python "
            "(A1 -> C8 -> B1), with preview and explicit confirmation."
        )
    )
    parser.add_argument("--deck", type=Path, default=default_deck, help="Deck YAML path")
    parser.add_argument(
        "--gantry-config",
        type=Path,
        default=default_gantry,
        help="Gantry config YAML path",
    )
    parser.add_argument("--instrument", default="pipette", help="Instrument name")
    parser.add_argument("--offset-x", type=float, default=0.0, help="Instrument X offset")
    parser.add_argument("--offset-y", type=float, default=0.0, help="Instrument Y offset")
    parser.add_argument("--depth", type=float, default=0.0, help="Instrument depth offset")
    parser.add_argument("--skip-home", action="store_true", help="Skip homing before run")
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip gantry health check after connect",
    )
    parser.add_argument("--yes", action="store_true", help="Skip RUN confirmation prompt")
    return parser


def _preview(protocol, deck) -> str:
    preview_rows: list[MovePreviewStep] = []
    for step in protocol.steps:
        target = str(step.args["position"])
        instrument = str(step.args["instrument"])
        coord = deck.resolve(target)
        preview_rows.append(
            MovePreviewStep(
                step_index=step.index,
                instrument=instrument,
                target=target,
                coordinate=coord,
            )
        )
    return format_move_preview(preview_rows)


def _confirm_or_exit(force_yes: bool) -> bool:
    if force_yes:
        return True
    response = input("Type RUN to execute this Python-defined protocol on hardware: ").strip()
    return response == "RUN"


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    deck = load_deck_from_yaml_safe(args.deck)
    protocol = build_three_well_protocol(instrument=args.instrument)

    print("---- Coordinate preview (from Python protocol + deck) ----")
    print(_preview(protocol, deck))
    print()
    print("---- Instrument mount offsets used for execution ----")
    print(
        f"Instrument={args.instrument} | "
        f"offset_x={args.offset_x:.3f}, offset_y={args.offset_y:.3f}, depth={args.depth:.3f}"
    )
    print()
    if not _confirm_or_exit(args.yes):
        print("Cancelled. No hardware commands were sent.")
        return 0

    gantry_config = _load_yaml_mapping(args.gantry_config)
    gantry = Gantry(config=gantry_config)
    mounted = MountedInstrument(
        name=args.instrument,
        offset_x=args.offset_x,
        offset_y=args.offset_y,
        depth=args.depth,
    )
    board = Board(gantry=gantry, instruments={args.instrument: mounted})
    context = ProtocolContext(
        board=board,
        deck=deck,
        logger=logging.getLogger("protocol.python_three_well"),
    )

    gantry.connect()
    try:
        if not args.skip_health_check and not gantry.is_healthy():
            raise RuntimeError("Gantry health check failed after connect.")
        if not args.skip_home:
            gantry.home()
        results = protocol.run(context)
    finally:
        gantry.disconnect()

    print(f"Protocol complete. Executed {len(results)} step(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
