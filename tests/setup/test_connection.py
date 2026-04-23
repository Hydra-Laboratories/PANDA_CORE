"""Unit tests for setup/test_connection.py helper functions.

These tests use MockMill / offline mode — no hardware required.
"""

from __future__ import annotations

import textwrap
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from gantry.gantry import Gantry


class TestFormatGrblSettings:
    """Verify the GRBL-settings formatter used in the connection report."""

    def test_formats_known_settings(self):
        from setup.test_connection import format_grbl_settings

        raw = {"$100": "800.000", "$110": "2000.000", "$130": "400.000"}
        lines = format_grbl_settings(raw)
        assert any("$100" in line and "800" in line for line in lines)
        assert len(lines) == 3

    def test_empty_settings(self):
        from setup.test_connection import format_grbl_settings

        assert format_grbl_settings({}) == []


class TestConnectionReport:
    """Verify the report builder produces the expected sections."""

    def test_report_contains_required_sections(self):
        from setup.test_connection import build_connection_report

        report = build_connection_report(
            port="/dev/tty.usbserial-130",
            status="<Idle|WPos:0.000,0.000,0.000|Bf:15,127>",
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
            healthy=True,
            grbl_settings={"$100": "800.000"},
            alarm=False,
        )
        assert "Connection" in report
        assert "/dev/tty.usbserial-130" in report
        assert "Healthy" in report
        assert "Idle" in report

    def test_report_shows_alarm(self):
        from setup.test_connection import build_connection_report

        report = build_connection_report(
            port="/dev/tty.usbserial-130",
            status="<Alarm|WPos:0.000,0.000,0.000>",
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
            healthy=False,
            grbl_settings={},
            alarm=True,
        )
        assert "ALARM" in report or "Alarm" in report


class TestOfflineGantryConnection:
    """Verify that the Gantry wrapper works in offline mode."""

    def test_offline_gantry_is_healthy(self):
        gantry = Gantry(config={}, offline=True)
        assert gantry.is_healthy()

    def test_offline_gantry_returns_coordinates(self):
        gantry = Gantry(config={}, offline=True)
        coords = gantry.get_coordinates()
        assert coords == {"x": 0.0, "y": 0.0, "z": 0.0}
