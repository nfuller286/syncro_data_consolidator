# -*- coding: utf-8 -*-
"""Utility functions for parsing and handling dates and times."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Use the more flexible 'parse' instead of the strict 'isoparse'
from dateutil.parser import parse

from sdc.utils.sdc_logger import get_sdc_logger

def parse_datetime_utc(date_string: Optional[str], config: Dict[str, Any]) -> Optional[datetime]:
    """
    Parses a date string into a timezone-aware datetime object in UTC.

    This function handles various common formats and ensures the final
    datetime object is consistently in UTC.

    Args:
        date_string: The string representation of the date to parse.
        config: The application's configuration dictionary for logging.

    Returns:
        A timezone-aware datetime object in UTC, or None if parsing fails
        or the input string is empty.
    """
    logger = get_sdc_logger(__name__, config)

    if not date_string:
        logger.debug("Received an empty or None date_string, returning None.")
        return None

    try:
        # Use dateutil.parser.parse for robust, flexible parsing
        dt_object = parse(date_string)

        # If the datetime object is naive (no timezone), assume UTC.
        if dt_object.tzinfo is None:
            logger.debug(f"Parsed naive datetime '{date_string}'. Assuming UTC.")
            return dt_object.replace(tzinfo=timezone.utc)
        else:
            # If it has timezone info, convert it to UTC to standardize.
            logger.debug(f"Parsed timezone-aware datetime '{date_string}'. Converting to UTC.")
            return dt_object.astimezone(timezone.utc)

    except (ValueError, TypeError) as e:
        logger.error(f"Failed to parse date string: '{date_string}'. Error: {e}")
        return None
