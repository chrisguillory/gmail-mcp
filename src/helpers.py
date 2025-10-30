"""Helper utilities for Gmail MCP server."""

import re
from datetime import datetime
from email.utils import parsedate_to_datetime

from src.models import EmailMetadata


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


def format_email_date(date_str: str) -> str:
    """
    Parse and format an email date string to local timezone.

    Converts RFC 2822 formatted email dates to the system's local timezone
    and formats them in a compact, readable format.

    Args:
        date_str: RFC 2822 formatted date string from email header

    Returns:
        Formatted date string in format: YYYY-MM-DD HH:MM AM/PM TZ
        Falls back to original date string if parsing fails.

    Example:
        "Tue, 28 Oct 2025 16:56:35 +0000" -> "2025-10-28 09:56 AM PDT"
    """
    if not date_str or date_str == 'Unknown Date':
        return 'Unknown Date'

    try:
        # Parse the RFC 2822 date string
        dt = parsedate_to_datetime(date_str)

        # Convert to local timezone
        local_dt = dt.astimezone()

        # Format as: YYYY-MM-DD HH:MM AM/PM TZ
        formatted = local_dt.strftime('%Y-%m-%d %I:%M %p %Z')

        return formatted
    except (ValueError, TypeError, AttributeError):
        # If parsing fails, return the original date string
        return date_str


def validate_date_format(date_str: str | None) -> bool:
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


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal and ensure safe file operations.

    Args:
        filename: The filename to sanitize

    Returns:
        Sanitized filename safe for file system operations
    """
    # Replace invalid characters with underscores
    safe_filename = ''.join(c if c.isalnum() or c in '.-_ ' else '_' for c in filename)

    # Ensure filename doesn't start with a dot (hidden file)
    if not safe_filename or safe_filename.startswith('.'):
        safe_filename = 'file_' + safe_filename

    # Limit length
    if len(safe_filename) > 200:
        safe_filename = safe_filename[:200]

    return safe_filename


def check_message_has_attachments(message: dict) -> bool:
    """
    Check if a Gmail message has attachments.

    Args:
        message: Gmail message object

    Returns:
        True if message has attachments, False otherwise
    """
    payload = message.get('payload', {})
    if 'parts' in payload:
        for part in payload['parts']:
            if part.get('filename'):
                return True
    return False


def get_headers_dict(message: dict) -> dict[str, str]:
    """
    Extract headers from a Gmail message into a dictionary.

    Args:
        message: The Gmail message object

    Returns:
        Dictionary of message headers
    """
    headers = {}
    for header in message['payload']['headers']:
        headers[header['name']] = header['value']
    return headers


def build_email_metadata(message: dict, message_id: str) -> EmailMetadata:
    """
    Build EmailMetadata from a Gmail message object.

    Args:
        message: The Gmail message object
        message_id: The message ID

    Returns:
        EmailMetadata instance
    """
    headers = get_headers_dict(message)

    return EmailMetadata(
        id=message_id,
        thread_id=message.get('threadId', ''),
        subject=headers.get('Subject', 'No Subject'),
        from_addr=headers.get('From', 'Unknown'),
        to_addr=headers.get('To', 'Unknown'),
        date=format_email_date(headers.get('Date', 'Unknown Date')),
        labels=message.get('labelIds', []),
        has_attachments=check_message_has_attachments(message),
        web_url=get_gmail_web_url(message_id),
    )


def format_email_as_markdown(message: dict, message_id: str, body: str) -> str:
    """
    Format a Gmail message as markdown.

    Args:
        message: The Gmail message object
        message_id: The message ID
        body: The email body text

    Returns:
        Markdown formatted email
    """
    metadata = build_email_metadata(message, message_id)

    markdown = f"""# Email: {metadata.subject}

**Message ID:** {metadata.id}
**Thread ID:** {metadata.thread_id}
**From:** {metadata.from_addr}
**To:** {metadata.to_addr}
**Date:** {metadata.date}
**Labels:** {', '.join(metadata.labels)}
**Has Attachments:** {metadata.has_attachments}
**Web URL:** {metadata.web_url}

---

## Body

{body}
"""
    return markdown


def format_thread_as_markdown(
    thread: dict, thread_id: str, messages_with_bodies: list[tuple[dict, str]]
) -> str:
    """
    Format a Gmail thread as markdown.

    Args:
        thread: The Gmail thread object
        thread_id: The thread ID
        messages_with_bodies: List of (message, body) tuples

    Returns:
        Markdown formatted thread
    """
    if not messages_with_bodies:
        return f'# Email Thread\n\n**Thread ID:** {thread_id}\n\nNo messages found.\n'

    # Get subject from first message
    first_message = messages_with_bodies[0][0]
    headers = get_headers_dict(first_message)
    subject = headers.get('Subject', 'No Subject')

    markdown = f"""# Email Thread: {subject}

**Thread ID:** {thread_id}
**Message Count:** {len(messages_with_bodies)}

---

"""

    for i, (message, body) in enumerate(messages_with_bodies, 1):
        message_id = message.get('id', 'unknown')
        headers = get_headers_dict(message)

        markdown += f"""## Message {i}

**Message ID:** {message_id}
**From:** {headers.get('From', 'Unknown')}
**To:** {headers.get('To', 'Unknown')}
**Date:** {format_email_date(headers.get('Date', 'Unknown Date'))}
**Subject:** {headers.get('Subject', 'No Subject')}

{body}

---

"""

    return markdown
