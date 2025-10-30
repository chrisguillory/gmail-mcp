"""Pydantic models for Gmail MCP server with strict validation."""

import pydantic


class BaseModel(pydantic.BaseModel):
    """Base model with strict validation - no extra fields, all fields required unless Optional."""

    model_config = pydantic.ConfigDict(extra='forbid', strict=True)


class AttachmentInfo(BaseModel):
    """Metadata for a Gmail attachment."""

    filename: str
    attachment_id: str
    mime_type: str
    size_bytes: int


class DownloadedAttachment(BaseModel):
    """Information about a downloaded attachment saved to temp storage."""

    path: str  # Absolute path to temp file
    filename: str  # Original filename
    size_bytes: int
    mime_type: str
    message_id: str
    attachment_id: str


class EmailMetadata(BaseModel):
    """Core metadata for an email message."""

    id: str
    thread_id: str
    subject: str
    from_addr: str  # 'from' is Python keyword
    to_addr: str  # 'to' for consistency
    date: str  # Formatted date string
    labels: list[str]
    has_attachments: bool
    web_url: str


class EmailDownloadResult(BaseModel):
    """Result of downloading an email to temp file."""

    path: str  # Path to downloaded markdown file
    size_bytes: int  # Size of downloaded file
    metadata: EmailMetadata  # Full email metadata


class ThreadDownloadResult(BaseModel):
    """Result of downloading a thread to temp file."""

    path: str  # Path to downloaded markdown file
    size_bytes: int  # Size of downloaded file
    message_count: int  # Number of messages in thread
    thread_id: str
    subject: str  # Subject of first message
    date_range: str  # "YYYY-MM-DD to YYYY-MM-DD" or single date


class SearchResult(BaseModel):
    """Result of a search operation."""

    path: str  # Path to downloaded markdown file with all results
    size_bytes: int  # Size of downloaded file
    match_count: int  # Number of matching emails
    query: str  # The search query that was executed
    metadata_list: list[EmailMetadata]  # Metadata for all matching emails


class LabelInfo(BaseModel):
    """Information about a Gmail label."""

    id: str
    name: str
    type: str  # 'system' or 'user'
    message_list_visibility: str | None = None
    label_list_visibility: str | None = None


class LabelOperationResult(BaseModel):
    """Result of a label add/remove operation."""

    message_id: str
    subject: str
    label_name: str
    label_id: str
    operation: str  # 'added' or 'removed'


class DraftCreatedResult(BaseModel):
    """Result of creating a draft email."""

    draft_id: str
    to: str
    subject: str
    body_preview: str  # First 200 chars
    cc: str | None = None
    bcc: str | None = None


class EmailSentResult(BaseModel):
    """Result of sending an email."""

    message_id: str
    to: str
    subject: str
    body_preview: str  # First 200 chars
    cc: str | None = None
    bcc: str | None = None
