"""Helper module for reading raw keypresses without requiring Enter.

Uses tty/termios (Unix) to put the terminal in raw mode and read
single keypresses, including multi-byte arrow key escape sequences.
"""

import sys
import tty
import termios


def read_keypress() -> str:
    """Read a single keypress and return a normalized string.

    Returns one of:
        "UP", "DOWN", "LEFT", "RIGHT" — arrow keys
        "Z", "X", "Q"                 — letter keys (uppercased)
        raw character                  — anything else
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)

        if ch == "\x1b":
            seq = sys.stdin.read(2)
            arrow_map = {
                "[A": "UP",
                "[B": "DOWN",
                "[C": "RIGHT",
                "[D": "LEFT",
            }
            return arrow_map.get(seq, ch)

        return ch.upper()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
