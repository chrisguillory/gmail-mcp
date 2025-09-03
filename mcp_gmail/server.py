"""
Gmail MCP Server Implementation

This module provides a Model Context Protocol server for interacting with Gmail.
It exposes Gmail messages as resources and provides tools for composing and sending emails.
"""

import re
from datetime import datetime
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from mcp_gmail.config import settings
from mcp_gmail.gmail import (
    create_draft,
    get_gmail_service,
    get_headers_dict,
    get_labels,
    get_message,
    get_thread,
    list_messages,
    modify_message_labels,
    parse_message_body,
    search_messages,
)
from mcp_gmail.gmail import send_email as gmail_send_email

# Initialize the Gmail service
service = get_gmail_service(
    credentials_path=settings.credentials_path, token_path=settings.token_path, scopes=settings.scopes
)

mcp = FastMCP(
    'Gmail MCP Server',
    instructions='Access and interact with Gmail. You can get messages, threads, search emails, and send or compose new messages.',  # noqa: E501
)

EMAIL_PREVIEW_LENGTH = 200

# Available fields for message responses
AVAILABLE_MESSAGE_FIELDS = {
    'id',
    'thread_id',
    'subject',
    'from',
    'to',
    'date',
    'body_preview',
    'body',
    'labels',
    'has_attachments',
    'web_url',
}

# Default fields for minimal response
DEFAULT_MESSAGE_FIELDS = {'id', 'subject', 'from', 'date'}


# Helper functions
def get_gmail_web_url(message_id: str, account_index: int = 0) -> str:
    """
    Generate Gmail web interface URL for a message.

    Args:
        message_id: The Gmail message ID
        account_index: The account index (0 for first account)

    Returns:
        Gmail web URL for the message
    """
    return f'https://mail.google.com/mail/u/{account_index}/#all/{message_id}'


def parse_message_fields(fields_param: Optional[str]) -> set:
    """
    Parse the fields parameter for message responses.

    Args:
        fields_param: Comma-separated field names, "all", or None

    Returns:
        Set of field names to include in response
    """
    if fields_param is None:
        return DEFAULT_MESSAGE_FIELDS

    if fields_param.lower() == 'all':
        return AVAILABLE_MESSAGE_FIELDS

    # Parse comma-separated fields and validate
    requested = set(field.strip().lower() for field in fields_param.split(',') if field.strip())

    # Filter to only valid fields
    valid_fields = requested & AVAILABLE_MESSAGE_FIELDS

    # Warn about invalid fields (in production, you might want to raise an error)
    invalid_fields = requested - AVAILABLE_MESSAGE_FIELDS
    if invalid_fields:
        # Could log warning or include in response
        pass

    return valid_fields if valid_fields else DEFAULT_MESSAGE_FIELDS


def format_message_with_fields(message, message_id: str, fields: set) -> str:
    """
    Format a Gmail message with only requested fields.

    Args:
        message: The Gmail message object
        message_id: The message ID
        fields: Set of fields to include

    Returns:
        Formatted message string with requested fields
    """
    headers = get_headers_dict(message)
    result_lines = []

    if 'id' in fields:
        result_lines.append(f'Message ID: {message_id}')

    if 'thread_id' in fields:
        thread_id = message.get('threadId', '')
        if thread_id:
            result_lines.append(f'Thread ID: {thread_id}')

    if 'from' in fields:
        from_header = headers.get('From', 'Unknown')
        result_lines.append(f'From: {from_header}')

    if 'to' in fields:
        to_header = headers.get('To', 'Unknown')
        result_lines.append(f'To: {to_header}')

    if 'subject' in fields:
        subject = headers.get('Subject', 'No Subject')
        result_lines.append(f'Subject: {subject}')

    if 'date' in fields:
        date = headers.get('Date', 'Unknown Date')
        result_lines.append(f'Date: {date}')

    if 'labels' in fields:
        label_ids = message.get('labelIds', [])
        if label_ids:
            result_lines.append(f'Labels: {", ".join(label_ids)}')

    if 'has_attachments' in fields:
        # Check if message has attachments
        has_attachments = False
        payload = message.get('payload', {})
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('filename'):
                    has_attachments = True
                    break
        result_lines.append(f'Has Attachments: {has_attachments}')

    if 'web_url' in fields:
        result_lines.append(f'Web URL: {get_gmail_web_url(message_id)}')

    if 'body_preview' in fields:
        body = parse_message_body(message)
        preview = body[:EMAIL_PREVIEW_LENGTH].replace('\n', ' ').strip()
        if len(body) > EMAIL_PREVIEW_LENGTH:
            preview += '...'
        result_lines.append(f'Preview: {preview}')

    if 'body' in fields:
        body = parse_message_body(message)
        result_lines.append(f'\nBody:\n{body}')

    return '\n'.join(result_lines)


# Helper functions
def format_message(message):
    """Format a Gmail message for display."""
    headers = get_headers_dict(message)
    body = parse_message_body(message)

    # Extract relevant headers
    from_header = headers.get('From', 'Unknown')
    to_header = headers.get('To', 'Unknown')
    subject = headers.get('Subject', 'No Subject')
    date = headers.get('Date', 'Unknown Date')

    return f"""
From: {from_header}
To: {to_header}
Subject: {subject}
Date: {date}

{body}
"""


def validate_date_format(date_str):
    """
    Validate that a date string is in the format YYYY/MM/DD.

    Args:
        date_str: The date string to validate

    Returns:
        bool: True if valid, False otherwise
    """
    if not date_str:
        return True

    # Check format with regex
    if not re.match(r'^\d{4}/\d{2}/\d{2}$', date_str):
        return False

    # Validate the date is a real date
    try:
        datetime.strptime(date_str, '%Y/%m/%d')
        return True
    except ValueError:
        return False


# Resources
@mcp.resource('gmail://messages/{message_id}')
def get_email_message(message_id: str) -> str:
    """
    Get the content of an email message by its ID.

    Args:
        message_id: The Gmail message ID

    Returns:
        The formatted email content
    """
    message = get_message(service, message_id, user_id=settings.user_id)
    formatted_message = format_message(message)
    return formatted_message


@mcp.resource('gmail://threads/{thread_id}')
def get_email_thread(thread_id: str) -> str:
    """
    Get all messages in an email thread by thread ID.

    Args:
        thread_id: The Gmail thread ID

    Returns:
        The formatted thread content with all messages
    """
    thread = get_thread(service, thread_id, user_id=settings.user_id)
    messages = thread.get('messages', [])

    result = f'Email Thread (ID: {thread_id})\n'
    for i, message in enumerate(messages, 1):
        result += f'\n--- Message {i} ---\n'
        result += format_message(message)

    return result


# Tools
@mcp.tool()
def create_draft(
    to: str = Field(..., description='Recipient email address'),
    subject: str = Field(..., description='Email subject line'),
    body: str = Field(..., description='Email body content (plain text or HTML)'),
    cc: Optional[str] = Field(None, description='Carbon copy recipients (comma-separated if multiple)'),
    bcc: Optional[str] = Field(
        None, description='Blind carbon copy recipients (comma-separated if multiple)'
    ),
) -> str:
    """
    Create a new email draft.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body content
        cc: Carbon copy recipients (optional)
        bcc: Blind carbon copy recipients (optional)

    Returns:
        The ID of the created draft and its content
    """
    sender = service.users().getProfile(userId=settings.user_id).execute().get('emailAddress')
    draft = create_draft(
        service, sender=sender, to=to, subject=subject, body=body, user_id=settings.user_id, cc=cc, bcc=bcc
    )

    draft_id = draft.get('id')
    return f"""
Email draft created with ID: {draft_id}
To: {to}
Subject: {subject}
CC: {cc or ''}
BCC: {bcc or ''}
Body: {body[:EMAIL_PREVIEW_LENGTH]}{'...' if len(body) > EMAIL_PREVIEW_LENGTH else ''}
"""


@mcp.tool()
def send_email(
    to: str = Field(..., description='Recipient email address'),
    subject: str = Field(..., description='Email subject line'),
    body: str = Field(..., description='Email body content (plain text or HTML)'),
    cc: Optional[str] = Field(None, description='Carbon copy recipients (comma-separated if multiple)'),
    bcc: Optional[str] = Field(
        None, description='Blind carbon copy recipients (comma-separated if multiple)'
    ),
) -> str:
    """
    Compose and send an email.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body content
        cc: Carbon copy recipients (optional)
        bcc: Blind carbon copy recipients (optional)

    Returns:
        Content of the sent email
    """
    sender = service.users().getProfile(userId=settings.user_id).execute().get('emailAddress')
    message = gmail_send_email(
        service, sender=sender, to=to, subject=subject, body=body, user_id=settings.user_id, cc=cc, bcc=bcc
    )

    message_id = message.get('id')
    return f"""
Email sent successfully with ID: {message_id}
To: {to}
Subject: {subject}
CC: {cc or ''}
BCC: {bcc or ''}
Body: {body[:EMAIL_PREVIEW_LENGTH]}{'...' if len(body) > EMAIL_PREVIEW_LENGTH else ''}
"""


@mcp.tool()
def search_emails(
    from_email: Optional[str] = Field(None, description='Filter by sender email address'),
    to_email: Optional[str] = Field(None, description='Filter by recipient email address'),
    subject: Optional[str] = Field(None, description='Filter by subject text (partial match)'),
    has_attachment: bool = Field(False, description='Filter for emails with attachments'),
    read_status: Optional[str] = Field(
        None, description='Filter by read status: "read", "unread", or None for all'
    ),
    after_date: Optional[str] = Field(
        None, description='Filter for emails after this date (format: YYYY/MM/DD)'
    ),
    before_date: Optional[str] = Field(
        None, description='Filter for emails before this date (format: YYYY/MM/DD)'
    ),
    label: Optional[str] = Field(None, description='Filter by Gmail label name or ID'),
    gmail_query: Optional[str] = Field(
        None, description='Raw Gmail search query (e.g., "is:read from:github.com subject:PR")'
    ),
    max_results: int = Field(10, description='Maximum number of results to return'),
    fields: Optional[str] = Field(
        None,
        description='Comma-separated list of fields: id, thread_id, subject, from, to, date, body_preview, body, labels, has_attachments, web_url. Default: "id,subject,from,date". Use "all" for all fields.',
    ),
) -> str:
    """
    Search for emails using specific search criteria.

    Args:
        from_email: Filter by sender email
        to_email: Filter by recipient email
        subject: Filter by subject text
        has_attachment: Filter for emails with attachments
        read_status: Filter by read status - "read", "unread", or None for all
        after_date: Filter for emails after this date (format: YYYY/MM/DD)
        before_date: Filter for emails before this date (format: YYYY/MM/DD)
        label: Filter by Gmail label
        gmail_query: Raw Gmail search query (e.g., "is:read from:github.com subject:PR")
        max_results: Maximum number of results to return
        fields: Comma-separated list of fields to include in response.
                Available: id, thread_id, subject, from, to, date, body_preview, body,
                labels, has_attachments, web_url
                Default: "id,subject,from,date" (minimal set for token efficiency)
                Use "all" for all available fields

    Returns:
        Formatted list of matching emails with requested fields

    Note: Use either explicit parameters OR gmail_query, not both.
    If gmail_query is provided, all other parameters are ignored.
    """
    # Validate date formats
    if after_date and not validate_date_format(after_date):
        raise ToolError(f"after_date '{after_date}' is not in the required format YYYY/MM/DD")

    if before_date and not validate_date_format(before_date):
        raise ToolError(f"before_date '{before_date}' is not in the required format YYYY/MM/DD")

    # Parse requested fields
    requested_fields = parse_message_fields(fields)

    # Use either explicit parameters OR raw Gmail query (not both)
    if gmail_query:
        # Check if any explicit parameters are provided and warn the user
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
            params_used = []
            if from_email:
                params_used.append(f'- from_email: {from_email}')
            if to_email:
                params_used.append(f'- to_email: {to_email}')
            if subject:
                params_used.append(f'- subject: {subject}')
            if has_attachment:
                params_used.append(f'- has_attachment: {has_attachment}')
            if read_status:
                params_used.append(f'- read_status: {read_status}')
            if after_date:
                params_used.append(f'- after_date: {after_date}')
            if before_date:
                params_used.append(f'- before_date: {before_date}')
            if label:
                params_used.append(f'- label: {label}')

            error_msg = f"""Cannot use both explicit parameters and gmail_query together.
            
You provided gmail_query: "{gmail_query}"
But also provided explicit parameters that will be ignored:
{chr(10).join(params_used)}

Please use either explicit parameters OR gmail_query, not both."""
            raise ToolError(error_msg)

        # Use raw Gmail query directly
        messages = list_messages(
            service, user_id=settings.user_id, max_results=max_results, query=gmail_query
        )
        # Early return for gmail_query path
        result = f'Found {len(messages)} messages matching criteria:\n'

        for msg_info in messages:
            msg_id = msg_info.get('id')
            message = get_message(service, msg_id, user_id=settings.user_id)

            result += f'\n{format_message_with_fields(message, msg_id, requested_fields)}\n'

        return result

    # Use explicit parameters with search_messages
    messages = search_messages(
        service,
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

    result = f'Found {len(messages)} messages matching criteria:\n'

    for msg_info in messages:
        msg_id = msg_info.get('id')
        message = get_message(service, msg_id, user_id=settings.user_id)

        result += f'\n{format_message_with_fields(message, msg_id, requested_fields)}\n'

    return result


@mcp.tool()
def list_labels() -> str:
    """
    List all Gmail labels for the user.

    Returns:
        Formatted list of labels with their IDs
    """
    labels = get_labels(service, user_id=settings.user_id)

    result = 'Available Gmail Labels:\n'
    for label in labels:
        label_id = label.get('id', 'Unknown')
        name = label.get('name', 'Unknown')
        type_info = label.get('type', 'user')

        result += f'\nLabel ID: {label_id}\n'
        result += f'Name: {name}\n'
        result += f'Type: {type_info}\n'

    return result


@mcp.tool()
def add_label(
    message_id: str = Field(..., description='Gmail message ID'),
    label_id: str = Field(
        ...,
        description='Gmail label ID to add. Common: INBOX (unarchives), UNREAD (marks unread), STARRED (stars), IMPORTANT, SPAM, TRASH',
    ),
) -> str:
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
        label_id: The Gmail label ID to add (use list_available_labels to find label IDs)

    Returns:
        Confirmation message
    """
    # Add the specified label
    modify_message_labels(
        service, user_id=settings.user_id, message_id=message_id, remove_labels=[], add_labels=[label_id]
    )

    # Get full message details to show what was modified
    full_message = get_message(service, message_id, user_id=settings.user_id)
    headers = get_headers_dict(full_message)
    subject = headers.get('Subject', 'No Subject')

    # Get the label name for the confirmation message
    label_name = label_id
    labels = get_labels(service, user_id=settings.user_id)
    for label in labels:
        if label.get('id') == label_id:
            label_name = label.get('name', label_id)
            break

    return f"""
Label added to message:
ID: {message_id}
Subject: {subject}
Added Label: {label_name} ({label_id})
"""


@mcp.tool()
def remove_label(
    message_id: str = Field(..., description='Gmail message ID'),
    label_id: str = Field(
        ...,
        description='Gmail label ID to remove. Common: INBOX (archives message), UNREAD, STARRED (unstars), SPAM, TRASH',
    ),
) -> str:
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
        label_id: The Gmail label ID to remove (use list_available_labels to find label IDs)

    Returns:
        Confirmation message
    """
    # Get the label name before we remove it
    label_name = label_id
    labels = get_labels(service, user_id=settings.user_id)
    for label in labels:
        if label.get('id') == label_id:
            label_name = label.get('name', label_id)
            break

    # Remove the specified label
    modify_message_labels(
        service, user_id=settings.user_id, message_id=message_id, remove_labels=[label_id], add_labels=[]
    )

    # Get full message details to show what was modified
    full_message = get_message(service, message_id, user_id=settings.user_id)
    headers = get_headers_dict(full_message)
    subject = headers.get('Subject', 'No Subject')

    return f"""
Label removed from message:
ID: {message_id}
Subject: {subject}
Removed Label: {label_name} ({label_id})
"""


@mcp.tool()
def get_emails(
    message_ids: list[str] = Field(..., description='List of Gmail message IDs to retrieve'),
    fields: Optional[str] = Field(
        None,
        description='Comma-separated list of fields: id, thread_id, subject, from, to, date, body_preview, body, labels, has_attachments, web_url. Default: "id,subject,from,date". Use "all" for all fields.',
    ),
) -> str:
    """
    Get the content of multiple email messages by their IDs.

    Args:
        message_ids: A list of Gmail message IDs
        fields: Comma-separated list of fields to include in response.
                Available: id, thread_id, subject, from, to, date, body_preview, body,
                labels, has_attachments, web_url
                Default: "id,subject,from,date" (minimal set for token efficiency)
                Use "all" for all available fields

    Returns:
        The formatted content of all requested emails with requested fields
    """
    if not message_ids:
        return 'No message IDs provided.'

    # Parse requested fields
    requested_fields = parse_message_fields(fields)

    # Fetch all emails first
    retrieved_emails = []
    error_emails = []

    for msg_id in message_ids:
        try:
            message = get_message(service, msg_id, user_id=settings.user_id)
            retrieved_emails.append((msg_id, message))
        except Exception as e:
            error_emails.append((msg_id, str(e)))

    # Build result string after fetching all emails
    result = f'Retrieved {len(retrieved_emails)} emails:\n'

    # Format all successfully retrieved emails
    for i, (msg_id, message) in enumerate(retrieved_emails, 1):
        result += f'\n--- Email {i} ---\n'
        result += format_message_with_fields(message, msg_id, requested_fields)
        result += '\n'

    # Report any errors
    if error_emails:
        result += f'\n\nFailed to retrieve {len(error_emails)} emails:\n'
        for i, (msg_id, error) in enumerate(error_emails, 1):
            result += f'\n--- Email {i} (ID: {msg_id}) ---\n'
            result += f'Error: {error}\n'

    return result


if __name__ == '__main__':
    import logging

    logging.basicConfig(level=logging.DEBUG)
    print('Starting Gmail MCP Server...')
    mcp.run(transport='stdio')
