from datetime import datetime, timezone
import uuid

UNDEFINED_TIMESTAMP = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

# ScreenConnect Constants
SCREENCONNECT_NAMESPACE_OID = uuid.uuid5(uuid.NAMESPACE_DNS, 'screenconnect.syncromsp.com')
SCREENCONNECT_DEFAULT_API_LIMIT = 100
SCREENCONNECT_DEFAULT_FILTER_EXPRESSION = "ConnectionEndUniversal > $TIMESTAMP"
SCREENCONNECT_QUERY_FIELDS = [
    "SessionSessionID", 
    "ProcessType", 
    "SessionSessionType", 
    "SessionName", 
    "ParticipantName",
    "ConnectedTime", 
    "DisconnectedTime", 
    "DurationSeconds", 
    "ClientType", 
    "NetworkAddress",
    "SessionCustomProperty1", 
    "SessionCustomProperty4", 
    "SessionCustomProperty5"
]
