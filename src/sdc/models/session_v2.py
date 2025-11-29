from __future__ import annotations
import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# ===================================================================
#  Innermost Model: The building block for individual events
# ===================================================================

class SessionSegment(BaseModel):
    """Represents the smallest possible unit of raw data, one atomic event."""
    segment_id: str = Field(..., description="A unique ID for this specific event.")
    start_time_utc: datetime.datetime
    end_time_utc: datetime.datetime
    type: str = Field(..., description="The kind of event, e.g., 'ChatMessage', 'RemoteConnection', 'TicketComment'")
    author: Optional[str] = Field(None, description="Who or what created the event.")
    content: Optional[str] = Field(None, description="The text content of the event, if any.")
    metadata: Dict = Field(default_factory=dict, description="A flexible bucket for any other source-specific raw data relevant to this specific segment.")


# ===================================================================
#  Component Models: The main sections of the Session
# ===================================================================

class SessionMeta(BaseModel):
    """Contains metadata about the Session record itself, used for system tracking."""
    session_id: str = Field(..., description="A unique, deterministic hash of core data identifying this session.")
    schema_version: str = Field(..., description="The version of this model, e.g., '2.0'.")
    source_system: str = Field(..., description="The system the data came from, e.g., 'ScreenConnect', 'SyncroTicket'.")
    source_identifiers: List[str] = Field(..., description="The specific source filename(s) or API IDs.")
    processing_status: str = Field(..., description="The workflow state, e.g., 'Needs Linking', 'Linked', 'Reviewed'.")
    processing_log: List[str] = Field(default_factory=list, description="A log of processing steps applied to this session, e.g., 'customer_linker_v2.1'.")
    ingestion_timestamp_utc: datetime.datetime
    last_updated_timestamp_utc: datetime.datetime

class SessionContext(BaseModel):
    """Contains information linking the Session to business entities like customers and projects."""
    customer_id: Optional[int] = Field(None, description="The authoritative Syncro customer ID, populated by the linker.")
    customer_name: Optional[str] = Field(None, description="The guessed name from the source, or the authoritative name after linking.")
    contact_id: Optional[int] = Field(None, description="The authoritative Syncro contact ID, populated by the linker.")
    contact_name: Optional[str] = Field(None, description="The guessed name from the source, or the authoritative name after linking.")
    links: List[str] = Field(default_factory=list, description="A list of user-added keywords for project grouping.")

class SessionInsights(BaseModel):
    """Contains calculated or generated information derived from the session's content."""
    session_start_time_utc: datetime.datetime
    session_end_time_utc: datetime.datetime
    session_duration_minutes: int
    source_title: Optional[str] = Field(None, description="The title as it appeared in the source system (e.g., ticket subject).")
    llm_generated_title: Optional[str] = Field(None, description="A placeholder for a future AI-generated title.")
    llm_generated_category: Optional[str] = Field(None, description="A category assigned by an LLM processor.")
    generated_summaries: Dict[str, str] = Field(default_factory=dict, description="A flexible dictionary for multiple summary types (e.g., 'invoice', 'detailed').")
    structured_llm_results: Dict[str, Any] = Field(default_factory=dict, description="A flexible dictionary for storing structured JSON results from LLM analysis.")
    user_notes: str = Field("", description="A dedicated field for your manual notes and summaries.")


# ===================================================================
#  Top-Level Root Model: The complete Session object
# ===================================================================

class Session(BaseModel):
    """A complete, standardized record of a single, continuous activity from one source."""
    meta: SessionMeta
    context: SessionContext
    insights: SessionInsights
    segments: List[SessionSegment]