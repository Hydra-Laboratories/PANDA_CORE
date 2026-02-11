"""Status codes for the CNC mill."""

from enum import Enum
from .exceptions import CNCMillException


class Status(Enum):
    """Status of the CNC mill."""

    DISCONNECTED = "Disconnected"
    CONNECTING = "Connecting"
    IDLE = "Idle"
    RUN = "Run"
    HOLD = "Hold"
    DOOR = "Door"
    HOME = "Home"
    ALARM = "Alarm"
    CHECK = "Check"
    JOG = "Jog"
    QUEUE = "Queue"
    COOLING = "Cooling"
    AUTOHOLD = "AutoHold"


class AlarmStatus(Enum):
    """Alarm status of the CNC mill."""

    ALARM1 = "Hard limit triggered. Position Lost."
    ALARM2 = "Soft limit alarm, position kept. Unlock is Safe."
    ALARM3 = "Reset while in motion. Position lost."
    ALARM4 = "Probe fail. Probe not in expected initial state."
    ALARM5 = "Probe fail. Probe did not contact the work."
    ALARM6 = "Homing fail. The active homing cycle was reset."
    ALARM7 = "Homing fail. Door opened during homing cycle."
    ALARM8 = "Homing fail. Pull off failed to clear limit switch."
    ALARM9 = "Homing fail. Could not find limit switch."

    def raise_exception(self):
        """Raise an exception with the error message."""
        raise CNCMillException(self.value)


class ErrorCodes(Enum):
    """Alarm status of the CNC mill."""

    ERROR1 = "GCode Command letter was not found."
    ERROR2 = "GCode Command value invalid or missing."
    ERROR3 = "Grbl '$' not recognized or supported."
    ERROR4 = "Negative value for an expected positive value."
    ERROR5 = "Homing fail. Homing not enabled in settings."
    ERROR6 = "Min step pulse must be greater than 3usec."
    ERROR7 = "EEPROM read failed. Default values used."
    ERROR8 = "Grbl '$' command Only valid when Idle."
    ERROR9 = "GCode commands invalid in alarm or jog state."
    ERROR10 = "Soft limits require homing to be enabled."
    ERROR11 = "Max characters per line exceeded. Ignored."
    ERROR12 = "Grbl '$' setting exceeds the maximum step rate."
    ERROR13 = "Safety door opened and door state initiated."
    ERROR14 = "Build info or start-up line > EEPROM line length."
    ERROR15 = "Jog target exceeds machine travel, ignored."
    ERROR16 = "Jog Cmd missing '=' or has prohibited GCode."
    ERROR17 = "Laser mode requires PWM output."
    ERROR20 = "Unsupported or invalid GCode command."
    ERROR21 = "> 1 GCode command in a modal group in block."
    ERROR22 = "Feed rate has not yet been set or is undefined."
    ERROR23 = "GCode command requires an integer value."
    ERROR24 = "> 1 GCode command using axis words found."
    ERROR25 = "Repeated GCode word found in block."
    ERROR26 = "No axis words found in command block."
    ERROR27 = "Line number value is invalid."
    ERROR28 = "GCode Cmd missing a required value word."
    ERROR29 = "G59.x WCS are not supported."
    ERROR30 = "G53 only valid with G0 and G1 motion modes."
    ERROR31 = "Unneeded Axis words found in block."
    ERROR32 = "G2/G3 arcs need >= 1 in-plane axis word."
    ERROR33 = "Motion command target is invalid."
    ERROR34 = "Arc radius value is invalid."
    ERROR35 = "G2/G3 arcs need >= 1 in-plane offset word."
    ERROR36 = "Unused value words found in block."
    ERROR37 = "G43.1 offset not assigned to tool length axis."
    ERROR38 = "Tool number greater than max value."

    def raise_exception(self):
        """Raise an exception with the error message."""
        raise CNCMillException(self.value)
