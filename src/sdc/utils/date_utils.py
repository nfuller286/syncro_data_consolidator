# -*- coding: utf-8 -*-
"""Utility functions for parsing and handling dates and times."""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

# Use the more flexible 'parse' instead of the strict 'isoparse'
from dateutil.parser import parse

from sdc.utils.sdc_logger import get_sdc_logger

def parse_datetime_utc(
    date_string: Optional[str],
    config: Dict[str, Any],
    default_on_error: Optional[datetime] = None
) -> Optional[datetime]:
    """
    Parses a date string into a timezone-aware datetime object in UTC.

    This function handles various common formats and ensures the final
    datetime object is consistently in UTC.

    Args:
        date_string: The string representation of the date to parse.
        config: The application's configuration dictionary for logging.
        default_on_error: A datetime object to return if parsing fails.
                          If None, returns None on failure.

    Returns:
        A timezone-aware datetime object in UTC, or None if parsing fails
        or the input string is empty (unless a default is provided).
    """
    logger = get_sdc_logger(__name__, config)

    if not date_string:
        logger.debug("Received an empty or None date_string, returning default_on_error.")
        return default_on_error

    try:
        # Use dateutil.parser.parse for robust, flexible parsing
        dt_object = parse(date_string)

        # If the datetime object is naive (no timezone), assume UTC.
        if dt_object.tzinfo is None:
            return dt_object.replace(tzinfo=timezone.utc)
        # If it has timezone info, convert it to UTC to standardize.
        return dt_object.astimezone(timezone.utc)

    except (ValueError, TypeError, AttributeError) as e:
        logger.warning(f"Failed to parse date string: '{date_string}'. Error: {e}. Returning default_on_error.")
        return default_on_error

def get_past_datetime_str(days: int) -> str:
    """
    Calculates a datetime in the past and returns it as a formatted string.

    Args:
        days: The number of days in the past to calculate.

    Returns:
        An ISO-like formatted string for the calculated past datetime in UTC.
    """
    past_datetime = datetime.now(timezone.utc) - timedelta(days=days)
    return past_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')
