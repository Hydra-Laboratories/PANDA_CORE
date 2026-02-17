"""Run a protocol on real gantry hardware after explicit confirmation."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.protocol_engine.hardware_run import HardwareRunOptions, run_protocol_on_gantry
from src.protocol_engine.preview import format_move_preview, preview_protocol_moves


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parent
    default_deck = repo_root / "configs" / "deck.sample.yaml"
    default_protocol = repo_root / "experiments" / "sample_three_well_protocol.yaml"
    default_gantry = repo_root / "configs" / "genmitsu_3018_PROver_v2.yaml"

    parser = argparse.ArgumentParser(
        description=(
            "Execute a protocol on hardware. Prints a coordinate preview first, "
            "then requires explicit confirmation before running."
        )
    )
    parser.add_argument("--deck", type=Path, default=default_deck, help="Deck YAML path")
    parser.add_argument(
        "--protocol", type=Path, default=default_protocol, help="Protocol YAML path"
    )
    parser.add_argument(
        "--gantry-config",
        type=Path,
        default=default_gantry,
        help="Gantry config YAML path",
    )
    parser.add_argument(
        "--instrument",
        default="pipette",
        help="Instrument name used by move steps (default: pipette)",
    )
    parser.add_argument("--offset-x", type=float, default=0.0, help="Instrument X offset")
    parser.add_argument("--offset-y", type=float, default=0.0, help="Instrument Y offset")
    parser.add_argument("--depth", type=float, default=0.0, help="Instrument Z depth offset")
    parser.add_argument(
        "--skip-home",
        action="store_true",
        help="Skip gantry homing before protocol run",
    )
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip gantry health check after connect",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive confirmation prompt",
    )
    return parser


def _confirm_or_exit(force_yes: bool) -> bool:
    if force_yes:
        return True
    response = input("Type RUN to execute this protocol on hardware: ").strip()
    return response == "RUN"


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    print("---- Coordinate preview (from deck + protocol) ----")
    preview_steps = preview_protocol_moves(args.deck, args.protocol)
    print(format_move_preview(preview_steps))
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

    options = HardwareRunOptions(
        deck_path=args.deck,
        protocol_path=args.protocol,
        gantry_config_path=args.gantry_config,
        instrument_name=args.instrument,
        instrument_offset_x=args.offset_x,
        instrument_offset_y=args.offset_y,
        instrument_depth=args.depth,
        home_before_run=not args.skip_home,
        require_healthy=not args.skip_health_check,
    )
    results = run_protocol_on_gantry(options)
    print(f"Protocol complete. Executed {len(results)} step(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
