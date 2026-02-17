"""Load, validate, and run a protocol end-to-end.

Usage:
    python setup/run_protocol.py <machine.yaml> <deck.yaml> <board.yaml> <protocol.yaml>

Example:
    python setup/run_protocol.py \\
        configs/machines/genmitsu_3018_PROver_v2.yaml \\
        configs/decks/mofcat_deck.yaml \\
        configs/boards/mofcat_board.yaml \\
        configs/protocols/protocol.sample.yaml

Steps:
    1. Load machine config and create gantry
    2. Load all configs and validate bounds (via setup_protocol)
    3. Connect to gantry and home
    4. Run the protocol
    5. Disconnect
"""

import sys
from pathlib import Path

import yaml

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from setup.validate_setup import run_validation
from src.gantry import Gantry
from src.protocol_engine.setup import setup_protocol
from src.validation.errors import SetupValidationError

SEPARATOR = "-" * 60


def main() -> None:
    if len(sys.argv) != 5:
        print("Usage: python setup/run_protocol.py <machine.yaml> <deck.yaml> <board.yaml> <protocol.yaml>")
        print()
        print("Example:")
        print("  python setup/run_protocol.py \\")
        print("    configs/machines/genmitsu_3018_PROver_v2.yaml \\")
        print("    configs/decks/mofcat_deck.yaml \\")
        print("    configs/boards/mofcat_board.yaml \\")
        print("    configs/protocols/protocol.sample.yaml")
        sys.exit(1)

    machine_path, deck_path, board_path, protocol_path = sys.argv[1:5]

    # Phase 1: Validate (offline, before touching hardware)
    print(run_validation(machine_path, deck_path, board_path, protocol_path))

    # Phase 2: Load machine config for gantry construction
    print()
    print(SEPARATOR)
    print("Setting up for execution...")
    print(SEPARATOR)
    print()

    try:
        with open(machine_path) as f:
            raw_config = yaml.safe_load(f)
    except Exception as exc:
        print(f"ERROR: Could not load machine config: {exc}")
        sys.exit(1)

    gantry = Gantry(config=raw_config)

    # Phase 3: Run setup_protocol with real gantry (re-loads + validates)
    try:
        protocol, context = setup_protocol(
            machine_path, deck_path, board_path, protocol_path, gantry=gantry,
        )
    except SetupValidationError as exc:
        print(f"Validation failed:\n{exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Setup failed: {exc}")
        sys.exit(1)

    print(f"Protocol loaded: {len(protocol)} steps")
    print()

    # Phase 4: Connect + home + run
    try:
        print("Connecting to gantry...")
        gantry.connect()

        if not gantry.is_healthy():
            print("WARNING: Gantry health check failed, attempting to proceed...")

        print("Homing...")
        gantry.home()
        print("Homing complete.")
        print()

        print(SEPARATOR)
        print("Running protocol...")
        print(SEPARATOR)
        print()

        results = protocol.run(context)

        print()
        print(SEPARATOR)
        print(f"Protocol complete — {len(results)} steps executed.")
        print(SEPARATOR)

    except KeyboardInterrupt:
        print("\nAborted by user.")
    except Exception as exc:
        print(f"\nERROR during execution: {exc}")
    finally:
        print("Disconnecting...")
        gantry.disconnect()
        print("Done.")


if __name__ == "__main__":
    main()
