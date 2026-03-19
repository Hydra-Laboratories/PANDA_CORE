"""Tests for the UV curing instrument driver (offline mode)."""

import unittest

from instruments.uv_curing.driver import UVCuring
from instruments.uv_curing.models import CureResult, UVCuringStatus


class TestUVCuringOffline(unittest.TestCase):

    def setUp(self):
        self.uv = UVCuring(offline=True, default_intensity=50.0,
                           default_exposure_time=2.0, default_z=-15.0)

    def test_connect_disconnect_are_noops(self):
        self.uv.connect()
        self.uv.disconnect()

    def test_health_check_returns_true(self):
        self.assertTrue(self.uv.health_check())

    def test_set_intensity(self):
        self.uv.set_intensity(75.0)
        status = self.uv.get_status()
        self.assertAlmostEqual(status.current_intensity, 75.0)

    def test_set_intensity_clamps(self):
        self.uv.set_intensity(150.0)
        self.assertAlmostEqual(self.uv._current_intensity, 100.0)
        self.uv.set_intensity(-10.0)
        self.assertAlmostEqual(self.uv._current_intensity, 0.0)

    def test_led_on_off(self):
        self.uv.led_on()
        self.assertTrue(self.uv.get_status().led_on)
        self.uv.led_off()
        self.assertFalse(self.uv.get_status().led_on)

    def test_cure_returns_result(self):
        result = self.uv.cure(intensity=80.0, exposure_time=3.0, well_id="A1")
        self.assertIsInstance(result, CureResult)
        self.assertAlmostEqual(result.intensity_percent, 80.0)
        self.assertAlmostEqual(result.exposure_time_s, 3.0)
        self.assertEqual(result.well_id, "A1")
        self.assertAlmostEqual(result.z_mm, -15.0)
        self.assertTrue(result.is_valid)

    def test_cure_uses_defaults(self):
        result = self.uv.cure(well_id="B2")
        self.assertAlmostEqual(result.intensity_percent, 50.0)
        self.assertAlmostEqual(result.exposure_time_s, 2.0)

    def test_cure_turns_led_off_after(self):
        self.uv.cure(well_id="A1")
        self.assertFalse(self.uv.get_status().led_on)

    def test_measure_is_alias_for_cure(self):
        result = self.uv.measure(well_id="C3", intensity=10.0)
        self.assertIsInstance(result, CureResult)
        self.assertEqual(result.well_id, "C3")

    def test_get_status(self):
        status = self.uv.get_status()
        self.assertIsInstance(status, UVCuringStatus)
        self.assertTrue(status.is_connected)
        self.assertFalse(status.led_on)

    def test_disconnect_turns_led_off(self):
        self.uv.led_on()
        self.assertTrue(self.uv.get_status().led_on)
        self.uv.disconnect()
        self.assertFalse(self.uv._led_on)


class TestUVCuringOnlineRequiresHardware(unittest.TestCase):

    def test_health_check_without_connect_returns_false(self):
        uv = UVCuring(offline=False)
        self.assertFalse(uv.health_check())

    def test_send_command_without_connect_raises(self):
        uv = UVCuring(offline=False)
        from instruments.uv_curing.exceptions import UVCuringCommandError
        with self.assertRaises(UVCuringCommandError):
            uv._send_command("LED ON")
