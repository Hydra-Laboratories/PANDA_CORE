"""Run the Sterling vial scan protocol.

Usage:
    python setup/run_sterling_scan.py
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from setup.run_protocol import main as run_protocol_main

GANTRY = "configs/gantry/cub_xl_sterling.yaml"
DECK = "configs/deck/sterling_deck.yaml"
PROTOCOL = "configs/protocol/sterling_vial_scan.yaml"

if __name__ == "__main__":
    sys.argv = [sys.argv[0], GANTRY, DECK, PROTOCOL]
    run_protocol_main()
