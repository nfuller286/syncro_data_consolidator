# -*- coding: utf-8 -*-
"""Standardized logging utility for the SDC project."""

import logging
import os
from typing import Any, Dict

def get_sdc_logger(name: str, config: Dict[str, Any]) -> logging.Logger:
    """Configures and returns a logger instance based on application config.

    This function sets up a logger with handlers for file and/or terminal
    output based on the provided configuration dictionary. It ensures that
    handlers are not added multiple times to the same logger instance.

    Args:
        name: The name for the logger, typically __name__ from the calling module.
        config: The application's configuration dictionary, expected to contain
                a 'logging' section.

    Returns:
        A configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    # If handlers are already configured for this logger, don't add them again
    if logger.hasHandlers():
        return logger

    # Safely get logging configuration with defaults
    log_config = config.get('logging', {})
    log_level_str = log_config.get('log_level', 'INFO').upper()
    log_file_path = log_config.get('log_file_path', '/a0/syncro_data_consolidator/logs/sdc.log')
    log_to_terminal = log_config.get('log_to_terminal', True)

    # Get the logging level object from the string
    log_level = getattr(logging, log_level_str, logging.INFO)
    logger.setLevel(log_level)

    # Create a standard formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Always configure the file handler
    if log_file_path:
        try:
            # Ensure the directory for the log file exists
            log_dir = os.path.dirname(log_file_path)
            os.makedirs(log_dir, exist_ok=True)

            file_handler = logging.FileHandler(log_file_path)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (OSError, IOError) as e:
            # Fallback to logging an error to the console if file handler fails
            print(f"Error setting up file logger at {log_file_path}: {e}")

    # Configure the stream handler for terminal output if enabled
    if log_to_terminal:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    # If no handlers were added at all (e.g., file path is null and terminal is false)
    # add a NullHandler to prevent 'No handlers could be found' warnings.
    if not logger.hasHandlers():
        logger.addHandler(logging.NullHandler())

    return logger

