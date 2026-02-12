# grbl_command_reference.py

# Dictionary of GRBL G-code commands with their descriptions
grbl_gcode_commands = {
    # Non-Modal Commands
    "G4": "Dwell",
    "G10L2": "Set Work Coordinate System Offset",
    "G10L20": "Set Tool Table Offset",
    "G28": "Return to Home Position",
    "G30": "Return to Secondary Home Position",
    "G28.1": "Set Home Position",
    "G30.1": "Set Secondary Home Position",
    "G53": "Move in Absolute Machine Coordinates",
    "G92": "Set Position",
    "G92.1": "Cancel G92 Offsets",
    # Motion Modes
    "G0": "Rapid Positioning",
    "G1": "Linear Interpolation",
    "G2": "Clockwise Circular Interpolation",
    "G3": "Counterclockwise Circular Interpolation",
    "G38.2": "Probe Toward Workpiece, Stop on Contact",
    "G38.3": "Probe Toward Workpiece, No Error if No Contact",
    "G38.4": "Probe Away from Workpiece, Stop on Loss of Contact",
    "G38.5": "Probe Away from Workpiece, No Error if No Contact",
    "G80": "Cancel Canned Cycle",
    # Feed Rate Modes
    "G93": "Inverse Time Mode",
    "G94": "Units per Minute Mode",
    # Unit Modes
    "G20": "Inches",
    "G21": "Millimeters",
    # Distance Modes
    "G90": "Absolute Positioning",
    "G91": "Incremental Positioning",
    # Arc IJK Distance Modes
    "G91.1": "Incremental Arc Distance Mode",
    # Plane Select Modes
    "G17": "XY Plane Selection",
    "G18": "ZX Plane Selection",
    "G19": "YZ Plane Selection",
    # Spindle Control
    "M3": "Spindle On (Clockwise)",
    "M4": "Spindle On (Counter-Clockwise)",
    "M5": "Spindle Stop",
    # Coolant Control
    "M7": "Mist Coolant On",
    "M8": "Flood Coolant On",
    "M9": "Coolant Off",
}

# Dictionary of GRBL non-G-code commands with their descriptions
grbl_non_gcode_commands = {
    "$$": "Display Grbl Settings",
    "$#": "View GCode Parameters",
    "$G": "View GCode parser state",
    "$C": "Toggle Check Gcode Mode",
    "$H": "Run Homing Cycle",
    "$J=gcode": "Run Jogging Motion",
    "$X": "Kill Alarm Lock state",
    "$I": "View Build Info",
    "$N": "View saved start up code",
    "$Nx": "Nx=line Save Start-up GCode line (x=0 or 1). These are executed on a reset",
    "$RST=$": "Restores the Grbl settings to defaults",
    "$RST=#": "Erases G54-G59 WCS offsets and G28/30 positions stored in EEPROM",
    "$RST=*": "Clear and Load all data from EEPROM",
    "$SLP": "Enable Sleep mode",
    "Ctrl-x": "Soft Reset",
    "?": "Status report query",
    "~": "Cycle Start/Resume from Feed Hold, Door or Program pause",
    "!": "Feed Hold – Stop all motion",
}

# Dictionary of GRBL error codes with their descriptions
grbl_error_codes = {
    1: "Expected Command Letter: G-code words consist of a letter and a value. Letter was not found",
    2: "Bad Number Format: Missing the expected G-code word value or numeric value format is not valid",
    3: "Invalid Statement: Grbl ‘$’ system command was not recognized or supported",
    4: "Value < 0: Negative value received for an expected positive value",
    5: "Homing Disabled: Homing cycle failure. Homing is not enabled via settings",
    7: "EEPROM Read Fail: An EEPROM read failed. Auto-restoring affected EEPROM to default values",
    8: "Not Idle: Grbl ‘$’ command cannot be used unless Grbl is IDLE. Ensures smooth operation during a job",
    9: "G-Code Lock: G-code commands are locked out during alarm or jog state",
    10: "Homing Not Enabled: Soft limits cannot be enabled without homing also enabled",
    11: "Line Overflow: Max characters per line exceeded. File most likely formatted improperly",
    14: "Line Length Exceeded: Build info or startup line exceeded EEPROM line length limit. Line not stored",
    15: "Travel Exceeded: Jog target exceeds machine travel. Jog command has been ignored",
    17: "Setting Disabled: Laser mode requires PWM output",
    20: "Unsupported Command: Unsupported or invalid g-code command found in block",
    21: "Modal Group Violation: More than one g-code command from same modal group found in block",
    22: "Undefined Feed Rate: Feed rate has not yet been set or is undefined",
}

# Dictionary of GRBL alarm codes with their descriptions
grbl_alarm_codes = {
    1: "Hard limit triggered. Position Lost",
    2: "Soft limit alarm, position kept. Unlock is Safe",
    3: "Reset while in motion. Position lost",
    4: "Probe fail. Probe not in expected initial state",
    5: "Probe fail. Probe did not contact the work",
    6: "Homing fail. The active homing cycle was reset",
    7: "Homing fail. Door opened during homing cycle",
    8: "Homing fail. Pull off failed to clear limit switch",
    9: "Homing fail. Could not find limit switch",
}

grbl_settings = {
    0: "Step pulse, microseconds",
    1: "Step idle delay, milliseconds",
    2: "Step port invert, XYZmask*",
    3: "Direction port invert, XYZmask*",
    4: "Step enable invert, (0=Disable, 1=Invert)",
    5: "Limit pins invert, (0=N-Open. 1=N-Close)",
    6: "Probe pin invert, (0=N-Open. 1=N-Close)",
    10: "Status report, '?' status. 0=WCS, 1=Machine, 2=plan/buffer + WCS, 3=plan/buffer + Machine.",
    11: "Junction deviation, mm",
    12: "Arc tolerance, mm",
    13: "Report in inches, (0=mm. 1=Inches)**",
    20: "Soft limits, (0=Disable. 1=Enable, Hard limits and homing Required.",
    21: "Hard limits, (0=Disable. 1=Enable)",
    22: "Homing cycle, (0=Disable. 1=Enable)",
    23: "Homing direction invert, XYZmask* Sets home Pos",
    24: "Homing feed, mm/min",
    25: "Homing seek, mm/min",
    26: "Homing debounce, milliseconds",
    27: "Homing pull-off, mm",
    30: "Max spindle speed, RPM",
    31: "Min spindle speed, RPM",
    32: "Laser mode, (0=Off, 1=On)",
    100: "Number of X steps to move 1mm",
    101: "Number of Y steps to move 1mm",
    102: "Number of Z steps to move 1mm",
    103: "Number of A steps to move 1°",
    110: "X Max rate, mm/min",
    111: "Y Max rate, mm/min",
    112: "Z Max rate, mm/min",
    113: "A Max rate, °/min",
    120: "X Acceleration, mm/sec^2",
    121: "Y Acceleration, mm/sec^2",
    122: "Z Acceleration, mm/sec^2",
    123: "A Acceleration, °/sec^2",
    130: "X Max travel, mm Only for Homing and Soft Limits.",
    131: "Y Max travel, mm Only for Homing and Soft Limits.",
    132: "Z Max travel, mm Only for Homing and Soft Limits.",
    133: "A Max travel, ° Only for Homing and Soft Limits.",
}


def get_command_description(command):
    """
    Retrieve the description of a given GRBL command.

    Parameters:
        command (str): The GRBL command (e.g., 'G0', '$$', 'M3').

    Returns:
        str: Description of the GRBL command if found, else 'Unknown command'.
    """
    command = command.upper()
    if command in grbl_gcode_commands:
        return command
    elif command in grbl_non_gcode_commands:
        return command
    elif "=" in command:
        # Handle commands with parameters (e.g., $x=val)
        # Extract the command key (e.g., $x) and value (e.g., val)
        # Split the command by '=' and get the first part as the command key
        # and the second part as the value

        command_key, value = command.split("=")
        command_key = command_key.strip()
        value = value.strip()
        if command_key in grbl_settings:
            return f"{command_key}={value}"
        elif command_key in grbl_non_gcode_commands:
            return f"{command_key}={value}"
        else:
            return "Unknown command"

    else:
        return "Unknown command"


def get_error_description(error_code):
    """
    Retrieve the description of a given GRBL error code.

    Parameters:
        error_code (int): The GRBL error code (e.g., 1, 2, 3).
    Returns:
        str: Description of the GRBL error code if found, else 'Unknown error code'.
    """
    if error_code in grbl_error_codes:
        return grbl_error_codes[error_code]
    else:
        return "Unknown error code"


def get_alarm_description(alarm_code):
    """
    Retrieve the description of a given GRBL alarm code.

    Parameters:
        alarm_code (int): The GRBL alarm code (e.g., 1, 2, 3).
    Returns:
        str: Description of the GRBL alarm code if found, else 'Unknown alarm code'.
    """
    if alarm_code in grbl_alarm_codes:
        return grbl_alarm_codes[alarm_code]
    else:
        return "Unknown alarm code"


def get_all_commands():
    """
    Retrieve all GRBL commands and their descriptions.

    Returns:
        dict: Dictionary of all GRBL commands and their descriptions.
    """
    return {**grbl_gcode_commands, **grbl_non_gcode_commands}


def get_all_error_codes():
    """
    Retrieve all GRBL error codes and their descriptions.
    Returns:
        dict: Dictionary of all GRBL error codes and their descriptions.
    """
    return grbl_error_codes


def get_all_alarm_codes():
    """
    Retrieve all GRBL alarm codes and their descriptions.
    Returns:
        dict: Dictionary of all GRBL alarm codes and their descriptions.
    """
    return grbl_alarm_codes


def get_all_codes():
    """
    Retrieve all GRBL codes (commands, error codes, and alarm codes) and their descriptions.
    Returns:
        dict: Dictionary of all GRBL codes and their descriptions.
    """
    all_codes = {
        "commands": get_all_commands(),
        "error_codes": get_all_error_codes(),
        "alarm_codes": get_all_alarm_codes(),
    }
    return all_codes


def get_code_description(code):
    """
    Retrieve the description of a given GRBL code (command, error code, or alarm code).
    Parameters:
        code (str or int): The GRBL code (e.g., 'G0', '$$', 1).
    Returns:
        str: Description of the GRBL code if found, else 'Unknown code'.
    """
    if isinstance(code, str):
        return get_command_description(code)
    elif isinstance(code, int):
        if code in grbl_error_codes:
            return get_error_description(code)
        elif code in grbl_alarm_codes:
            return get_alarm_description(code)
        else:
            return "Unknown code"
    else:
        return "Unknown code"


def validate_gcode(gcode):
    """
    Validate a given G-code command.

    Parameters:
        gcode (str): The G-code command to validate.

    Returns:
        bool: True if the G-code is valid, False otherwise.
    """
    # Check if the G-code starts with 'G' or 'M'
    if not (gcode.startswith("G") or gcode.startswith("M")):
        return False

    # Check if the G-code contains only valid characters
    for char in gcode[1:]:
        if not (char.isdigit() or char in [".", "-", "+"]):
            return False

    return True


def validate_command(command):
    """
    Validate a given GRBL command.
    Parameters:
        command (str): The GRBL command to validate.
    Returns:
        bool: True if the command is valid, False otherwise.
    """
    # Check if the command is in the list of valid commands
    if command in grbl_gcode_commands or command in grbl_non_gcode_commands:
        return True
    else:
        return False


def validate_error_code(error_code):
    """
    Validate a given GRBL error code.
    Parameters:
        error_code (int): The GRBL error code to validate.
    Returns:
        bool: True if the error code is valid, False otherwise.
    """
    # Check if the error code is in the list of valid error codes
    if error_code in grbl_error_codes:
        return True
    else:
        return False


def validate_alarm_code(alarm_code):
    """
    Validate a given GRBL alarm code.
    Parameters:
        alarm_code (int): The GRBL alarm code to validate.
    Returns:
        bool: True if the alarm code is valid, False otherwise.
    """
    # Check if the alarm code is in the list of valid alarm codes
    if alarm_code in grbl_alarm_codes:
        return True
    else:
        return False


def validate_command_or_gcode(command_or_gcode):
    """
    Validate a given GRBL command or G-code.
    Parameters:
        command_or_gcode (str): The GRBL command or G-code to validate.
    Returns:
        bool: True if the command or G-code is valid, False otherwise.
    """
    # Check if the input is a valid G-code
    if validate_gcode(command_or_gcode):
        return True

    # Check if the input is a valid GRBL command
    if validate_command(command_or_gcode):
        return True

    return False
