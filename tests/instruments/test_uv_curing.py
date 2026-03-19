"""Tests for the UV curing instrument driver."""

import unittest
from unittest.mock import patch, MagicMock

from instruments.base_instrument import BaseInstrument, InstrumentError
from instruments.uv_curing.driver import UVCuring
from instruments.uv_curing.models import CureResult, UVCuringStatus
from instruments.uv_curing.exceptions import (
    UVCuringError,
    UVCuringConnectionError,
    UVCuringCommandError,
    UVCuringTimeoutError,
)


class TestExceptionHierarchy(unittest.TestCase):

    def test_uv_curing_error_is_instrument_error(self):
        self.assertTrue(issubclass(UVCuringError, InstrumentError))

    def test_connection_error_is_uv_curing_error(self):
        self.assertTrue(issubclass(UVCuringConnectionError, UVCuringError))

    def test_command_error_is_uv_curing_error(self):
        self.assertTrue(issubclass(UVCuringCommandError, UVCuringError))

    def test_timeout_error_is_uv_curing_error(self):
        self.assertTrue(issubclass(UVCuringTimeoutError, UVCuringError))


class TestCureResult(unittest.TestCase):

    def test_frozen(self):
        result = CureResult(well_id="A1", intensity_percent=50.0,
                            exposure_time_s=1.0, z_mm=-15.0, timestamp=0.0)
        with self.assertRaises(AttributeError):
            result.well_id = "B2"

    def test_is_valid_true(self):
        result = CureResult(well_id="A1", intensity_percent=50.0,
                            exposure_time_s=1.0, z_mm=-15.0, timestamp=0.0)
        self.assertTrue(result.is_valid)

    def test_is_valid_false_zero_intensity(self):
        result = CureResult(well_id="A1", intensity_percent=0.0,
                            exposure_time_s=1.0, z_mm=-15.0, timestamp=0.0)
        self.assertFalse(result.is_valid)

    def test_is_valid_false_zero_exposure(self):
        result = CureResult(well_id="A1", intensity_percent=50.0,
                            exposure_time_s=0.0, z_mm=-15.0, timestamp=0.0)
        self.assertFalse(result.is_valid)


class TestUVCuringIsBaseInstrument(unittest.TestCase):

    def test_is_subclass(self):
        self.assertTrue(issubclass(UVCuring, BaseInstrument))

    def test_instance(self):
        uv = UVCuring(offline=True)
        self.assertIsInstance(uv, BaseInstrument)


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
        self.assertAlmostEqual(self.uv.get_status().current_intensity, 75.0)

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

    def test_cure_rejects_zero_intensity(self):
        with self.assertRaises(UVCuringCommandError):
            self.uv.cure(intensity=0.0, well_id="A1")

    def test_cure_rejects_zero_exposure(self):
        with self.assertRaises(UVCuringCommandError):
            self.uv.cure(exposure_time=0.0, well_id="A1")

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
        self.assertTrue(self.uv._led_on)
        self.uv.disconnect()
        self.assertFalse(self.uv._led_on)


class TestUVCuringOnlineRequiresHardware(unittest.TestCase):

    def test_health_check_without_connect_returns_false(self):
        uv = UVCuring(offline=False)
        self.assertFalse(uv.health_check())

    def test_send_command_without_connect_raises(self):
        uv = UVCuring(offline=False)
        with self.assertRaises(UVCuringCommandError):
            uv._send_command("LED ON")


class TestUVCuringOnlineMocked(unittest.TestCase):
    """Tests with mocked serial connection."""

    @patch('instruments.uv_curing.driver.serial.Serial')
    def test_connect_opens_serial(self, mock_serial_cls):
        uv = UVCuring(port="/dev/ttyUSB1", offline=False)
        uv.connect()
        mock_serial_cls.assert_called_once_with(
            port="/dev/ttyUSB1", baudrate=115200, timeout=5.0,
        )

    @patch('instruments.uv_curing.driver.serial.Serial')
    def test_connect_raises_on_serial_error(self, mock_serial_cls):
        import serial as real_serial
        mock_serial_cls.side_effect = real_serial.SerialException("no port")
        uv = UVCuring(port="/dev/fake", offline=False)
        with self.assertRaises(UVCuringConnectionError):
            uv.connect()

    @patch('instruments.uv_curing.driver.serial.Serial')
    def test_send_command_writes_and_reads(self, mock_serial_cls):
        mock_ser = mock_serial_cls.return_value
        mock_ser.is_open = True
        mock_ser.readline.return_value = b"OK\n"
        uv = UVCuring(port="/dev/ttyUSB1", offline=False)
        uv.connect()
        response = uv._send_command("LED ON")
        mock_ser.write.assert_called_with(b"LED ON\n")
        self.assertEqual(response, "OK")

    @patch('instruments.uv_curing.driver.serial.Serial')
    def test_send_command_raises_on_error_response(self, mock_serial_cls):
        mock_ser = mock_serial_cls.return_value
        mock_ser.is_open = True
        mock_ser.readline.return_value = b"ERR: bad command\n"
        uv = UVCuring(port="/dev/ttyUSB1", offline=False)
        uv.connect()
        with self.assertRaises(UVCuringCommandError):
            uv._send_command("BAD")

    @patch('instruments.uv_curing.driver.serial.Serial')
    def test_send_command_raises_on_timeout(self, mock_serial_cls):
        mock_ser = mock_serial_cls.return_value
        mock_ser.is_open = True
        mock_ser.readline.return_value = b""
        uv = UVCuring(port="/dev/ttyUSB1", offline=False)
        uv.connect()
        with self.assertRaises(UVCuringTimeoutError):
            uv._send_command("LED ON")

    @patch('instruments.uv_curing.driver.serial.Serial')
    def test_disconnect_closes_serial(self, mock_serial_cls):
        mock_ser = mock_serial_cls.return_value
        mock_ser.is_open = True
        mock_ser.readline.return_value = b"OK\n"
        uv = UVCuring(port="/dev/ttyUSB1", offline=False)
        uv.connect()
        uv.disconnect()
        mock_ser.close.assert_called_once()

    @patch('instruments.uv_curing.driver.serial.Serial')
    def test_disconnect_safe_when_led_command_fails(self, mock_serial_cls):
        mock_ser = mock_serial_cls.return_value
        mock_ser.is_open = True
        mock_ser.readline.return_value = b"OK\n"
        uv = UVCuring(port="/dev/ttyUSB1", offline=False)
        uv.connect()
        uv._led_on = True
        mock_ser.write.side_effect = Exception("serial dead")
        uv.disconnect()
        self.assertFalse(uv._led_on)

    @patch('instruments.uv_curing.driver.serial.Serial')
    def test_health_check_true_when_connected(self, mock_serial_cls):
        mock_ser = mock_serial_cls.return_value
        mock_ser.is_open = True
        uv = UVCuring(port="/dev/ttyUSB1", offline=False)
        uv.connect()
        self.assertTrue(uv.health_check())
