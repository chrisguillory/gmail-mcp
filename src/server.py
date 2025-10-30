"""Gmail MCP Server Implementation with file-based responses."""

import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from src.config import settings
from src.gmail import (
    GmailService,
    get_attachment_data,
    get_gmail_service,
    get_labels,
    get_message,
    list_message_attachments,
    list_messages,
    modify_message_labels,
    parse_message_body,
    search_messages,
)
from src.gmail import (
    create_draft as gmail_create_draft,
)
from src.gmail import (
    get_thread as gmail_get_thread,
)
from src.gmail import (
    send_email as gmail_send_email,
)
from src.helpers import (
    build_email_metadata,
    format_email_as_markdown,
    format_thread_as_markdown,
    get_headers_dict,
    sanitize_filename,
    validate_date_format,
)
from src.dual_logger import DualLogger
from src.models import (
    AttachmentInfo,
    DownloadedAttachment,
    DraftCreatedResult,
    EmailDownloadResult,
    EmailSentResult,
    LabelInfo,
    LabelOperationResult,
    SearchResult,
    ThreadDownloadResult,
)

# Global variables for resource management
_temp_dir: tempfile.TemporaryDirectory | None = None
_export_dir: Path | None = None
_gmail_service: GmailService | None = None

EMAIL_PREVIEW_LENGTH = 200


@asynccontextmanager
async def lifespan(server):
    """Manage resources - cleanup on shutdown."""
    global _temp_dir, _export_dir, _gmail_service

    # Initialize temp directory for email downloads
    _temp_dir = tempfile.TemporaryDirectory()
    _export_dir = Path(_temp_dir.name)

    # Initialize Gmail service
    _gmail_service = get_gmail_service(
        credentials_path=settings.credentials_path,
        token_path=settings.token_path,
        scopes=settings.scopes,
    )

    try:
        yield {}
    finally:
        # Cleanup temp directory
        if _temp_dir:
            _temp_dir.cleanup()


mcp = FastMCP(
    'Gmail MCP Server',
    instructions=(
        'Access and interact with Gmail. '
        'You can get messages, threads, search emails, and send or compose new messages.'
    ),
    lifespan=lifespan,
)


# Resources remain the same but now use file-based downloads internally
@mcp.resource('gmail://messages/{message_id}')
def get_email_message(message_id: str) -> str:
    """
    Get the content of an email message by its ID.

    Args:
        message_id: The Gmail message ID

    Returns:
        The formatted email content
    """
    message = get_message(_gmail_service, message_id, user_id=settings.user_id)
    body = parse_message_body(message)
    return format_email_as_markdown(message, message_id, body)


@mcp.resource('gmail://threads/{thread_id}')
def get_email_thread(thread_id: str) -> str:
    """
    Get all messages in an email thread by thread ID.

    Args:
        thread_id: The Gmail thread ID

    Returns:
        The formatted thread content with all messages
    """
    thread = gmail_get_thread(_gmail_service, thread_id, user_id=settings.user_id)
    messages = thread.get('messages', [])

    messages_with_bodies = []
    for message in messages:
        body = parse_message_body(message)
        messages_with_bodies.append((message, body))

    return format_thread_as_markdown(thread, thread_id, messages_with_bodies)


# Tools
@mcp.tool(annotations=ToolAnnotations(title='Create Draft', readOnlyHint=False, idempotentHint=False))
async def create_draft(
    to: str = Field(..., description='Recipient email address'),
    subject: str = Field(..., description='Email subject line'),
    body: str = Field(..., description='Email body content (plain text or HTML)'),
    cc: str | None = Field(None, description='Carbon copy recipients (comma-separated if multiple)'),
    bcc: str | None = Field(None, description='Blind carbon copy recipients (comma-separated if multiple)'),
    ctx: Context = None,
) -> DraftCreatedResult:
    """
    Create a new email draft.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body content
        cc: Carbon copy recipients (optional)
        bcc: Blind carbon copy recipients (optional)
        ctx: MCP context for logging

    Returns:
        DraftCreatedResult with draft ID and details
    """
    logger = DualLogger(ctx)
    await logger.info(f'Creating draft to {to}')

    sender = _gmail_service.users().getProfile(userId=settings.user_id).execute().get('emailAddress')
    draft = gmail_create_draft(
        _gmail_service,
        sender=sender,
        to=to,
        subject=subject,
        body=body,
        user_id=settings.user_id,
        cc=cc,
        bcc=bcc,
    )

    draft_id = draft.get('id')
    await logger.info(f'Draft created with ID: {draft_id}')

    return DraftCreatedResult(
        draft_id=draft_id,
        to=to,
        subject=subject,
        body_preview=body[:EMAIL_PREVIEW_LENGTH] if len(body) > EMAIL_PREVIEW_LENGTH else body,
        cc=cc,
        bcc=bcc,
    )


@mcp.tool(annotations=ToolAnnotations(title='Send Email', readOnlyHint=False, idempotentHint=False))
async def send_email(
    to: str = Field(..., description='Recipient email address'),
    subject: str = Field(..., description='Email subject line'),
    body: str = Field(..., description='Email body content (plain text or HTML)'),
    cc: str | None = Field(None, description='Carbon copy recipients (comma-separated if multiple)'),
    bcc: str | None = Field(None, description='Blind carbon copy recipients (comma-separated if multiple)'),
    ctx: Context = None,
) -> EmailSentResult:
    """
    Compose and send an email.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body content
        cc: Carbon copy recipients (optional)
        bcc: Blind carbon copy recipients (optional)
        ctx: MCP context for logging

    Returns:
        EmailSentResult with message ID and details
    """
    logger = DualLogger(ctx)
    await logger.info(f'Sending email to {to}')

    sender = _gmail_service.users().getProfile(userId=settings.user_id).execute().get('emailAddress')
    message = gmail_send_email(
        _gmail_service,
        sender=sender,
        to=to,
        subject=subject,
        body=body,
        user_id=settings.user_id,
        cc=cc,
        bcc=bcc,
    )

    message_id = message.get('id')
    await logger.info(f'Email sent with ID: {message_id}')

    return EmailSentResult(
        message_id=message_id,
        to=to,
        subject=subject,
        body_preview=body[:EMAIL_PREVIEW_LENGTH] if len(body) > EMAIL_PREVIEW_LENGTH else body,
        cc=cc,
        bcc=bcc,
    )


@mcp.tool(annotations=ToolAnnotations(title='Search Emails', readOnlyHint=True))
async def search_emails(
    from_email: str | None = Field(None, description='Filter by sender email address'),
    to_email: str | None = Field(None, description='Filter by recipient email address'),
    subject: str | None = Field(None, description='Filter by subject text (partial match)'),
    has_attachment: bool = Field(False, description='Filter for emails with attachments'),
    read_status: str | None = Field(
        None, description='Filter by read status: "read", "unread", or None for all'
    ),
    after_date: str | None = Field(
        None, description='Filter for emails after this date (format: YYYY/MM/DD)'
    ),
    before_date: str | None = Field(
        None, description='Filter for emails before this date (format: YYYY/MM/DD)'
    ),
    label: str | None = Field(None, description='Filter by Gmail label name or ID'),
    gmail_query: str | None = Field(
        None, description='Raw Gmail search query (e.g., "is:read from:github.com subject:PR")'
    ),
    max_results: int = Field(10, description='Maximum number of results to return'),
    ctx: Context = None,
) -> SearchResult:
    """
    Search for emails and download results to a temporary markdown file.

    Args:
        from_email: Filter by sender email
        to_email: Filter by recipient email
        subject: Filter by subject text
        has_attachment: Filter for emails with attachments
        read_status: Filter by read status - "read", "unread", or None for all
        after_date: Filter for emails after this date (format: YYYY/MM/DD)
        before_date: Filter for emails before this date (format: YYYY/MM/DD)
        label: Filter by Gmail label
        gmail_query: Raw Gmail search query
        max_results: Maximum number of results to return
        ctx: MCP context for logging

    Returns:
        SearchResult with path to downloaded file and metadata list

    Note: Use either explicit parameters OR gmail_query, not both.
    """
    logger = DualLogger(ctx)
    await logger.info(f'Searching emails with query: {gmail_query or "structured search"}')

    # Validate date formats
    if after_date and not validate_date_format(after_date):
        raise ToolError(f"after_date '{after_date}' is not in the required format YYYY/MM/DD")

    if before_date and not validate_date_format(before_date):
        raise ToolError(f"before_date '{before_date}' is not in the required format YYYY/MM/DD")

    # Use either explicit parameters OR raw Gmail query
    if gmail_query:
        # Check if any explicit parameters are provided
        explicit_params = [
            from_email,
            to_email,
            subject,
            has_attachment,
            read_status,
            after_date,
            before_date,
            label,
        ]
        if any(param is not None and param is not False for param in explicit_params):
            raise ToolError(
                'Cannot use both explicit parameters and gmail_query together. '
                'Please use either explicit parameters OR gmail_query, not both.'
            )

        messages = list_messages(
            _gmail_service, user_id=settings.user_id, max_results=max_results, query=gmail_query
        )
        query_str = gmail_query
    else:
        messages = search_messages(
            _gmail_service,
            user_id=settings.user_id,
            from_email=from_email,
            to_email=to_email,
            subject=subject,
            has_attachment=has_attachment,
            read_status=read_status,
            after=after_date,
            before=before_date,
            labels=[label] if label else None,
            max_results=max_results,
        )
        # Build query string for result
        query_parts = []
        if from_email:
            query_parts.append(f'from:{from_email}')
        if to_email:
            query_parts.append(f'to:{to_email}')
        if subject:
            query_parts.append(f'subject:{subject}')
        query_str = ' '.join(query_parts) if query_parts else 'all messages'

    await logger.info(f'Found {len(messages)} matching emails')

    # Download all emails to file
    markdown_content = '# Gmail Search Results\n\n'
    markdown_content += f'**Query:** {query_str}\n'
    markdown_content += f'**Results:** {len(messages)} emails\n\n'
    markdown_content += '---\n\n'

    metadata_list = []

    for i, msg_info in enumerate(messages, 1):
        msg_id = msg_info.get('id')
        message = get_message(_gmail_service, msg_id, user_id=settings.user_id)
        body = parse_message_body(message)

        # Build metadata
        metadata = build_email_metadata(message, msg_id)
        metadata_list.append(metadata)

        # Add to markdown
        markdown_content += f'## Email {i}\n\n'
        markdown_content += format_email_as_markdown(message, msg_id, body)
        markdown_content += '\n\n---\n\n'

    # Write to temp file
    filename = sanitize_filename(f'search_{query_str}_{len(messages)}_results.md')
    file_path = _export_dir / filename
    file_path.write_text(markdown_content, encoding='utf-8')

    await logger.info(f'Downloaded search results to {file_path}')

    return SearchResult(
        path=str(file_path),
        size_bytes=len(markdown_content.encode('utf-8')),
        match_count=len(messages),
        query=query_str,
        metadata_list=metadata_list,
    )


@mcp.tool(annotations=ToolAnnotations(title='Get Emails', readOnlyHint=True))
async def get_emails(
    message_ids: list[str] = Field(..., description='List of Gmail message IDs to retrieve'),
    ctx: Context = None,
) -> list[EmailDownloadResult]:
    """
    Download multiple emails to temporary files.

    Args:
        message_ids: A list of Gmail message IDs
        ctx: MCP context for logging

    Returns:
        List of EmailDownloadResult with paths and metadata for each email
    """
    logger = DualLogger(ctx)
    await logger.info(f'Downloading {len(message_ids)} emails')

    if not message_ids:
        raise ToolError('No message IDs provided.')

    results = []

    for msg_id in message_ids:
        try:
            message = get_message(_gmail_service, msg_id, user_id=settings.user_id)
            body = parse_message_body(message)

            # Build metadata
            metadata = build_email_metadata(message, msg_id)

            # Format as markdown
            markdown_content = format_email_as_markdown(message, msg_id, body)

            # Write to temp file
            filename = sanitize_filename(f'email_{msg_id}_{metadata.subject}.md')
            file_path = _export_dir / filename
            file_path.write_text(markdown_content, encoding='utf-8')

            results.append(
                EmailDownloadResult(
                    path=str(file_path),
                    size_bytes=len(markdown_content.encode('utf-8')),
                    metadata=metadata,
                )
            )
        except Exception as e:
            await logger.error(f'Failed to download email {msg_id}: {str(e)}')
            raise ToolError(f'Failed to download email {msg_id}: {str(e)}') from e

    await logger.info(f'Successfully downloaded {len(results)} emails')

    return results


@mcp.tool(annotations=ToolAnnotations(title='Get Thread', readOnlyHint=True))
async def get_thread(
    thread_id: str = Field(..., description='Gmail thread ID'),
    ctx: Context = None,
) -> ThreadDownloadResult:
    """
    Download an email thread to a temporary markdown file.

    Args:
        thread_id: The Gmail thread ID
        ctx: MCP context for logging

    Returns:
        ThreadDownloadResult with path and thread metadata
    """
    logger = DualLogger(ctx)
    await logger.info(f'Downloading thread {thread_id}')

    thread = gmail_get_thread(_gmail_service, thread_id, user_id=settings.user_id)
    messages = thread.get('messages', [])

    if not messages:
        raise ToolError(f'No messages found in thread {thread_id}')

    # Parse all messages
    messages_with_bodies = []
    for message in messages:
        body = parse_message_body(message)
        messages_with_bodies.append((message, body))

    # Get subject from first message
    first_headers = get_headers_dict(messages[0])
    subject = first_headers.get('Subject', 'No Subject')

    # Get date range
    first_date = first_headers.get('Date', 'Unknown')
    last_headers = get_headers_dict(messages[-1])
    last_date = last_headers.get('Date', 'Unknown')
    date_range = f'{first_date} to {last_date}' if len(messages) > 1 else first_date

    # Format as markdown
    markdown_content = format_thread_as_markdown(thread, thread_id, messages_with_bodies)

    # Write to temp file
    filename = sanitize_filename(f'thread_{thread_id}_{subject}.md')
    file_path = _export_dir / filename
    file_path.write_text(markdown_content, encoding='utf-8')

    await logger.info(f'Downloaded thread to {file_path}')

    return ThreadDownloadResult(
        path=str(file_path),
        size_bytes=len(markdown_content.encode('utf-8')),
        message_count=len(messages),
        thread_id=thread_id,
        subject=subject,
        date_range=date_range,
    )


@mcp.tool(annotations=ToolAnnotations(title='List Labels', readOnlyHint=True))
async def list_labels(ctx: Context = None) -> list[LabelInfo]:
    """
    List all Gmail labels for the user.

    Args:
        ctx: MCP context for logging

    Returns:
        List of LabelInfo objects
    """
    logger = DualLogger(ctx)
    await logger.info('Listing Gmail labels')

    labels = get_labels(_gmail_service, user_id=settings.user_id)

    results = []
    for label in labels:
        results.append(
            LabelInfo(
                id=label.get('id', 'Unknown'),
                name=label.get('name', 'Unknown'),
                type=label.get('type', 'user'),
                message_list_visibility=label.get('messageListVisibility'),
                label_list_visibility=label.get('labelListVisibility'),
            )
        )

    await logger.info(f'Found {len(results)} labels')

    return results


@mcp.tool(annotations=ToolAnnotations(title='Add Label', readOnlyHint=False, idempotentHint=True))
async def add_label(
    message_id: str = Field(..., description='Gmail message ID'),
    label_id: str = Field(
        ...,
        description=(
            'Gmail label ID to add. Common: INBOX (unarchives), UNREAD (marks unread), '
            'STARRED (stars), IMPORTANT, SPAM, TRASH'
        ),
    ),
    ctx: Context = None,
) -> LabelOperationResult:
    """
    Add a label to an email message.

    Common operations:
    - Unarchive: add 'INBOX' label (moves back to inbox)
    - Mark as unread: add 'UNREAD' label
    - Star: add 'STARRED' label
    - Mark important: add 'IMPORTANT' label
    - Move to spam: add 'SPAM' label
    - Move to trash: add 'TRASH' label

    Args:
        message_id: The Gmail message ID
        label_id: The Gmail label ID to add
        ctx: MCP context for logging

    Returns:
        LabelOperationResult with operation details
    """
    logger = DualLogger(ctx)
    await logger.info(f'Adding label {label_id} to message {message_id}')

    # Add the specified label
    modify_message_labels(
        _gmail_service,
        user_id=settings.user_id,
        message_id=message_id,
        remove_labels=[],
        add_labels=[label_id],
    )

    # Get full message details
    full_message = get_message(_gmail_service, message_id, user_id=settings.user_id)
    headers = get_headers_dict(full_message)
    subject = headers.get('Subject', 'No Subject')

    # Get the label name
    label_name = label_id
    labels = get_labels(_gmail_service, user_id=settings.user_id)
    for label in labels:
        if label.get('id') == label_id:
            label_name = label.get('name', label_id)
            break

    await logger.info(f'Label {label_name} added to message')

    return LabelOperationResult(
        message_id=message_id,
        subject=subject,
        label_name=label_name,
        label_id=label_id,
        operation='added',
    )


@mcp.tool(annotations=ToolAnnotations(title='Remove Label', readOnlyHint=False, idempotentHint=True))
async def remove_label(
    message_id: str = Field(..., description='Gmail message ID'),
    label_id: str = Field(
        ...,
        description=(
            'Gmail label ID to remove. Common: INBOX (archives message), UNREAD, '
            'STARRED (unstars), SPAM, TRASH'
        ),
    ),
    ctx: Context = None,
) -> LabelOperationResult:
    """
    Remove a label from an email message.

    Common operations:
    - Archive: remove 'INBOX' label
    - Mark as read: remove 'UNREAD' label ← Most common!
    - Unstar: remove 'STARRED' label
    - Remove from spam: remove 'SPAM' label
    - Remove from trash: remove 'TRASH' label

    Args:
        message_id: The Gmail message ID
        label_id: The Gmail label ID to remove
        ctx: MCP context for logging

    Returns:
        LabelOperationResult with operation details
    """
    logger = DualLogger(ctx)
    await logger.info(f'Removing label {label_id} from message {message_id}')

    # Get the label name before we remove it
    label_name = label_id
    labels = get_labels(_gmail_service, user_id=settings.user_id)
    for label in labels:
        if label.get('id') == label_id:
            label_name = label.get('name', label_id)
            break

    # Remove the specified label
    modify_message_labels(
        _gmail_service,
        user_id=settings.user_id,
        message_id=message_id,
        remove_labels=[label_id],
        add_labels=[],
    )

    # Get full message details
    full_message = get_message(_gmail_service, message_id, user_id=settings.user_id)
    headers = get_headers_dict(full_message)
    subject = headers.get('Subject', 'No Subject')

    await logger.info(f'Label {label_name} removed from message')

    return LabelOperationResult(
        message_id=message_id,
        subject=subject,
        label_name=label_name,
        label_id=label_id,
        operation='removed',
    )


@mcp.tool(annotations=ToolAnnotations(title='List Attachments', readOnlyHint=True))
async def list_attachments(
    message_id: str = Field(..., description='Gmail message ID'), ctx: Context = None
) -> list[AttachmentInfo]:
    """
    List all attachments in an email message.

    Args:
        message_id: The Gmail message ID
        ctx: MCP context for logging

    Returns:
        List of attachment metadata
    """
    logger = DualLogger(ctx)
    await logger.info(f'Listing attachments for message {message_id}')

    attachments_data = list_message_attachments(_gmail_service, message_id, user_id=settings.user_id)

    results = [AttachmentInfo(**att) for att in attachments_data]

    await logger.info(f'Found {len(results)} attachments')

    return results


@mcp.tool(
    annotations=ToolAnnotations(title='Download Attachment', readOnlyHint=False, idempotentHint=False)
)
async def download_attachment(
    message_id: str = Field(..., description='Gmail message ID'),
    attachment_id: str = Field(..., description='Gmail attachment ID from list_attachments'),
    filename: str = Field(..., description='Filename to save as (will be sanitized)'),
    ctx: Context = None,
) -> DownloadedAttachment:
    """
    Download an email attachment to temporary storage and return the file path.

    Use list_attachments() first to get the attachment_id and original filename.
    The file is saved to a temporary directory that auto-cleans on server shutdown.
    Use the Read tool to view/access the downloaded file.

    Args:
        message_id: The Gmail message ID
        attachment_id: The attachment ID from list_attachments()
        filename: Desired filename (will be sanitized for safety)
        ctx: MCP context for logging

    Returns:
        DownloadedAttachment with path to temp file and metadata
    """
    logger = DualLogger(ctx)
    await logger.info(f'Downloading attachment {filename} from message {message_id}')

    # Download attachment data
    attachment_data = get_attachment_data(
        _gmail_service, message_id=message_id, attachment_id=attachment_id, user_id=settings.user_id
    )

    # Sanitize filename
    safe_filename = sanitize_filename(filename)

    # Save to temp directory
    save_path = _export_dir / safe_filename
    save_path.write_bytes(attachment_data)

    # Get attachment metadata for response
    attachments = list_message_attachments(_gmail_service, message_id, user_id=settings.user_id)
    att_metadata = next((att for att in attachments if att['attachment_id'] == attachment_id), None)

    if not att_metadata:
        # Fallback if metadata not found
        att_metadata = {'filename': filename, 'mime_type': 'application/octet-stream'}

    await logger.info(f'Downloaded attachment to {save_path}')

    return DownloadedAttachment(
        path=str(save_path),
        filename=att_metadata['filename'],
        size_bytes=len(attachment_data),
        mime_type=att_metadata['mime_type'],
        message_id=message_id,
        attachment_id=attachment_id,
    )


if __name__ == '__main__':
    import logging

    logging.basicConfig(level=logging.DEBUG)
    print('Starting Gmail MCP Server...')
    mcp.run(transport='stdio')
