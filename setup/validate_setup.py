"""Validate a protocol setup by loading all configs and checking bounds.

Usage:
    python setup/validate_setup.py <machine.yaml> <deck.yaml> <board.yaml> <protocol.yaml>

Example:
    python setup/validate_setup.py \\
        configs/machines/genmitsu_3018_PROver_v2.yaml \\
        configs/decks/mofcat_deck.yaml \\
        configs/boards/mofcat_board.yaml \\
        configs/protocols/protocol.sample.yaml
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.board.loader import load_board_from_yaml
from src.deck.deck import Deck
from src.deck.labware.vial import Vial
from src.deck.labware.well_plate import WellPlate
from src.deck.loader import load_deck_from_yaml
from src.machine.loader import load_machine_from_yaml
from src.protocol_engine.loader import load_protocol_from_yaml
from src.protocol_engine.setup import _default_mock_gantry
from src.validation.bounds import validate_deck_positions, validate_gantry_positions

SEPARATOR = "-" * 60


def _labware_summary(deck: Deck) -> list[str]:
    """Return one-line summaries for each piece of labware."""
    lines = []
    for key in deck:
        labware = deck[key]
        if isinstance(labware, WellPlate):
            lines.append(f"    {key}: well_plate ({len(labware.wells)} wells)")
        elif isinstance(labware, Vial):
            loc = labware.location
            lines.append(
                f"    {key}: vial at ({loc.x}, {loc.y}, {loc.z})"
            )
        else:
            lines.append(f"    {key}: {type(labware).__name__}")
    return lines


def _instrument_summary(board) -> list[str]:
    """Return one-line summaries for each instrument."""
    lines = []
    for name, instr in board.instruments.items():
        lines.append(
            f"    {name}: offset=({instr.offset_x}, {instr.offset_y}), "
            f"depth={instr.depth}"
        )
    return lines


def run_validation(
    machine_path: str,
    deck_path: str,
    board_path: str,
    protocol_path: str,
) -> str:
    """Run full setup validation and return formatted output."""
    lines: list[str] = []

    def out(text: str = "") -> None:
        lines.append(text)

    out(SEPARATOR)
    out("Protocol Setup Validation")
    out(SEPARATOR)
    out()

    # 1. Machine
    out("[1/4] Loading machine config...")
    try:
        machine = load_machine_from_yaml(machine_path)
    except Exception as exc:
        out(f"  ERROR: {exc}")
        out()
        out(SEPARATOR)
        out("RESULT: ERROR — could not load machine config")
        out(SEPARATOR)
        return "\n".join(lines)

    vol = machine.working_volume
    out(f"  OK: {machine_path}")
    out(f"  Working volume: X[{vol.x_min}, {vol.x_max}]  "
        f"Y[{vol.y_min}, {vol.y_max}]  Z[{vol.z_min}, {vol.z_max}]")
    out(f"  Homing strategy: {machine.homing_strategy}")
    out()

    # 2. Deck
    out("[2/4] Loading deck config...")
    try:
        deck = load_deck_from_yaml(deck_path)
    except Exception as exc:
        out(f"  ERROR: {exc}")
        out()
        out(SEPARATOR)
        out("RESULT: ERROR — could not load deck config")
        out(SEPARATOR)
        return "\n".join(lines)

    out(f"  OK: {deck_path}")
    out(f"  Labware ({len(deck)}):")
    for summary_line in _labware_summary(deck):
        out(summary_line)
    out()

    # 3. Board
    out("[3/4] Loading board config...")
    try:
        gantry = _default_mock_gantry()
        board = load_board_from_yaml(board_path, gantry)
    except Exception as exc:
        out(f"  ERROR: {exc}")
        out()
        out(SEPARATOR)
        out("RESULT: ERROR — could not load board config")
        out(SEPARATOR)
        return "\n".join(lines)

    out(f"  OK: {board_path}")
    out(f"  Instruments ({len(board.instruments)}):")
    for summary_line in _instrument_summary(board):
        out(summary_line)
    out()

    # 4. Protocol
    out("[4/4] Loading protocol...")
    try:
        protocol = load_protocol_from_yaml(protocol_path)
    except Exception as exc:
        out(f"  ERROR: {exc}")
        out()
        out(SEPARATOR)
        out("RESULT: ERROR — could not load protocol")
        out(SEPARATOR)
        return "\n".join(lines)

    out(f"  OK: {protocol_path}")
    out(f"  Steps: {len(protocol)}")
    for step in protocol.steps:
        out(f"    [{step.index}] {step.command_name}({', '.join(f'{k}={v!r}' for k, v in step.args.items())})")
    out()

    # 5. Deck bounds validation
    out("Validating deck positions...")
    deck_violations = validate_deck_positions(machine, deck)
    if deck_violations:
        out(f"  FAIL — {len(deck_violations)} violation(s):")
        for v in deck_violations:
            out(f"  - {v.labware_key}.{v.position_id}: "
                f"deck ({v.x}, {v.y}, {v.z}) violates {v.bound_name}={v.bound_value}")
    else:
        total_positions = sum(
            len(deck[k].wells) if isinstance(deck[k], WellPlate) else 1
            for k in deck
        )
        out(f"  OK ({total_positions} positions checked)")
    out()

    # 6. Gantry bounds validation
    out("Validating gantry positions...")
    gantry_violations = validate_gantry_positions(machine, deck, board)
    if gantry_violations:
        out(f"  FAIL — {len(gantry_violations)} violation(s):")
        for v in gantry_violations:
            out(f"  - {v.instrument_name} -> {v.labware_key}.{v.position_id}: "
                f"gantry ({v.x}, {v.y}, {v.z}) violates {v.bound_name}={v.bound_value}")
    else:
        total_positions = sum(
            len(deck[k].wells) if isinstance(deck[k], WellPlate) else 1
            for k in deck
        )
        out(f"  OK ({total_positions} positions x {len(board.instruments)} instrument(s) checked)")
    out()

    # Final result
    all_violations = deck_violations + gantry_violations
    out(SEPARATOR)
    if all_violations:
        out(f"RESULT: FAIL — {len(all_violations)} violation(s) found")
    else:
        out("RESULT: PASS — all positions within machine bounds")
        out("Protocol is ready to run.")
    out(SEPARATOR)

    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) != 5:
        print("Usage: python setup/validate_setup.py <machine.yaml> <deck.yaml> <board.yaml> <protocol.yaml>")
        print()
        print("Example:")
        print("  python setup/validate_setup.py \\")
        print("    configs/machines/genmitsu_3018_PROver_v2.yaml \\")
        print("    configs/decks/mofcat_deck.yaml \\")
        print("    configs/boards/mofcat_board.yaml \\")
        print("    configs/protocols/protocol.sample.yaml")
        sys.exit(1)

    machine_path, deck_path, board_path, protocol_path = sys.argv[1:5]
    output = run_validation(machine_path, deck_path, board_path, protocol_path)
    print(output)


if __name__ == "__main__":
    main()
