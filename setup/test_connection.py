"""Test a gantry connection and print a compact diagnostic report.

This script is intended for first-time controller bring-up. It can also be
imported by tests for its report helpers.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from gantry import Gantry, load_gantry_from_yaml


def format_grbl_settings(grbl_settings: dict[str, str]) -> list[str]:
    """Return stable one-line strings for a GRBL settings mapping."""
    return [
        f"{setting} = {value}"
        for setting, value in sorted(
            grbl_settings.items(),
            key=lambda item: int(item[0].removeprefix("$")),
        )
    ]


def build_connection_report(
    *,
    port: str,
    status: str,
    coordinates: dict[str, float],
    healthy: bool,
    grbl_settings: dict[str, str],
    alarm: bool,
) -> str:
    """Build a human-readable connection report."""
    lines = [
        "Connection Report",
        "=================",
        f"Connection: {port}",
        f"Healthy: {'yes' if healthy else 'no'}",
        f"Status: {status}",
        (
            "Coordinates: "
            f"X={coordinates['x']:.3f}, "
            f"Y={coordinates['y']:.3f}, "
            f"Z={coordinates['z']:.3f}"
        ),
        f"Alarm: {'ALARM' if alarm else 'clear'}",
        "GRBL Settings:",
    ]

    formatted_settings = format_grbl_settings(grbl_settings)
    if formatted_settings:
        lines.extend(f"  {line}" for line in formatted_settings)
    else:
        lines.append("  (none reported)")

    return "\n".join(lines)


def _load_gantry_config(gantry_name: str) -> dict[str, Any]:
    """Load a gantry YAML config by name from configs/gantry/."""
    config_path = project_root / "configs" / "gantry" / f"{gantry_name}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Gantry config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _collect_connection_info(gantry_name: str, port: str | None) -> str:
    """Connect to the gantry and return a formatted diagnostic report."""
    config = _load_gantry_config(gantry_name)
    gantry_config = load_gantry_from_yaml(str(project_root / "configs" / "gantry" / f"{gantry_name}.yaml"))
    report_port = port or config.get("serial_port", "<auto-scan>")
    gantry = Gantry(config=config)

    if port:
        # The low-level driver keeps the selected port on the Mill instance.
        assert gantry._mill is not None
        gantry._mill.port = port

    grbl_settings: dict[str, str] = {}
    status = "Unknown"
    coordinates = {"x": 0.0, "y": 0.0, "z": 0.0}
    healthy = False
    alarm = False

    try:
        gantry.connect()
        healthy = gantry.is_healthy()
        coordinates = gantry.get_coordinates()
        status = gantry.get_status()
        alarm = "alarm" in status.lower()
        if gantry._mill is not None:
            grbl_settings = gantry._mill.grbl_settings()
            report_port = getattr(gantry._mill.ser_mill, "port", report_port)
    finally:
        gantry.disconnect()

    return build_connection_report(
        port=report_port,
        status=status,
        coordinates=coordinates,
        healthy=healthy,
        grbl_settings=grbl_settings,
        alarm=alarm,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gantry",
        default="cub_xl",
        help="Gantry config name in configs/gantry/ without the .yaml suffix.",
    )
    parser.add_argument(
        "--port",
        default=None,
        help="Optional serial port override, for example /dev/tty.usbserial-130.",
    )
    args = parser.parse_args()

    try:
        print(_collect_connection_info(args.gantry, args.port))
    except Exception as exc:
        print(f"Connection test failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
