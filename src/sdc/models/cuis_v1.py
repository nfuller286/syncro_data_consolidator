# -*- coding: utf-8 -*-
"""Pydantic model for the Core Unified Information Structure (CUIS) V1.0.

This file defines the complete data structure for a CUIS item, which is used
by the Syncro Data Consolidator (SDC) to represent normalized information
from various sources.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SdcCore(BaseModel):
    """Metadata used by SDC for internal tracking and management."""
    sdc_cuis_id: UUID = Field(default_factory=uuid4, description="Unique SDC-generated UUID for this CUIS item.")
    sdc_version: Optional[str] = Field(None, description="Version of the SDC system that generated/updated this item.")
    sdc_cuis_schema_version: str = Field("1.0", description="Version of the CUIS schema this item conforms to.")
    sdc_source_system: Optional[str] = Field(None, description="The original system from which the data was ingested.")
    sdc_source_sub_type: Optional[str] = Field(None, description="More specific type within the source system.")
    sdc_source_primary_id: Optional[str] = Field(None, description="Primary unique identifier from the source system.")
    sdc_source_file_path: Optional[str] = Field(None, description="Path to the original source file, if applicable.")
    sdc_ingestion_timestamp_utc: datetime = Field(default_factory=datetime.utcnow, description="ISO 8601 UTC timestamp when SDC first ingested this data.")
    sdc_last_updated_timestamp_utc: datetime = Field(default_factory=datetime.utcnow, description="ISO 8601 UTC timestamp when SDC last updated this CUIS item.")
    sdc_processing_status: Optional[str] = Field("new", description="Current processing status within SDC.")
    sdc_content_embedding_model_name: Optional[str] = Field(None, description="Name of the LLM model used to generate sdc_content_embedding.")
    sdc_content_embedding: List[float] = Field(default_factory=list, description="Vector embedding of the core content.")
    sdc_data_source_agent_override: Optional[str] = Field(None, description="Identifier for the agent/user SDC attributes this record to.")


class CoreContent(BaseModel):
    """Normalized essential content derived from the source."""
    summary_title_or_subject: Optional[str] = Field(None, description="A concise title or subject line for the CUIS item.")
    primary_text_content: Optional[str] = Field(None, description="The main body of text associated with this item.")
    creation_timestamp_utc: Optional[datetime] = Field(None, description="Original creation time of the source event.")
    start_timestamp_utc: Optional[datetime] = Field(None, description="Start time of the activity/event, if applicable.")
    end_timestamp_utc: Optional[datetime] = Field(None, description="End time of the activity/event, if applicable.")
    source_data_updated_at_timestamp_utc: Optional[datetime] = Field(None, description="Timestamp from the source system indicating its last update.")
    duration_seconds: Optional[int] = Field(None, description="Duration of the event in seconds, if applicable.")


class EntitiesInvolved(BaseModel):
    """Information about customers, contacts, assignees, and other actors."""
    syncro_customer_id_guessed: Optional[str] = Field(None, description="Customer ID guessed by SDC before authoritative linking.")
    syncro_customer_name_guessed: Optional[str] = Field(None, description="Customer name guessed by SDC before authoritative linking.")
    syncro_customer_id_authoritative: Optional[int] = Field(None, description="Authoritative Syncro Customer ID after linking.")
    syncro_customer_name_authoritative: Optional[str] = Field(None, description="Authoritative Syncro Customer Name after linking.")
    syncro_contact_id_guessed: Optional[str] = Field(None, description="Contact ID guessed by SDC.")
    syncro_contact_name_guessed: Optional[str] = Field(None, description="Contact name guessed by SDC.")
    syncro_contact_id_authoritative: Optional[int] = Field(None, description="Authoritative Syncro Contact ID after linking.")
    syncro_contact_name_authoritative: Optional[str] = Field(None, description="Authoritative Syncro Contact Name after linking.")
    primary_actor_user_id_source: Optional[int] = Field(None, description="User ID of the primary actor from the source system.")
    primary_actor_user_name_source: Optional[str] = Field(None, description="User name of the primary actor from the source system.")
    primary_actor_user_id_authoritative: Optional[str] = Field(None, description="Standardized/Authoritative User ID.")
    primary_actor_user_name_authoritative: Optional[str] = Field(None, description="Standardized/Authoritative User Name.")
    other_involved_entities: List[Dict[str, Any]] = Field(default_factory=list, description="Array of objects for other entities.")


class Categorization(BaseModel):
    """Fields related to classifying the CUIS item."""
    work_type_guessed: Optional[str] = Field(None, description="Type of work guessed by SDC.")
    work_type_authoritative: Optional[str] = Field(None, description="Confirmed type of work.")
    billable_status_guessed: Optional[str] = Field(None, description="Guessed billable status.")
    billable_status_authoritative: Optional[str] = Field(None, description="Confirmed billable status.")
    original_status_from_source: Optional[str] = Field(None, description="Status as it appeared in the source system.")
    original_priority_from_source: Optional[str] = Field(None, description="Priority as it appeared in the source system.")
    tags_keywords_generated: List[str] = Field(default_factory=list, description="Tags/keywords generated by LLM or rules.")
    tags_keywords_manual: List[str] = Field(default_factory=list, description="Tags/keywords manually added.")


class Link(BaseModel):
    """Represents relationships to other CUIS items or external entities."""
    target_cuis_id: Optional[str] = Field(None, description="sdc_cuis_id of the linked CUIS item.")
    target_external_system: Optional[str] = Field(None, description="Name of the external system if linking to an external entity.")
    target_external_id: Optional[str] = Field(None, description="ID of the entity in the external system.")
    link_type: Optional[str] = Field(None, description="Type of relationship.")
    link_description: Optional[str] = Field(None, description="Optional description of the link.")
    link_timestamp_utc: datetime = Field(default_factory=datetime.utcnow, description="ISO 8601 UTC timestamp when the link was established.")


class CuisEntry(BaseModel):
    """Represents sub-items like ticket comments or individual messages."""
    entry_id_source: Optional[str] = Field(None, description="Unique ID of this sub-entry from the source system.")
    entry_timestamp_utc: Optional[datetime] = Field(None, description="ISO 8601 UTC timestamp for this specific entry.")
    entry_author_name_source: Optional[str] = Field(None, description="Author name from the source for this entry.")
    entry_author_id_source: Optional[str] = Field(None, description="Author ID from the source for this entry.")
    entry_body_text: Optional[str] = Field(None, description="The main text content of this sub-entry.")
    entry_type_source: Optional[str] = Field(None, description="Original type from source (e.g., 'Comment', 'Note').")
    entry_type_deduced: Optional[str] = Field(None, description="Type deduced by SDC (e.g., 'Email', 'Private Note').")
    entry_metadata_source: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata from the source for this entry.")
    entry_order: Optional[int] = Field(None, description="Original order if specified in source.")


class CUISV1(BaseModel):
    """Root model for the Core Unified Information Structure (CUIS) V1.0."""
    sdc_core: SdcCore = Field(default_factory=SdcCore)
    core_content: CoreContent = Field(default_factory=CoreContent)
    entities_involved: EntitiesInvolved = Field(default_factory=EntitiesInvolved)
    categorization: Categorization = Field(default_factory=Categorization)
    links: List[Link] = Field(default_factory=list)
    cuis_entries: List[CuisEntry] = Field(default_factory=list)
    source_specific_details: Dict[str, Any] = Field(default_factory=dict)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            UUID: lambda v: str(v),
            datetime: lambda v: v.isoformat() + 'Z' if v else None
        }
        validate_assignment = True
