Data Source Name: Syncro RMM Platform Data (Tickets & Customers via API)

A. Identification & Origin:

Unique Identifier(s):

Syncro Ticket:
id (Integer): The primary unique internal database identifier. Consistently used for API calls requiring a specific ticket (e.g., fetching its comments).
number (String/Integer): The unique, human-readable ticket identifier, often used for reference.
Syncro Customer:
id (Integer): The primary unique identifier for a customer (often referred to as customer_id when present on other objects like tickets). This was the target for customer lookup processes.
Syncro Contact (as referenced within a ticket):
contact_id (Integer): Key identifier for the associated contact if present on the ticket object.
Source System Detail & API Endpoint(s):

Data originates from the Syncro RMM platform via its REST API.
For fetching lists of Tickets: GET /api/v1/tickets was primarily used.
Supported filtering (e.g., by customer_id, created_after).
Handled pagination (API response included a meta object with total_pages, current_page).
For fetching Comments for a specific Ticket: GET /api/v1/tickets/{id}/comments was sometimes used as a dedicated endpoint, where {id} is the ticket's unique integer ID. (Note: The main /tickets endpoint often returns comments nested within each ticket object as well).
For Customer ID Lookup/Details:
GET /api/v1/customers/autocomplete: Used for an initial, faster search for customer IDs based on a name query.
GET /api/v1/customers: Used as a fallback to fetch all customers if autocomplete was insufficient, or for retrieving full customer lists.
Format:

Raw data from all interacted Syncro API endpoints was JSON.
Responses for lists (e.g., /tickets, /customers) typically involved a main JSON object containing an array of the primary data objects (e.g., a tickets array, a customers array) and often a meta object for pagination.
B. Core Content & Meaning:

Primary Descriptive Fields for a Syncro Ticket:

The ticket's subject.
The body of each comment within the ticket's comments array provided the narrative and history.
Key Data Fields Processed from a Syncro Ticket Object (for various goals):

Comprehensive/Detailed Processing & CDM Conversion:
id (Ticket's unique integer ID)
number (Human-readable ticket number)
subject (Title)
status
priority
problem_type
customer_id
contact_id
customer_business_then_name (Often mapped to customer_name)
contact_fullname (Often mapped to contact_name)
created_at, updated_at, resolved_at, due_date (Timestamps)
user (Nested object containing details of the assigned user: id, full_name, email)
comments (Array of comment objects, detailed in Section D)
billing_status (If available)
"Barebones" / Trimmed Version (often for LLM consumption, e.g., trim_tickets.py output):
number
subject
customer_name (derived from customer_business_then_name)
comments_for_llm: A simplified array of key comment details, typically {"created_at": "...", "body": "..."} for each comment.
Key Data Fields Processed from a Syncro Customer Object (for ID lookup/reference):

id: The unique integer customer identifier (this was the primary target for lookup).
business_name: The primary field used for name-based lookups.
C. Key Entities & Context:

People/Organizations:

Customers: Linked to tickets via customer_id. Customer name typically from customer_business_then_name on the ticket or business_name from a customer object.
Contacts: Linked to tickets via contact_id if present. Contact name from contact_fullname on the ticket.
Assigned User (Technician): Details (ID, name, email) found within a nested user object on the ticket.
Timestamps:

Ticket-level: created_at, updated_at, resolved_at, due_date. Essential for tracking lifecycle and sorting.
Comment-level: created_at for each comment.
Status & Priority:

Status: Explicitly available via the status field on the ticket object (e.g., "New", "Resolved").
Priority: Explicitly available via the priority field (e.g., "Low", "High").
(Note: While present in raw Syncro data, extraction of status/priority wasn't a focus for all processing scripts, e.g., trim_tickets.py focused on other fields).
Valuable Information in Comments (beyond raw text):

Comment Metadata for Type Deduction: A key processing step involved analyzing comment metadata fields (not just parsing comment body text) to infer the comment's type (e.g., "Email", "Private Note", "SMS"). Fields like comment subject, tech, hidden, destination_emails, email_sender, sms_body were crucial for this. This deduced type was often stored (e.g., as rmm_comment_type_deduced in the CDM).
D. Structure & Relationships:

Sub-Components (Ticket Comments):

Universally, ticket comments are structured as a nested array of JSON objects within the main ticket object, typically under a comments key.
Essential fields defining a comment object typically include: id (comment's unique ID), body (text content), subject (comment's own subject), tech (creator/system identifier), user_id (author ID), created_at (Timestamp), hidden (Boolean). Other fields like destination_emails, email_sender, sms_body exist for specific comment types.
Parent/Child Relationships Between Tickets:

The specific API interactions and processing scripts discussed (primarily focused on /tickets list endpoint or individual ticket data) did not explicitly detail handling or representation of parent/child relationships between Syncro tickets.
Sequential Ordering:

Comments within a ticket are inherently ordered, usually by creation time.
E. Goals for Processing Syncro Data (Synthesized from all Agent Zero Contexts):

Comprehensive Data Retrieval & Understanding:

Fetch detailed Syncro RMM ticket information, including all attributes, linked entities (customer, contact, user), and importantly, all associated comments with their full metadata.
Data Transformation for Standardization (CDM):

A core objective was to transform raw Syncro ticket data into a standardized Canonical Data Model (CDM). This aimed to create a consistent, unified representation of ticket data, enabling easier comparison and integration with data from other sources (like notes.json).
Data Trimming/Simplification for Specific Use Cases (e.g., LLMs):

Produce "barebones" or simplified versions of ticket data (e.g., trim_tickets.py creating comments_for_llm). This was often to prepare data for efficient consumption by Large Language Models or other specific downstream processes.
Customer Identification & Data Augmentation:

Accurately identify and retrieve the authoritative Syncro customer_id for customer names found in various datasets (including external JSON files or data derived from other sources). This involved using Syncro's customer API endpoints (/customers/autocomplete, /customers) and was crucial for linking disparate data correctly within the Syncro ecosystem.
Correlation & Comparison:

Enable the correlation and comparison of Syncro tickets with tickets/notes from other systems (e.g., notes.json) using semantic analysis (LLMs, embeddings) to identify related items or potential duplicates.
Identify potential duplicate tickets within the Syncro RMM system itself.
Linking Data:

Ensure fetched comments were correctly associated with their parent ticket.
Link external data points or records to their correct Syncro Customer ID.
