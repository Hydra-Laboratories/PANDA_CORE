"""Logger for the grbl_cnc_mill package."""

import logging
from pathlib import Path


# Create a logger
def set_up_mill_logger(
    path_to_logs: Path = Path(__file__).parent / "logs",
) -> logging.Logger:
    """Set up the mill logger.

    Args:
    path_to_logs (Path): The path to the logs directory.
    """
    path_to_logs = Path(path_to_logs)
    if not path_to_logs.exists():
        path_to_logs.mkdir(
            parents=True, exist_ok=True
        )  # Ensure the directory is created
    logger = logging.getLogger("grbl_cnc_mill")
    if not logger.hasHandlers():
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s&%(name)s&%(levelname)s&%(module)s&%(funcName)s&%(lineno)d&%(message)s"
        )
        system_handler = logging.FileHandler(path_to_logs / "mill_control.log")
        system_handler.setFormatter(formatter)
        logger.addHandler(system_handler)
        # Add a console handler for debugging
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.ERROR)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def set_up_command_logger(
    path_to_logs: Path = Path(__file__).parent / "logs/",
) -> logging.Logger:
    """Set up the command logger.

    Args:
    path_to_logs (Path): The path to the logs directory.
    """
    path_to_logs = Path(path_to_logs)
    if not path_to_logs.exists():
        path_to_logs.mkdir(
            parents=True, exist_ok=True
        )  # Ensure the directory is created
    logger = logging.getLogger("grbl_cnc_mill_cmds")
    if not logger.hasHandlers():
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(message)s")
        system_handler = logging.FileHandler(path_to_logs / "command.log")
        system_handler.setFormatter(formatter)
        logger.addHandler(system_handler)

    return logger
