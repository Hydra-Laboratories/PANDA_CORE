"""Load, validate, and run a protocol end-to-end.

Usage:
    python setup/run_protocol.py <gantry.yaml> <deck.yaml> <board.yaml> <protocol.yaml> [--db <path>]

Example:
    python setup/run_protocol.py \\
        configs/gantry/genmitsu_3018_PROver_v2.yaml \\
        configs/deck/mofcat_deck.yaml \\
        configs/board/mofcat_board.yaml \\
        configs/protocol/protocol.sample.yaml \\
        --db data/databases/panda_data.db

Steps:
    1. Validate all configs and bounds (offline, no hardware)
    2. Load gantry config and create gantry
    3. Connect to gantry
    4. Run the protocol (with optional SQLite data tracking)
    5. Disconnect
"""

import sys
import traceback
from pathlib import Path

import yaml

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from setup.validate_setup import run_validation
from gantry import Gantry
from protocol_engine.setup import setup_protocol
from validation.errors import SetupValidationError

SEPARATOR = "-" * 60
DEFAULT_DB_PATH = "data/databases/panda_data.db"


def _parse_args():
    """Parse CLI arguments: 4 positional YAML paths + optional --db flag."""
    args = sys.argv[1:]
    db_path = DEFAULT_DB_PATH

    if "--db" in args:
        idx = args.index("--db")
        if idx + 1 >= len(args):
            print("ERROR: --db requires a path argument")
            sys.exit(1)
        db_path = args[idx + 1]
        args = args[:idx] + args[idx + 2:]
    elif "--no-db" in args:
        db_path = None
        args.remove("--no-db")

    if len(args) != 4:
        print("Usage: python setup/run_protocol.py <gantry.yaml> <deck.yaml> <board.yaml> <protocol.yaml> [--db <path>] [--no-db]")
        sys.exit(1)

    return args[0], args[1], args[2], args[3], db_path


def main() -> None:
    gantry_path, deck_path, board_path, protocol_path, db_path = _parse_args()

    # Phase 1: Validate (offline, before touching hardware)
    result = run_validation(gantry_path, deck_path, board_path, protocol_path)
    print(result.output)
    if not result.passed:
        print("\nAborting — validation did not pass.")
        sys.exit(1)

    # Phase 2: Load gantry config for hardware construction
    print()
    print(SEPARATOR)
    print("Setting up for execution...")
    print(SEPARATOR)
    print()

    try:
        with open(gantry_path) as f:
            raw_config = yaml.safe_load(f)
    except Exception as exc:
        print(f"ERROR: Could not load gantry config: {exc}")
        sys.exit(1)

    gantry = Gantry(config=raw_config)

    # Phase 3: Run setup_protocol with real gantry (re-loads + validates)
    try:
        protocol, context = setup_protocol(
            gantry_path, deck_path, board_path, protocol_path,
            gantry=gantry, db_path=db_path,
        )
    except SetupValidationError as exc:
        print(f"Validation failed:\n{exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Setup failed: {exc}")
        sys.exit(1)

    print(f"Protocol loaded: {len(protocol)} steps")
    if context.campaign_id is not None:
        print(f"Campaign ID: {context.campaign_id} (tracking to {db_path})")
    print()

    # Phase 4: Connect + run
    try:
        print("Connecting to gantry...")
        gantry.connect()

        if not gantry.is_healthy():
            print("ERROR: Gantry health check failed. Aborting.")
            gantry.disconnect()
            sys.exit(1)

        print(SEPARATOR)
        print("Running protocol...")
        print(SEPARATOR)
        print()

        results = protocol.run(context)

        print()
        print(SEPARATOR)
        print(f"Protocol complete — {len(results)} steps executed.")
        if context.campaign_id is not None:
            print(f"Data stored in campaign {context.campaign_id}")
        print(SEPARATOR)

    except KeyboardInterrupt:
        print("\nAborted by user.")
        sys.exit(130)
    except Exception as exc:
        print(f"\nERROR during execution: {exc}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        if context.data_store is not None:
            context.data_store.close()
        print("Disconnecting...")
        gantry.disconnect()
        print("Done.")


if __name__ == "__main__":
    main()
