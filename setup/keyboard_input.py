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


def _unix_flush_stdin():
    """Discard any buffered stdin without blocking."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while select.select([sys.stdin], [], [], 0)[0]:
            sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _unix_read_keypress_batch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        key = _unix_read_one_key()
        count = 1

        # 150ms timeout catches held-key repeats (typical repeat rate 30-100ms)
        while select.select([sys.stdin], [], [], 0.15)[0]:
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


def _windows_flush_stdin():
    """Discard any buffered stdin without blocking."""
    while msvcrt.kbhit():
        msvcrt.getch()


def _windows_read_keypress_batch():
    key = _windows_read_one_key()
    count = 1

    # 150ms timeout catches held-key repeats
    deadline = time.monotonic() + 0.15
    while time.monotonic() < deadline:
        if msvcrt.kbhit():
            next_key = _windows_read_one_key()
            if next_key == key:
                count += 1
                deadline = time.monotonic() + 0.15
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


def flush_stdin() -> None:
    """Discard any buffered stdin without blocking.

    Call this after a blocking operation (e.g. gantry.move_to) to throw
    away keypresses that accumulated while the operation was running.
    """
    if _IS_WINDOWS:
        _windows_flush_stdin()
    else:
        _unix_flush_stdin()
