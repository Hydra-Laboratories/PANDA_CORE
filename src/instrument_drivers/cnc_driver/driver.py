"""
This module contains the MillControl class, which is used to control the a GRBL CNC machine.
The MillControl class is used by the EPanda class to move the pipette and electrode to the
specified coordinates.

The MillControl class contains methods to move the pipette and
electrode to a safe position, rinse the electrode, and update the offsets in the mill config
file.

The MillControl class contains methods to connect to the mill, execute commands,
stop the mill, reset the mill, home the mill, get the current status of the mill, get the
gcode mode of the mill, get the gcode parameters of the mill, and get the gcode parser state
of the mill.
"""

# pylint: disable=line-too-long

# standard libraries
import json
import os
import re
import time
from pathlib import Path
from typing import List, Optional, Tuple, Union

# third-party libraries
import serial
import serial.tools.list_ports

from .exceptions import (
    CommandExecutionError,
    LocationNotFound,
    MillConfigError,
    MillConfigNotFound,
    MillConnectionError,
    StatusReturnError,
)

# local libraries
from .logger import set_up_command_logger, set_up_mill_logger
from .tools import Coordinates, ToolManager

# Formatted strings for the mill commands
MILL_MOVE = (
    "G01 X{} Y{} Z{}"  # Move to specified coordinates at the specified feed rate
)
MILL_MOVE_Z = "G01 Z{}"  # Move to specified Z coordinate at the specified feed rate
RAPID_MILL_MOVE = (
    "G00 X{} Y{} Z{}"  # Move to specified coordinates at the maximum feed rate
)
# Compile regex patterns for extracting coordinates from the mill status
wpos_pattern = re.compile(r"WPos:([\d.-]+),([\d.-]+),([\d.-]+)")
mpos_pattern = re.compile(r"MPos:([\d.-]+),([\d.-]+),([\d.-]+)")

axis_conf_table = [
    {"setting_value": 0, "reverse_x": 0, "reverse_y": 0, "reverse_z": 0},
    {"setting_value": 1, "reverse_x": 1, "reverse_y": 0, "reverse_z": 0},
    {"setting_value": 2, "reverse_x": 0, "reverse_y": 1, "reverse_z": 0},
    {"setting_value": 3, "reverse_x": 1, "reverse_y": 1, "reverse_z": 0},
    {"setting_value": 4, "reverse_x": 0, "reverse_y": 0, "reverse_z": 1},
    {"setting_value": 5, "reverse_x": 1, "reverse_y": 0, "reverse_z": 1},
    {"setting_value": 6, "reverse_x": 0, "reverse_y": 1, "reverse_z": 1},
    {"setting_value": 7, "reverse_x": 1, "reverse_y": 1, "reverse_z": 1},
]


class Mill:
    """
    Set up the mill connection and pass commands, including special commands.

    Attributes:
        mill_config_file (str): The name of the mill configuration file.
        config (dict): The configuration of the mill.
        ser_mill (serial.Serial): The serial connection to the mill.
        homed (bool): True if the mill is homed, False otherwise.
        active_connection (bool): True if the connection to the mill is active, False otherwise.
        tool_manager (ToolManager): The tool manager for the mill.
        working_volume (Coordinates): The working volume of the mill.
        safe_floor_height (float): The safe floor height of the mill.
        logger_location (Path): The location of the logger.
        logger (Logger): The logger for the mill.

    Methods:
        change_logging_level(level): Change the logging level.
        homing_sequence(): Home the mill, set the feed rate, and clear the buffers.
        connect_to_mill(port, baudrate, parity, stopbits, bytesize, timeout): Connect to the mill.
        check_for_alarm_state(): Check if the mill is in an alarm state.
        read_mill_config_file(config_file): Read the mill configuration file.
        read_mill_config(): Read the mill configuration from the mill and set it as an attribute.
        write_mill_config_file(config_file): Write the mill configuration to the configuration file.
        execute_command(command): Execute a command on the mill.
        stop(): Stop the mill.
        reset(): Reset the mill.
        soft_reset(): Soft reset the mill.
        home(timeout): Home the mill.
        __wait_for_completion(incoming_status, timeout): Wait for the mill to complete the previous command.
        current_status(): Get the current status of the mill.
        set_feed_rate(rate): Set the feed rate of the mill.
        clear_buffers(): Clear the input and output buffers of the mill.
        gcode_mode(): Get the gcode mode of the mill.
        gcode_parameters(): Get the gcode parameters of the mill.
        gcode_parser_state(): Get the gcode parser state of the mill.
        grbl_settings(): Get the GRBL settings of the mill.
        set_grbl_setting(setting, value): Set a GRBL setting of the mill.
        move_center_to_position(x_coord, y_coord, z_coord, coordinates): Move the mill to the specified coordinates.
        current_coordinates(tool): Get the current coordinates of the mill.
        move_to_safe_position(): Move the mill to its current x,y location and z = 0.
        move_to_position(x, y, z, coordinates, tool): Move the mill to the specified coordinates.
        update_offset(tool, offset_x, offset_y, offset_z): Update the offset in the config file.
        safe_move(x_coord, y_coord, z_coord, coordinates, tool, second_z_cord, second_z_cord_feed): Move the mill to the specified coordinates using only horizontal (xy) and vertical movements.
    """

    def __init__(self, port: Optional[str] = None):
        # self.mill_config_file = "_configuration.json"
        self.logger_location = Path(__file__).parent / "logs"
        self.logger = set_up_mill_logger(self.logger_location)
        self.port = port
        self.config = self.read_mill_config_file("_configuration.json")
        self._clean_config()
        self.ser_mill: serial.Serial = None

    def _clean_config(self):
        """Strip comments from config values"""
        for key, value in self.config.items():
            if isinstance(value, str) and "(" in value:
                self.config[key] = value.split("(", 1)[0].strip()
        self.homed = False
        self.auto_home = True
        self.active_connection = False
        self.tool_manager: ToolManager = ToolManager()
        self.working_volume: Coordinates = self.read_working_volume()
        self.safe_z_height = -10.0  # TODO: In the PANDA wrapper, set the safe floor height to the max height of any active object on the mill + the pipette length
        self.max_z_height = 0.0
        self.command_logger = set_up_command_logger(self.logger_location)
        self.interactive_mode = False

    def read_working_volume(self):
        """Checks the mill config for soft limits to be enabled, and then if so check the x, y, and z max travel limits"""
        working_volume: Coordinates = Coordinates(0, 0, 0)
        # multiplier = 1  # Used for flipping the sign of the working volume depending on the working volume
        if int(self.config["$20"]) == 1:
            self.logger.info("Soft limits are enabled in the mill config")
            # axis_conf_setting_value = int(self.config["$3"])
            # axis_conf = axis_conf_table[axis_conf_setting_value]
            xmultiplier = -1  # if axis_conf["reverse_x"] else 1
            ymultiplier = -1  # if axis_conf["reverse_y"] else 1
            zmultiplier = -1  # if axis_conf["reverse_z"] else 1
            working_volume.x = float(self.config["$130"]) * xmultiplier
            working_volume.y = float(self.config["$131"]) * ymultiplier
            working_volume.z = float(self.config["$132"]) * zmultiplier
        else:
            self.logger.warning("Soft limits are not enabled in the mill config")
            self.logger.warning("Using default working volume")
            working_volume = Coordinates(x=-415.0, y=-300.0, z=-200.0)
        return working_volume

    def change_logging_level(self, level):
        """Change the logging level"""
        self.logger.setLevel(level)

    def homing_sequence(self):
        """Home the mill, set the feed rate, and clear the buffers"""
        self.home()
        self.set_feed_rate(5000)  # Set feed rate to 2000
        self.clear_buffers()
        self.check_max_z_height()

    def check_max_z_height(self):
        """
        After homing, if there are no axes offset (G54-G59), the working coordinates should be 0,0,0.
        If there are axes offset, the working coordinates should be the offset values.

        For this function, if after homing the z coordinate is not 0, then the max z height is set to the current z coordinate.
        """
        current_coordinates = self.current_coordinates()
        if current_coordinates.z != 0:
            self.max_z_height = current_coordinates.z

    def locate_mill_over_serial(self, port: Optional[str] = None) -> Tuple[serial.Serial, str]:
        """
        Locate the mill over serial

        Start with the port proivded and attempt to connect and then query for the mill settings ($$) to verify the connection. The response should begin with a $ and end with an ok

        If the response does not begin with a $, scan for connected devices and attempt to connect to each one until a valid response is received.
        """

        def get_ports():
            """List all available ports"""
            if os.name == "posix":
                # Search for ttyUSB, usbmodem, and usbserial
                ports = list(serial.tools.list_ports.grep("ttyUSB|usbmodem|usbserial"))
            elif os.name == "nt":
                ports = list(serial.tools.list_ports.grep("COM"))
            else:
                raise OSError("Unsupported OS")
            return ports

        def read_past_found_on_port() -> str:
            """Read past the found on port"""
            if not os.path.exists(Path(__file__).parent / "mill_port.txt"):
                # Make a file if it doesn't exist
                with open(Path(__file__).parent / "mill_port.txt", "w") as file:
                    file.write("")

            with open(Path(__file__).parent / "mill_port.txt", "r") as file:
                found_on = file.read()

            if not found_on or found_on == "":
                return []

            return [found_on]

        ser_mill = serial.Serial()
        baudrates = [115200, 9600]
        timeout = 2 # Reduced timeout for faster scanning
        
        # Priority port requested by user
        priority_port = port  # None if not provided
        
        # Create a list starting with the priority port if it exists
        ports = []
        if priority_port:
            ports.append(priority_port)

        # Add others just in case, but after the priority one
        for p in get_ports():
             if p.device != priority_port:
                 ports.append(p.device)

        if not ports:
            self.logger.error("No serial ports found to connect to.")
            raise MillConnectionError("No serial ports found. Checked ttyUSB and usbmodem.")

        found = False
        found_on = None
        while not found:
            for port in ports:
                if not port:
                    continue
                
                for baudrate in baudrates:
                    try:
                        self.logger.info("Attempting connection to port: %s at %s baud", port, baudrate)
                        ser_mill = serial.Serial(
                            port=port,
                            baudrate=baudrate,
                            timeout=timeout,
                        )
                        
                        # Soft reset behavior: some boards reset on DTR toggle, but it can cause issues.
                        # We will try a simple flush first.
                        ser_mill.flushInput()
                        ser_mill.flushOutput()
                        time.sleep(0.1) # Reduced from 1s

                        if not ser_mill.is_open:
                            ser_mill.open()
                            time.sleep(0.5) # Reduced from 1s
                        
                        if not ser_mill.is_open:
                             self.logger.warning("Could not open port %s", port)
                             continue
                        
                        self.logger.info("Querying the mill for status")
                        
                        # Try to wake it up
                        ser_mill.write(b"\r\n")
                        time.sleep(0.1) # Reduced from 0.5
                        ser_mill.write(b"\x18") # Soft reset Ctrl-X
                        time.sleep(0.1) # Reduced from 0.5
                        ser_mill.flushInput()
                        
                        # Now ask for status
                        ser_mill.write(b"?") 
                        time.sleep(0.1) # Reduced from 0.5
                        
                        # Also send $$ as before, but ? is safer for status
                        ser_mill.write(b"$$\n")
                        time.sleep(0.2) # Reduced from 1s

                        statuses = ser_mill.readlines()
                        self.logger.info(f"Raw response: {statuses}")
                        
                        valid_response = False
                        for line in statuses:
                            decoded = line.decode(errors='ignore').rstrip()
                            if "Grbl" in decoded or "ok" in decoded or "error" in decoded or "Idle" in decoded:
                                valid_response = True
                                break
                        
                        if valid_response:
                             self.logger.info(f"Connected successfully to {port} at {baudrate}")
                             found = True
                             found_on = port
                             # Do NOT close here; return the open object to save time
                             break
                        else:
                             self.logger.warning(f"No valid GRBL response from {port} at {baudrate}")
                             ser_mill.close()
                             
                    except Exception as e:
                        self.logger.error(f"Error checking {port} at {baudrate}: {e}")
                        if ser_mill.is_open:
                            ser_mill.close()
                
                if found:
                    break

        # Write the port to a file for future use
        with open(Path(__file__).parent / "mill_port.txt", "w") as file:
            file.write(found_on)

        return ser_mill, found_on

    def connect_to_mill(
        self,
        port: Optional[str] = None,
        baudrate=115200,
        timeout=3,
    ) -> serial.Serial:
        """Connect to the mill"""
        try:
            ser_mill, port_name = self.locate_mill_over_serial(port)
            
            # If we got an open connection back, use it
            if ser_mill and ser_mill.is_open:
                self.logger.info("Reusing open serial connection from detection")
                self.ser_mill = ser_mill
            else:
                # Fallback (should rarely happen if locate succeeds)
                self.logger.info("Opening new serial connection to mill...")
                self.ser_mill = serial.Serial(
                    port=port_name,
                    baudrate=baudrate,
                    timeout=timeout,
                )
                time.sleep(2) # Only sleep if we actually had to open a fresh connection

            if not self.ser_mill.is_open:
                self.ser_mill.open()
                time.sleep(2)
            
            if self.ser_mill.is_open:
                self.logger.info("Serial connection to mill opened successfully")
                self.active_connection = True
            else:
                self.logger.error("Serial connection to mill failed to open")
                raise MillConnectionError("Error opening serial connection to mill")
                
            self.logger.info("Mill connected: %s", self.ser_mill.is_open)
            # print("Mill connected: ", ser_mill.is_open)

        except Exception as exep:
            self.logger.error("Error connecting to the mill: %s", str(exep))
            raise MillConnectionError("Error connecting to the mill") from exep

        # Update the mill config file with the settings from the mill
        self.read_mill_config()
        self.write_mill_config_file("_configuration.json")
        self.read_working_volume()

        self.check_for_alarm_state()
        self.clear_buffers()
        # Set a default feed rate to prevent error:22 on first move
        self.set_feed_rate(2000)
        return self.ser_mill

    def check_for_alarm_state(self):
        """Check if the mill is in an alarm state"""
        status = self.read()
        self.logger.debug("Status: %s", status)
        if not status:
            self.logger.warning("Initial status reading from the mill is blank")
            self.logger.warning("Querying the mill for status")

            status = self.current_status()
            self.logger.debug("Status: %s", status)
            if not status:
                self.logger.error("Failed to get status from the mill")
                raise MillConnectionError("Failed to get status from the mill")
        else:
            status = status[-1].decode().rstrip()
        if "alarm" in status.lower():
            self.logger.warning("Mill is in alarm state. Requesting user input")
            reset_alarm = "y"  # input("Reset the alarm? (y/n): ")
            if reset_alarm[0].lower() == "y":
                self.logger.info("Resetting the mill")
                self.reset()
            else:
                self.logger.error(
                    "Mill is in alarm state, user chose not to reset the mill"
                )
                raise MillConnectionError("Mill is in alarm state")
        if "error" in status.lower():
            self.logger.error("Error in status: %s", status)
            raise MillConnectionError(f"Error in status: {status}")

        # We only check that the mill is indeed lock upon connection because we will home before any movement
        # if "unlock" not in status.lower():
        #     self.logger.error("Mill is not locked")
        #     proceed = input("Proceed? (y/n): ")
        #     if proceed[0].lower() == "n":
        #         raise MillConnectionError("Mill is not locked")
        #     else:
        #         self.logger.warning("Proceeding despite mill not being locked")
        #         self.logger.warning("Current status: %s", status)
        #         self.logger.warning("Homing is reccomended before any movement")
        #         home_now = input("Home now? (y/n): ")
        #         if home_now.lower() == "y":
        #             self.homing_sequence()
        #         else:
        #             self.logger.warning("User chose not to home the mill")
        # self.logger.info("Mill is connected and ready for use, homing first")
        # self.homing_sequence()

    def __enter__(self):
        """Enter the context manager"""
        # Connect to mill with any port specified during object creation
        self.connect_to_mill(port=self.port)
        self.set_feed_rate(5000)

        # Optional auto-homing behavior that can be controlled by a property
        if not self.homed and getattr(self, "auto_home", True):
            self.homing_sequence()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the context manager"""
        self.disconnect()
        self.logger.info("Exiting the mill context manager")

    def disconnect(self):
        """Close the serial connection to the mill"""
        self.logger.info("Disconnecting from the mill")

        # This is PANDA specific and should be implemented by a wrapper class
        # if self.homed:
        #     self.logger.debug("Mill was homed, resting electrode")
        #     self.rest_electrode()

        if self.ser_mill:
            self.ser_mill.close()
            time.sleep(2)
            # self.logger.info("Mill connected: %s", self.ser_mill.is_open) 
            # is_open check on closed port might be valid or not depending on impl, but let's be safe
            if self.ser_mill.is_open:
                self.logger.error("Failed to close the serial connection to the mill")
                raise MillConnectionError("Error closing serial connection to mill")
            else:
                self.logger.info("Serial connection to mill closed successfully")
                self.active_connection = False
                self.ser_mill = None
        else:
             self.logger.info("Serial connection was already closed or never opened.")
        return

    def read_mill_config_file(self, config_file: str = "_configuration.json"):
        """Read the config file"""
        try:
            config_file_path = Path(__file__).parent / config_file
            with open(config_file_path, "r", encoding="UTF-8") as file:
                configuration = json.load(file)
                self.logger.debug("Mill config loaded: %s", configuration)
                return configuration
        except FileNotFoundError:
            self.logger.error("Config file not found")
            self.logger.error("Creating default config file")
            dft_config_file_path = Path(__file__).parent / "default_configuration.json"

            # Better approach: read default and return it directly
            try:
                with open(dft_config_file_path, "r", encoding="UTF-8") as dft_file:
                    default_config = json.load(dft_file)

                # Create the missing config file
                config_file_path.parent.mkdir(exist_ok=True)
                with open(config_file_path, "w", encoding="UTF-8") as file:
                    json.dump(default_config, file, indent=4)

                self.logger.info("Default config file copied to: %s", config_file_path)
                return default_config
            except FileNotFoundError as err:
                self.logger.critical("Default configuration file not found!")
                raise MillConfigNotFound(
                    "Neither primary nor default config file found"
                ) from err
        except Exception as err:
            self.logger.error("Error reading config file: %s", str(err))
            raise MillConfigError("Error reading config file") from err

    def read_mill_config(self):
        """Read the mill config from the mill and set it as an attribute"""
        try:
            if self.ser_mill is not None and self.ser_mill.is_open:
                self.logger.info("Reading mill config")
                mill_config = (
                    self.grbl_settings()
                )  # TODO: Verify the format that settings are returned
                self.config = mill_config
                self.logger.debug("Mill config: %s", mill_config)
            else:
                self.logger.error("Serial connection to mill is not open")
                self.logger.error("Falling back to reading from file")
                self.config = self.read_mill_config_file("_configuration.json")

        except Exception as exep:
            self.logger.error("Error reading mill config: %s", str(exep))
            raise MillConfigError("Error reading mill config") from exep

    def write_mill_config_file(self, config_file="_configuration.json"):
        """Write the mill config to the config file"""
        try:
            config_file_path = Path(__file__).parent / config_file
            with open(config_file_path, "w", encoding="UTF-8") as file:
                json.dump(self.config, file, indent=4)
            self.logger.info("Mill config written to file")
            return 0
        except Exception as exep:
            self.logger.error("Error writing mill config to file: %s", str(exep))
            raise MillConfigError("Error writing mill config to file") from exep

    def execute_command(self, command: str, suppress_errors: bool = False):
        """Encodes and sends commands to the mill and returns the response"""
        try:
            self.logger.debug("Command sent: %s", command)
            self.command_logger.debug("%s", command)
            command_bytes = str(command).encode(encoding="ascii")
            self.ser_mill.write(command_bytes + b"\n")
            # Removed blind 0.5s sleep here to speed up all commands
            # time.sleep(0.5)

            if command == "$$":
                # This is a special command that returns multiple lines
                full_mill_response = [
                    self.ser_mill.readline().decode(encoding="ascii").rstrip()
                ]
                while full_mill_response[-1] != "ok":
                    full_mill_response.append(
                        self.ser_mill.readline().decode(encoding="ascii").rstrip()
                    )
                full_mill_response = full_mill_response[:-1]
                self.logger.debug("Returned %s", full_mill_response)

                # parse the settings into a dictionary
                settings_dict = {}
                self.logger.info(f"Parsing settings from: {full_mill_response}")
                for setting in full_mill_response:
                    if not setting: 
                        continue
                    if setting.startswith("[MSG") or "Grbl" in setting:
                        continue
                        
                    if "=" not in setting:
                        self.logger.warning(f"Skipping non-setting line: {setting}")
                        continue
                        
                    try:
                        key, value = setting.split("=", 1) # Split only on first =
                        # Strip comments from the value (e.g., "0 (soft limits,bool)" -> "0")
                        if "(" in value:
                            value = value.split("(", 1)[0]
                        settings_dict[key.strip()] = value.strip()
                    except ValueError:
                         self.logger.error(f"Failed to parse setting line: {setting}")
                         continue

                return settings_dict

            mill_response = self.read().lower()
            if not command.startswith("$"):
                # self.logger.debug("Initially %s", mill_response)
                mill_response = self.__wait_for_completion(mill_response, suppress_errors=suppress_errors)
                self.logger.debug("Returned %s", mill_response)
            else:
                self.logger.debug("Returned %s", mill_response)

            if re.search(r"(error|alarm)", mill_response):
                if re.search(r"error:22", mill_response):
                    # This is a GRBL error that occurs when the feed rate isn't set before moving with G01 command
                    self.logger.error("Error in status: %s", mill_response)
                    # Try setting the feed rate and executing the command again
                    self.set_feed_rate(2000)
                    mill_response = self.execute_command(command, suppress_errors=suppress_errors)
                else:
                    if not suppress_errors:
                        self.logger.error(
                            "current_status: Error in status: %s", mill_response
                        )
                    raise StatusReturnError(f"Error in status: {mill_response}")

        except Exception as exep:
            if not suppress_errors:
                self.logger.error("Error executing command %s: %s", command, str(exep))
            raise CommandExecutionError(
                f"Error executing command {command}: {str(exep)}"
            ) from exep

        return mill_response

    def stop(self):
        """Stop the mill"""
        self.execute_command("!")

    def reset(self):
        """Reset or unlock the mill"""
        self.execute_command("$X")

    def soft_reset(self):
        """Soft reset the mill"""
        self.execute_command("^X")

    def home(self, timeout=90):
        """Home the mill with a timeout"""
        self.execute_command("$H")
        # replaced 15s sleep with a polling wait
        time.sleep(1) # Wait a second for homing to start
        start_time = time.time()

        while True:
            # Poll status more frequently to catch completion early
            status = self.current_status()

            if time.time() - start_time > timeout:
                self.logger.warning("Homing timed out")
                break

            if "Idle" in status:
                self.logger.info("Homing completed")
                self.homed = True
                break

            if "Alarm" in status or "alarm" in status:
                # Try homing again
                self.logger.warning("Homing failed, trying again...")
                self.execute_command("$H")

            time.sleep(0.5)

    def home_xy_hard_limits(self):
        """
        Custom homing strategy for machines without valid Z homing.
        Homes X and Y axes independently using hard limits.
        """
        self.logger.info("Starting Custom XY Hard Limit Homing...")
        
        # Define homing parameters (matching custom scripts)
        # X: Right is positive, Max Travel ~320
        # Y: Back is positive, Max Travel ~320
        HOMING_FEED_FAST = 500
        MAX_TRAVEL = 320.0
        BACKOFF_DIST = 2.0
        
        # Helper to home a single axis
        def home_axis(axis: str, direction: int):
            self.logger.info(f"Homing Axis: {axis}, Direction: {direction}")
            
            # Ensure relative mode
            self.execute_command("G91")
            
            dist_moved = 0.0
            switch_hit = False
            step_size = 10.0 # mm per check
            
            while dist_moved < MAX_TRAVEL:
                # Move
                move_cmd = f"G1 {axis}{step_size * direction} F{HOMING_FEED_FAST}"
                is_hit = False
                
                try:
                    self.execute_command(move_cmd, suppress_errors=True)
                    dist_moved += step_size
                except Exception as e:
                    # Check for alarm or error indicative of hard limit
                    err_msg = str(e)
                    if "error:9" in err_msg or "Alarm" in err_msg:
                        is_hit = True
                        self.logger.info(f"Hit detected via exception: {err_msg}")
                
                # Check Status for Pn: trigger or Alarm
                status = ""
                try:
                    status = self.current_status()
                except Exception as e:
                    # If current_status raises (due to Alarm), check the exception message
                    status_err = str(e)
                    if "Alarm" in status_err or "Pn:" in status_err:
                         # We can try to extract the status from the error message if needed
                         # But knowing we have an alarm is usually enough if we were moving
                         status = status_err
                         is_hit = True
                
                # GRBL triggers an Alarm (often error:9) upon hard limit
                # Status string might show <Alarm|...|Pn:X>
                if "Alarm" in status:
                    is_hit = True
                if "Pn:" in status:
                     # Check if specific axis triggered
                     triggered_pins = status.split("Pn:")[1].split("|")[0]
                     if axis in triggered_pins:
                         is_hit = True
                
                if is_hit:
                    self.logger.info(f"Hard limit hit for {axis}!")
                    switch_hit = True
                    
                    # Clear Alarm
                    self.logger.info("Clearing Alarm ($X)...")
                    try:
                        self.execute_command("$X")
                    except:
                        pass
                    time.sleep(1)
                    break
                
                # Optional: Sleep slightly to not flood serial?
                # execute_command waits for 'ok', so it naturally paces.
            
            if not switch_hit:
                self.logger.error(f"Failed to home {axis}: Max travel reached without hitting switch.")
                raise MillConnectionError(f"Homing failed for {axis}")

            # Back off
            self.logger.info(f"Backing off {axis}...")
            self.execute_command("G91")
            self.execute_command(f"G0 {axis}{-BACKOFF_DIST * direction}")
            
            # Set Zero
            # For 3018, usually:
            # X Limit is RIGHT (Max X). If we want X=0 at RIGHT, we set X=0. 
            # If we want X=0 at LEFT, we set X=MAX_TRAVEL (and soft limits work).
            # The custom script sets X=0 at the switch.
            self.logger.info(f"Setting {axis} Zero...")
            self.execute_command(f"G10 L20 P1 {axis}0")
            
            # Reset to Absolute
            self.execute_command("G90")

        # Home X (Right/Positive)
        home_axis("X", 1)
        
        # Home Y (Back/Positive)
        home_axis("Y", 1)
        
        self.homed = True
        self.logger.info("Custom XY Homing Complete.")

    def __wait_for_completion(self, incoming_status, suppress_errors: bool = False, timeout=5):
        """Wait for the mill to complete the previous command"""
        status = incoming_status
        start_time = time.time()
        while "Idle" not in status:
            if "<Run" in status:
                start_time = time.time()
            if "error" in status:
                if not suppress_errors:
                    self.logger.error("Error in status: %s", status)
                raise StatusReturnError(f"Error in status: {status}")
            if "alarm" in status:
                if not suppress_errors:
                    self.logger.error("Alarm in status: %s", status)
                raise StatusReturnError(f"Alarm in status: {status}")
            if time.time() - start_time > timeout:
                self.logger.warning("Command execution timed out")
                return status
            status = self.current_status()
        # print("Time to wait for completion: ", time.time() - start_time)
        return status

    def current_status(self) -> str:
        """Get the current status of the mill"""
        # start_time = time.time()
        attempt_limit = 5
        status = self.read()
        # print(status)

        while status in ["", "ok"] and attempt_limit > 0:
            self.ser_mill.write(b"?")
            time.sleep(0.2)
            status = self.read()
            # print(status) if status else None
            attempt_limit -= 1

        if not status:
            # Try reading multiple lines looking for an error or alarm
            status = self.ser_mill.readlines()
            status = [item.decode().rstrip() for item in status]
            if not status:
                self.logger.error("Failed to get status from the mill")
                if self.interactive_mode:
                    print("Failed to get status from the mill")
                    return ""
                raise StatusReturnError("Failed to get status from the mill")
            if any(re.search(r"\b(error|alarm)\b", item.lower()) for item in status):
                self.logger.error("Error in status: %s", status)
                if self.interactive_mode:
                    print("Error in status: %s", status)
                    return ""
                raise StatusReturnError(f"Error in status: {status}")
        # Check for busy
        # while status == "ok":
        #     status = self.serial_rx()
        # print("Time to get status: ", time.time() - start_time)
        return status

    def write(self, command: str):
        """Write a command to the mill"""
        command = command.upper()
        if command != "?":
            # If not a status request, ensure there is a carriage return at the end
            command += "\n"

        self.ser_mill.write(command.encode(encoding="ascii"))

    def read(self):
        msg = self.ser_mill.read(1)
        if msg == b"":
            return ""
        msg += self.ser_mill.read_all()
        msg = msg.decode(encoding="ascii")
        return msg

    def txrx(self, command: str) -> str:
        """Write a command to the mill and read the response"""
        self.write(command)
        time.sleep(0.2)
        return self.read()

    def set_feed_rate(self, rate):
        """Set the feed rate"""
        self.execute_command(f"F{rate}")

    def clear_buffers(self):
        """Clear input and output buffers"""
        self.ser_mill.flush()  # Clear input buffer
        self.ser_mill.read_all()  # Clear output buffer

    def gcode_mode(self):
        """Ask the mill for its gcode mode"""
        self.execute_command("$C")

    def gcode_parameters(self):
        """Ask the mill for its gcode parameters"""
        return self.execute_command("$#")

    def gcode_parser_state(self):
        """Ask the mill for its gcode parser state"""
        return self.execute_command("$G")

    def grbl_settings(self) -> dict:
        """Ask the mill for its grbl settings"""
        return self.execute_command("$$")

    def set_grbl_setting(self, setting: str, value: str):
        """Set a grbl setting"""
        command = f"${setting}={value}"
        return self.execute_command(command)

    def current_coordinates(
        self, tool: Optional[str] = None, tool_only: bool = True
    ) -> Union[Coordinates, Tuple[Coordinates, Coordinates]]:
        """
        Get the current coordinates of the mill.
        Args:
            tool (Tool): The tool for which to get the offset coordinates.
        Returns:
            mill_center (Coordinates): [x,y,z]
            tool_head (Coordinates): [x,y,z]
        """
        self.ser_mill.write(b"?")
        time.sleep(0.2)
        status = self.read()
        attempts = 0
        while status[0] != "<" and attempts < 3:
            if "alarm" in status.lower() or "error" in status.lower():
                self.logger.error("Error in status: %s", status)
                raise StatusReturnError(f"Error in status: {status}")
            if "ok" in status.lower():
                self.logger.debug("OK in status: %s", status)
            status = self.read()
            attempts += 1
        # Get the current mode of the mill
        # 0=WCS position, 1=Machine position, 2= plan/buffer and WCS position, 3=plan/buffer and Machine position.
        status_mode = int(self.config["$10"])

        if int(status_mode) not in [0, 1, 2, 3]:
            self.logger.error("Invalid status mode")
            raise ValueError("Invalid status mode")

        max_attempts = 3
        homing_pull_off = float(self.config["$27"])

        pattern = wpos_pattern if status_mode in [0, 2] else mpos_pattern
        coord_type = "WPos" if status_mode in [0, 2] else "MPos"

        for i in range(max_attempts):
            match = pattern.search(status)
            if match:
                x_coord = round(float(match.group(1)), 3)
                y_coord = round(float(match.group(2)), 3)
                z_coord = round(float(match.group(3)), 3)
                if coord_type == "MPos":
                    pass # Offset removed
                self.logger.info(
                    "%s coordinates: X = %s, Y = %s, Z = %s",
                    coord_type,
                    x_coord,
                    y_coord,
                    z_coord,
                )
                break
            else:
                self.logger.warning(
                    "%s coordinates not found in the line. Trying again...",
                    coord_type,
                )
            if i == max_attempts - 1:
                self.logger.error(
                    "Error occurred while getting %s coordinates", coord_type
                )
                raise LocationNotFound

        mill_center = Coordinates(x_coord, y_coord, z_coord)
        # So far we have obtain the mill's coordinates
        # Now we need to adjust them based on the instrument to communicate where the current instrument is
        if tool:
            try:
                offsets = self.tool_manager.get_offset(tool)
                # NOTE that these have minus instead of plus as usual since we are saying where the tool head is
                tool_head = Coordinates(
                    x_coord - offsets.x,
                    y_coord - offsets.y,
                    z_coord - offsets.z,
                )

            except Exception as exception:
                raise ValueError("Invalid instrument") from exception

            if tool_only:
                return tool_head
            else:
                return mill_center, tool_head
        else:
            return mill_center

    # TODO ensure all calls of this function are updated to reflect the return of two coordinates

    def move_to_safe_position(self) -> str:
        """Move the mill to its current x,y location and the max z height"""
        return self.execute_command(f"G01 Z{self.max_z_height}")

    def move_to_position(
        self,
        x_coordinate: float = 0.00,
        y_coordinate: float = 0.00,
        z_coordinate: float = 0.00,
        coordinates: Coordinates = None,
        tool: str = "center",
    ) -> Coordinates:
        """
        Move the mill to the specified coordinates.
        Args:
            x_coord (float): X coordinate.
            y_coord (float): Y coordinate.
            z_coord (float): Z coordinate.
            instrument (Instruments): Instrument to move.
        Returns:
            str: Response from the mill after executing the command.
        """
        # updated target coordinates with offsets so the center of the mill moves to the right spot
        goto = (
            Coordinates(x=x_coordinate, y=y_coordinate, z=z_coordinate)
            if not coordinates
            else coordinates
        )
        offsets = self.tool_manager.get_offset(tool)
        current_coordinates = self.current_coordinates()

        target_coordinates = self._calculate_target_coordinates(
            goto, current_coordinates, offsets
        )

        if self._is_already_at_target(target_coordinates, current_coordinates):
            self.logger.debug(
                "%s is already at the target coordinates of [%s, %s, %s]",
                tool,
                x_coordinate,
                y_coordinate,
                z_coordinate,
            )
            return current_coordinates

        self._log_target_coordinates(target_coordinates)
        self._validate_target_coordinates(target_coordinates)
        commands = self._generate_movement_commands(
            current_coordinates, target_coordinates
        )
        # command = MILL_MOVE.format(*goto)
        # self.execute_command(command)
        command_str = "\n".join(commands)
        self.execute_command(command_str)
        return None  # self.current_coordinates(tool)

    def move_to_positions(
        self,
        coordinates: List[Coordinates],
        tool: str = "center",
        safe_move_required: bool = True,
    ) -> None:
        """
        Move the mill to the specified list of coordinate locations safely.
        Each movement ensures proper Z-axis clearance before horizontal movements.

        Args:
            coordinates (List[Coordinates]): List of target coordinates to move to in sequence
            tool (str): The tool being used (default: "center")
            safe_move_required (bool): Whether to enforce safe movement patterns (default: True)
        """
        current_coordinates = self.current_coordinates()
        offsets = self.tool_manager.get_offset(tool)
        commands = []

        for target in coordinates:
            target_coordinates = self._calculate_target_coordinates(
                target, current_coordinates, offsets
            )

            self._validate_target_coordinates(target_coordinates)

            if self._is_already_at_target(target_coordinates, current_coordinates):
                self.logger.debug(
                    "%s is already at target coordinates [%s, %s, %s]",
                    tool,
                    target_coordinates.x,
                    target_coordinates.y,
                    target_coordinates.z,
                )
                continue

            # Safe move logic disabled by request
            commands.extend(
                self._generate_movement_commands(
                    current_coordinates, target_coordinates
                )
            )

            current_coordinates = target_coordinates

        if commands:
            command_str = "\n".join(commands)
            self.execute_command(command_str)

    def update_offset(self, tool, offset_x, offset_y, offset_z):
        """
        Update the offset in the config file
        """
        current_offset = self.tool_manager.get_offset(tool)
        new_offset = Coordinates(
            current_offset.x + offset_x,
            current_offset.y + offset_y,
            current_offset.z + offset_z,
        )

        self.tool_manager.update_tool(tool, new_offset)

    ## Special versions of the movement commands that avoid diagonal movements
    def safe_move(
        self,
        x_coord=None,
        y_coord=None,
        z_coord=None,
        coordinates: Coordinates = None,
        tool: str = "center",
        second_z_cord: float = None,
        second_z_cord_feed: float = 2000,
    ) -> Coordinates:
        """
        Move the mill to the specified coordinates using only horizontal (xy) and vertical movements.

        Args:
            x_coord (float): X coordinate.
            y_coord (float): Y coordinate.
            z_coord (float): Z coordinate.
            instrument (Instruments): The instrument to move to the specified coordinates.
            second_z_cord (float): The second z coordinate to move to.
            second_z_cord_feed (float): The feed rate to use when moving to the second z coordinate.

        Returns:
            Coordinates: Current center coordinates.
        """
        if not isinstance(tool, str):
            try:
                tool = tool.value
            except AttributeError:
                raise ValueError("Invalid tool") from None
        commands = []
        goto = (
            Coordinates(x=x_coord, y=y_coord, z=z_coord)
            if not coordinates
            else coordinates
        )
        offsets = self.tool_manager.get_offset(tool)
        current_coordinates = self.current_coordinates()

        target_coordinates = self._calculate_target_coordinates(
            goto, current_coordinates, offsets
        )
        self._validate_target_coordinates(target_coordinates)
        if self._is_already_at_target(target_coordinates, current_coordinates):
            self.logger.debug(
                "%s is already at the target coordinates of [%s, %s, %s]",
                tool,
                x_coord,
                y_coord,
                z_coord,
            )
            return current_coordinates

        self._log_target_coordinates(target_coordinates)
        move_to_zero = False
        if self.__should_move_to_safe_position_first(
            current_coordinates, target_coordinates, self.max_z_height
        ):
            self.logger.debug("Moving to Z=%s first", self.max_z_height)
            # self.execute_command("G01 Z0")
            commands.append(f"G01 Z{self.max_z_height}")
            # current_coordinates = self.current_coordinates(instrument)
            move_to_zero = True
        else:
            self.logger.debug("Not moving to Z=%s first", self.max_z_height)

        commands.extend(
            self._generate_movement_commands(
                current_coordinates, target_coordinates, move_to_zero
            )
        )

        if second_z_cord is not None:
            # Adjust the second_z_coord according to the tool offsets
            second_z_cord += offsets.z

            # Add the movement to the second z coordinate and feed rate
            commands.append(f"G01 Z{second_z_cord} F{second_z_cord_feed}")
            # Restore the feed rate to the default of 2000
            commands.append("F2000")
        # Form the individual movement commands into a block seperated by \n
        command_str = "\n".join(commands)
        self.execute_command(command_str)

        return self.current_coordinates()

    def _is_already_at_target(
        self, goto: Coordinates, current_coordinates: Coordinates
    ):
        """Check if the mill is already at the target coordinates"""
        return (goto.x, goto.y) == (
            current_coordinates.x,
            current_coordinates.y,
        ) and goto.z == current_coordinates.z

    def _calculate_target_coordinates(
        self, goto: Coordinates, current_coordinates: Coordinates, offsets: Coordinates
    ):
        """
        Calculate the target coordinates for the mill. Checking if the mill is already at the target xy coordinates and only moving if necessary.

        Args:
            goto (Coordinates): The target coordinates.
            current_coordinates (Coordinates): The current coordinates of the mill center.
            offsets (Coordinates): The offsets for the instrument.
        """
        return Coordinates(
            x=goto.x + offsets.x,
            y=goto.y + offsets.y,
            z=goto.z + offsets.z,
        )

    def _log_target_coordinates(self, target_coordinates: Coordinates):
        self.logger.debug(
            "Target coordinates: [%s, %s, %s]",
            target_coordinates.x,
            target_coordinates.y,
            target_coordinates.z,
        )

    def _validate_target_coordinates(self, target_coordinates: Coordinates):
        # Validation disabled by request
        pass
        # if (
        #     not self.working_volume.x <= target_coordinates.x <= 0
        # ):  # TODO remove the <=0 check after verifying that new offsets work
        #     # TODO move to overall travel from 0 to working volume as the check
        #     self.logger.error("x coordinate out of range")
        #     raise ValueError("x coordinate out of range")
        # if not self.working_volume.y <= target_coordinates.y <= 0:
        #     # If the target y is not between the working volume and 0, raise an error
        #     self.logger.error("y coordinate out of range")
        #     raise ValueError("y coordinate out of range")
        # if not self.working_volume.z <= target_coordinates.z <= self.max_z_height:
        #     # If the target z is not between the working volume and the max z height, raise an error
        #     self.logger.error("z coordinate out of range")
        #     raise ValueError("z coordinate out of range")

    def _generate_movement_commands(
        self,
        current_coordinates: Coordinates,
        target_coordinates: Coordinates,
        move_z_first: bool = False,
    ):
        commands = []
        if current_coordinates.z >= self.safe_z_height or move_z_first:
            # If above the safe height, allow an XY diagonal move then Z movement
            commands.append(f"G01 X{target_coordinates.x} Y{target_coordinates.y}")
            commands.append(f"G01 Z{target_coordinates.z}")
        else:
            if target_coordinates.x != current_coordinates.x:
                commands.append(f"G01 X{target_coordinates.x}")
            if target_coordinates.y != current_coordinates.y:
                commands.append(f"G01 Y{target_coordinates.y}")
            if target_coordinates.z != current_coordinates.z:
                commands.append(f"G01 Z{target_coordinates.z}")
            if (
                target_coordinates.z == current_coordinates.z and move_z_first
            ):  # The mill moved to Z max first, so move back to the target Z
                commands.append(f"G01 Z{target_coordinates.z}")

        return commands

    def __should_move_to_safe_position_first(
        self,
        current: Coordinates,
        destination: Coordinates,
        safe_height_floor: Optional[float] = None,
    ):
        """
        Determine if the mill should move to self.max_z_height before moving to the specified coordinates.
        Args:
            current (Coordinates): Current coordinates.
            offset (Coordinates): Target coordinates.
            safe_height_floor (float): Safe floor height.
        Returns:
            bool: True if the mill should move to self.max_z_height first, False otherwise.
        """
        if safe_height_floor is None:
            safe_height_floor = self.safe_z_height
        # If current Z is at z max or at or above the safe floor height, no need to move to Z max
        if current.z >= self.max_z_height or current.z >= safe_height_floor:
            return False

        # If current Z is below the safe floor height and X or Y coordinates are different, move to Z max
        if current.x != destination.x or current.y != destination.y:
            return True

        return False
