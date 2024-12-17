import time
import logging
import os
from datetime import datetime, timedelta

from rich.logging import RichHandler


def setup_logging(log_file='logs/main.log', level=logging.INFO) -> logging.Logger:
    """
    Sets up logging to file and console with consistent formatting.

    Args:
        log_file (str): The log file path.
        level (int): The logging level (e.g., logging.INFO).
    
    Returns:
        logging.Logger: Configured logger instance.
    """
    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    os.makedirs(log_dir, exist_ok=True)

    # Clear any existing handlers
    logging.getLogger().handlers = []

    # Create the logger
    logger = logging.getLogger()
    logger.setLevel(level)

    # Rich console handler (for console output)
    rich_handler = RichHandler(
        show_level=True,
        show_time=True, 
        log_time_format='%Y-%m-%d %H:%M:%S',
        omit_repeated_times=False,
        rich_tracebacks=True, 
        show_path=True,
        tracebacks_show_locals=False
    )
    rich_handler.setLevel(level)

    # Define the ISO8601 formatter for file logs
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s [%(module)s]: %(message)s', 
        datefmt='%Y-%m-%dT%H:%M:%SZ'
    )

    # Use UTC time for logs
    logging.Formatter.converter = time.gmtime  # Ensure UTC time

    # File handler (for log file output)
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    # Add handlers to the logger
    logger.addHandler(rich_handler)
    logger.addHandler(file_handler)

    return logger
