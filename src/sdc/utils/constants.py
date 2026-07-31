from datetime import datetime, timezone
import uuid

UNDEFINED_TIMESTAMP = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

# --- Session processing_status vocabulary ---
# The canonical set of values for SessionMeta.processing_status. These were
# previously bare string literals scattered across the ingestors, the linker
# and the analyzer; centralising them here keeps the spelling consistent
# (Title Case With Spaces) and makes the state machine greppable.
STATUS_NEEDS_LINKING = "Needs Linking"   # Ingested, awaiting the customer linker.
STATUS_LINKED = "Linked"                 # Successfully linked to a Syncro customer.
STATUS_COMPLETE = "Complete"             # Terminal success for sources that never link.
STATUS_REVIEWED = "Reviewed"             # Manually reviewed by a human.
STATUS_NO_MATCH_FOUND = "No Match Found" # Linker ran, found no match. Retryable.
STATUS_LINKING_FAILED = "Linking Failed" # Linker hit a genuine error. Retryable.

# Historical spelling of STATUS_LINKING_FAILED. Sessions written before the
# rename still carry this on disk, so retry runs must still recognise it.
LEGACY_STATUS_ERROR = "error"

# Statuses the customer linker will pick up on a normal run.
LINKABLE_STATUSES = frozenset({STATUS_NEEDS_LINKING})

# Additional statuses the linker will pick up when --retry is passed. These
# are terminal-but-not-successful outcomes: re-running is worthwhile once the
# customer cache has been refreshed or an LLM provider has been configured.
RETRYABLE_LINK_STATUSES = frozenset({
    STATUS_NO_MATCH_FOUND,
    STATUS_LINKING_FAILED,
    LEGACY_STATUS_ERROR,
})

# Statuses eligible for LLM analysis. Analysis summarises session *content*,
# which is independent of whether a customer link was established - an
# unlinked ScreenConnect session still describes real billable work, and
# SillyTavern sessions are never linkable at all.
ANALYZABLE_STATUSES = frozenset({
    STATUS_LINKED,
    STATUS_COMPLETE,
    STATUS_REVIEWED,
    STATUS_NO_MATCH_FOUND,
})

# ScreenConnect Constants
SCREENCONNECT_NAMESPACE_OID = uuid.uuid5(uuid.NAMESPACE_DNS, 'screenconnect.syncromsp.com')
SCREENCONNECT_DEFAULT_API_LIMIT = 100
SCREENCONNECT_QUERY_FIELDS = [
      "ProcessType",
      "SessionSessionType",
      "SessionName",
      "ParticipantName",
      "ConnectedTime",
      "DisconnectedTime",
      "DurationSeconds",
      "ConnectionID",
      "SessionCustomProperty1",
      "SessionSessionID",
      "ClientType"
]
