"""Contains mocks for cnc driver objects for offline testing"""

# standard libraries
import json
import logging
import re
from pathlib import Path

# third-party libraries
import serial

from .driver import Mill as RealMill
from .exceptions import MillConfigError
from .tools import Coordinates


class MockMill(RealMill):
    """A class that simulates a mill for testing purposes.

    Attributes:
    config_file (str): The path to the configuration file.
    config (dict): The configuration dictionary.
    ser_mill (None): The serial connection to the mill.
    current_x (float): The current x-coordinate.
    current_y (float): The current y-coordinate.
    current_z (float): The current z-coordinate.

    Methods:
    homing_sequence(): Simulate homing, setting feed rate, and clearing buffers.
    disconnect(): Simulate disconnecting from the mill.
    execute_command(command): Simulate executing a command.
    stop(): Simulate stopping the mill.
    reset(): Simulate resetting the mill.
    home(timeout): Simulate homing the mill.
    wait_for_completion(incoming_status, timeout): Simulate waiting for completion.
    current_status(): Simulate getting the current status.
    set_feed_rate(rate): Simulate setting the feed rate.
    clear_buffers(): Simulate clearing buffers.
    gcode_mode(): Simulate getting the G-code mode.
    gcode_parameters(): Simulate getting G-code parameters.
    gcode_parser_state(): Simulate getting G-code parser state.
    rinse_electrode(): Simulate rinsing the electrode.
    move_to_safe_position(): Simulate moving to a safe position.
    move_center_to_position(x_coord, y_coord, z_coord): Simulate moving to a specified position.
    current_coordinates(instrument): Return the tracked current coordinates.
    move_pipette_to_position(x_coord, y_coord, z_coord): Simulate moving the pipette to a specified position.
    move_electrode_to_position(x_coord, y_coord, z_coord): Simulate moving the electrode to a specified position.
    update_offset(offset_type, offset_x, offset_y, offset_z): Simulate updating offsets in the config.
    safe_move(x_coord, y_coord, z_coord, instrument): Simulate a safe move with horizontal and vertical movements.
    """

    def __init__(self):
        super().__init__()
        self.logger_location = Path(__file__).parent / "mock_logs"
        self.ser_mill: MockSerialToMill = self.connect_to_mill()
        self.working_volume: Coordinates = Coordinates(x=-415.0, y=-300.0, z=-200.0)
        self.safe_floor_height = -10.0

        self.change_logging_level("DEBUG")

    def connect_to_mill(self):
        """Connect to the mill"""
        self.logger.info("Connecting to the mill")
        ser_mill = MockSerialToMill(
            port="COM4",
            baudrate=115200,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=10,
        )
        self.active_connection = True
        return ser_mill

    def disconnect(self):
        """Disconnect from the mill"""
        self.logger.info("Disconnecting from the mill")
        self.ser_mill.close()
        self.active_connection = False

    def set_feed_rate(self, rate):
        """Simulate setting the feed rate"""
        self.feed_rate = rate
        self.logger.info("Setting feed rate to %s", rate)

    def clear_buffers(self):
        """Simulate clearing buffers"""
        self.logger.info("Clearing buffers")

    def grbl_settings(self):
        """Simulate getting the GRBL settings"""
        return self.config

    def read_mill_config(self):
        """Read the mill config from the mill and set it as an attribute"""
        try:
            if self.ser_mill.is_open:
                self.logger.info("Reading mill config")
                config_path = Path("grbl_cnc_mill/_configuration.json")
                with config_path.open("r") as file:
                    mill_config = json.load(file)
                self.config = mill_config
                self.logger.debug("Mill config: %s", mill_config)
            else:
                self.logger.error("Serial connection to mill is not open")
                # raise MillConnectionError(
                #     "Serial connection to mill is not open, cannot read config"
                # )
        except Exception as exep:
            self.logger.error("Error reading mill config: %s", str(exep))
            raise MillConfigError("Error reading mill config") from exep

    def __wait_for_completion(self, incoming_status, timeout=5):
        return f"<Idle|MPos:{self.ser_mill.current_x - 3},{self.ser_mill.current_y - 3},{self.ser_mill.current_z - 3}|Bf:15,127|FS:0,0>"

    def __current_status(self):
        return f"<Idle|MPos:{self.ser_mill.current_x},{self.ser_mill.current_y},{self.ser_mill.current_z}|Bf:15,127|FS:0,0>"

    def home(self):
        """Simulate homing the mill"""
        self.logger.info("Homing the mill")
        self.ser_mill.write(b"$H\n")


class MockSerialToMill:
    """A class that simulates a serial connection to the mill for testing purposes."""

    def __init__(self, port, baudrate, parity, stopbits, bytesize, timeout):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = 0
        self.stopbits = stopbits
        self.bytesize = bytesize
        self.parity = parity
        self.is_open = True
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_z = 0.0
        self.logger = logging.getLogger(__name__)

    def close(self):
        """Simulate closing the serial connection"""
        self.is_open = False

    def write(self, command: bytes):
        """Simulate writing to the serial connection"""
        # decode the command to a string
        command = command.decode("utf-8")
        if command == "$H\n" or command == "$H":
            self.current_x = 0.0
            self.current_y = 0.0
            self.current_z = 0.0
            print("Homing the mill")
            print("Setting current coordinates to 0, 0, 0")

        if command == "G01 Z0":
            self.current_z = 0.0
        elif command.startswith("G01"):
            # Extract the coordinates from the command when it could be any of the following:
            # G01 X{} Y{} Z{}
            # G01 X{} Y{}
            # G01 Y{} Z{}
            # G01 X{} Z{}
            # G01 X{}
            # G01 Y{}
            # G01 Z{}

            # Regular expression to extract the coordinates
            steps = command.count("\n")
            pattern = re.compile(r"G01(?: X([\d.-]+))?(?: Y([\d.-]+))?(?: Z([\d.-]+))?")
            for i in range(steps):
                step = command.split("\n")[i]
                match = pattern.search(step)
                if match:
                    goto = [self.current_x, self.current_y, self.current_z]
                    if match.group(1) is not None:
                        self.current_x = float(match.group(1))
                        goto[0] = self.current_x
                    if match.group(2) is not None:
                        self.current_y = float(match.group(2))
                        goto[1] = self.current_y
                    if match.group(3) is not None:
                        self.current_z = float(match.group(3))
                        goto[2] = self.current_z
                    self.logger.info("Moving to coordinates: %s", goto)
                    print(
                        f"Moving to coordinates: G00 X{goto[0]} Y{goto[1]} Z{goto[2]}"
                    )
                else:
                    self.logger.warning(
                        "Could not extract coordinates from the command: %s", step
                    )
            else:
                pass

    def read(self, size):
        """Simulate reading from the serial connection"""
        msg = f"<Idle|MPos:{self.current_x - 3},{self.current_y - 3},{self.current_z - 3}|Bf:15,127|FS:0,0>".encode()
        return msg[:size]

    def read_all(self):
        """Simulate reading from the serial connection"""
        return f"<Idle|MPos:{self.current_x - 3},{self.current_y - 3},{self.current_z - 3}|Bf:15,127|FS:0,0>\n".encode()

    def readline(self):
        """Simulate reading from the serial connection"""
        return f"<Idle|MPos:{self.current_x - 3},{self.current_y - 3},{self.current_z - 3}|Bf:15,127|FS:0,0>\n".encode()

    def readlines(self):
        """Simulate reading from the serial connection"""
        return [
            f"<Idle|MPos:{self.current_x},{self.current_y},{self.current_z}|Bf:15,127|FS:0,0>\n".encode()
        ]

    def flushInput(self):
        """Simulate flushing the input buffer"""
        pass

    def flushOutput(self):
        """Simulate flushing the output buffer"""
        pass

    def grbl_settings(self):
        """Simulate getting the GRBL settings"""
        return "Grbl 1.1f ['$' for help]\n".encode()
