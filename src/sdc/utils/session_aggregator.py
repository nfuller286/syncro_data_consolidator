# -*- coding: utf-8 -*-
"""Utility for aggregating individual SessionSegments into complete Session objects."""

import datetime
from typing import Any, List, Optional

from sdc.models.session_v2 import Session, SessionSegment
from sdc.utils.session_builder import build_session


def _get_key_value(segment: SessionSegment, key: str) -> Any:
    """
    Safely gets a value from a segment, checking top-level attributes first,
    then falling back to the metadata dictionary.
    """
    if hasattr(segment, key):
        return getattr(segment, key)
    return segment.metadata.get(key)


def group_segments_by_time_gap_and_keys(
    segments: List[SessionSegment],
    time_gap: datetime.timedelta,
    grouping_keys: Optional[List[str]] = None
) -> List[List[SessionSegment]]:
    """
    Groups a list of SessionSegments into sessions based on time gaps and key changes.

    Args:
        segments: A list of SessionSegment objects.
        time_gap: The maximum time allowed between segments in the same session.
        grouping_keys: A list of keys to check for value changes. A change in any
                       key's value will start a new session. Checks segment attributes
                       first, then metadata.

    Returns:
        A list of lists, where each inner list is a group of segments
        representing a single logical session.
    """
    if not segments:
        return []

    # The function expects pre-sorted segments, but a sort here is a good safeguard.
    segments.sort(key=lambda s: s.start_time_utc)

    sessions: List[List[SessionSegment]] = []
    current_session_segments: List[SessionSegment] = [segments[0]]

    for i in range(1, len(segments)):
        prev_segment = segments[i - 1]
        curr_segment = segments[i]

        time_gap_exceeded = (curr_segment.start_time_utc - prev_segment.end_time_utc) > time_gap

        keys_changed = False
        if grouping_keys:
            for key in grouping_keys:
                if _get_key_value(curr_segment, key) != _get_key_value(prev_segment, key):
                    keys_changed = True
                    break

        if time_gap_exceeded or keys_changed:
            sessions.append(current_session_segments)
            current_session_segments = [curr_segment]
        else:
            current_session_segments.append(curr_segment)

    if current_session_segments:
        sessions.append(current_session_segments)

    return sessions


def transform_grouped_segments_to_session(**kwargs) -> Session:
    """Convenience wrapper around session_builder.build_session."""
    return build_session(**kwargs)