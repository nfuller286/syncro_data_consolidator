# -*- coding: utf-8 -*-
"""Utility for building V2 Session objects consistently."""

import datetime
import uuid
from typing import List, Optional

from sdc.models.session_v2 import (Session, SessionContext, SessionInsights,
                                   SessionMeta, SessionSegment)


def create_session_meta(
    source_system: str,
    source_identifiers: List[str],
    processing_status: str = "Needs Linking"
) -> SessionMeta:
    """Handles the default instantiation of SessionMeta."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return SessionMeta(
        session_id=str(uuid.uuid4()),
        schema_version="2.0",
        source_system=source_system,
        source_identifiers=source_identifiers,
        processing_status=processing_status,
        ingestion_timestamp_utc=now,
        last_updated_timestamp_utc=now
    )

def create_session_context(
    customer_name: Optional[str] = None,
    contact_name: Optional[str] = None,
    customer_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    links: Optional[List[str]] = None
) -> SessionContext:
    """Handles default instantiation of SessionContext."""
    return SessionContext(
        customer_name=customer_name,
        contact_name=contact_name,
        customer_id=customer_id,
        contact_id=contact_id,
        links=links or []
    )

def create_session_insights(
    session_start_time_utc: datetime.datetime,
    session_end_time_utc: datetime.datetime,
    source_title: Optional[str] = None
) -> SessionInsights:
    """Handles default instantiation of SessionInsights, including duration calculation."""
    duration_minutes = 0
    if session_start_time_utc and session_end_time_utc and session_end_time_utc > session_start_time_utc:
        duration_minutes = int((session_end_time_utc - session_start_time_utc).total_seconds() / 60)

    return SessionInsights(
        session_start_time_utc=session_start_time_utc,
        session_end_time_utc=session_end_time_utc,
        session_duration_minutes=duration_minutes,
        source_title=source_title
    )

def build_session(
    segments: List[SessionSegment],
    source_system: str,
    source_identifiers: List[str],
    customer_name: Optional[str] = None,
    contact_name: Optional[str] = None,
    customer_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    source_title: Optional[str] = None,
    processing_status: str = "Needs Linking",
    links: Optional[List[str]] = None
) -> Session:
    """
    Orchestrates the creation of a complete Session object.

    Calculates start and end times from segments and uses helper functions
    to build the final Session.
    """
    if not segments:
        raise ValueError("Cannot build a session with no segments.")

    start_time = min(s.start_time_utc for s in segments)
    end_time = max(s.end_time_utc for s in segments)

    meta = create_session_meta(source_system, source_identifiers, processing_status)
    context = create_session_context(customer_name, contact_name, customer_id, contact_id, links)
    insights = create_session_insights(start_time, end_time, source_title)

    return Session(meta=meta, context=context, insights=insights, segments=segments)