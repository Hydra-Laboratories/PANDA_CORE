"""Helper module for reading raw keypresses without requiring Enter.

Cross-platform: uses tty/termios on Unix, msvcrt on Windows.
"""

import sys
import time

_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    import msvcrt
else:
    import select
    import tty
    import termios

_ARROW_MAP_UNIX = {
    "[A": "UP",
    "[B": "DOWN",
    "[C": "RIGHT",
    "[D": "LEFT",
}

# Windows arrow keys: msvcrt returns b'\xe0' or b'\x00' followed by a scan code
_ARROW_MAP_WINDOWS = {
    b"H": "UP",
    b"P": "DOWN",
    b"M": "RIGHT",
    b"K": "LEFT",
}


# ── Unix implementation ───────────────────────────────────────────────────────

def _unix_read_one_key():
    """Read a single key. Must already be in raw mode."""
    ch = sys.stdin.read(1)
    if ch == "\x1b":
        seq = sys.stdin.read(2)
        return _ARROW_MAP_UNIX.get(seq, ch)
    return ch.upper()


def _unix_read_keypress_batch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        key = _unix_read_one_key()
        count = 1

        while select.select([sys.stdin], [], [], 0.03)[0]:
            next_key = _unix_read_one_key()
            if next_key == key:
                count += 1
            else:
                break

        return key, count
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


# ── Windows implementation ────────────────────────────────────────────────────

def _windows_read_one_key():
    """Read a single key using msvcrt."""
    ch = msvcrt.getch()
    if ch in (b"\xe0", b"\x00"):
        scan = msvcrt.getch()
        return _ARROW_MAP_WINDOWS.get(scan, "")
    return ch.decode("ascii", errors="ignore").upper()


def _windows_read_keypress_batch():
    key = _windows_read_one_key()
    count = 1

    # Drain buffered repeats (give 30ms for more input to arrive)
    deadline = time.monotonic() + 0.03
    while time.monotonic() < deadline:
        if msvcrt.kbhit():
            next_key = _windows_read_one_key()
            if next_key == key:
                count += 1
                deadline = time.monotonic() + 0.03
            else:
                break
        else:
            time.sleep(0.005)

    return key, count


# ── Public API ────────────────────────────────────────────────────────────────

def read_keypress() -> str:
    """Read a single keypress and return a normalized string."""
    if _IS_WINDOWS:
        return _windows_read_one_key()
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return _unix_read_one_key()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def read_keypress_batch() -> tuple:
    """Read a keypress, then drain any buffered repeats of the same key.

    When a key is held down, the terminal generates repeated key events.
    This function consumes all buffered repeats and returns the key plus
    a count, so the caller can send a single larger move.

    Returns:
        (key_name, count) where count >= 1.
    """
    if _IS_WINDOWS:
        return _windows_read_keypress_batch()
    return _unix_read_keypress_batch()
