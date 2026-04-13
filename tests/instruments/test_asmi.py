"""Tests for the ASMI instrument driver (offline mode)."""

import unittest

from instruments.asmi.driver import ASMI
from instruments.asmi.models import ASMIStatus, MeasurementResult


class TestASMIOffline(unittest.TestCase):
    """Verify ASMI(offline=True) behaves correctly without hardware."""

    def setUp(self):
        self.asmi = ASMI(offline=True, default_force=1.5)

    def test_connect_disconnect_are_noops(self):
        self.asmi.connect()
        self.asmi.disconnect()

    def test_health_check_returns_true(self):
        self.assertTrue(self.asmi.health_check())

    def test_is_connected_returns_true(self):
        self.assertTrue(self.asmi.is_connected())

    def test_measure_returns_default_force(self):
        result = self.asmi.measure(n_samples=3)
        self.assertIsInstance(result, MeasurementResult)
        self.assertEqual(result.mean_n, 1.5)
        self.assertEqual(result.std_n, 0.0)
        self.assertEqual(len(result.readings), 3)

    def test_get_force_reading_returns_default(self):
        self.assertAlmostEqual(self.asmi.get_force_reading(), 1.5)

    def test_get_baseline_force_returns_default(self):
        avg, std = self.asmi.get_baseline_force(samples=5)
        self.assertAlmostEqual(avg, 1.5)
        self.assertAlmostEqual(std, 0.0)

    def test_get_status_offline(self):
        status = self.asmi.get_status()
        self.assertIsInstance(status, ASMIStatus)
        self.assertTrue(status.is_connected)
        self.assertEqual(status.sensor_description, "OfflineSensor")

    def test_indentation_offline_returns_data(self):
        """Offline indentation should return synthetic measurements quickly."""
        from gantry.gantry import Gantry
        gantry = Gantry(offline=True)
        # Use small range for fast test
        self.asmi._z_target = -12.0
        self.asmi._indentation_start_z = -10.0
        self.asmi._step_size = 0.1

        result = self.asmi.indentation(gantry)

        self.assertIn("measurements", result)
        self.assertIn("baseline_avg", result)
        self.assertIn("data_points", result)
        self.assertEqual(result["data_points"], len(result["measurements"]))
        self.assertGreater(result["data_points"], 0)
        self.assertFalse(result["force_exceeded"])

    def test_measurement_height_alias_still_controls_start_z(self):
        from gantry.gantry import Gantry

        gantry = Gantry(offline=True)
        self.asmi._z_target = -12.0
        self.asmi._step_size = 1.0

        result = self.asmi.indentation(gantry, measurement_height=-10.0)

        self.assertEqual(result["measurements"][0]["z_mm"], -11.0)


class TestASMIOnlineRequiresHardware(unittest.TestCase):
    """Verify ASMI(offline=False) raises without hardware."""

    def test_measure_without_connect_raises(self):
        asmi = ASMI(offline=False)
        from instruments.asmi.exceptions import ASMICommandError
        with self.assertRaises(ASMICommandError):
            asmi.measure()

    def test_health_check_without_connect_returns_false(self):
        asmi = ASMI(offline=False)
        self.assertFalse(asmi.health_check())

    def test_is_connected_without_connect_returns_false(self):
        asmi = ASMI(offline=False)
        self.assertFalse(asmi.is_connected())
