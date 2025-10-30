"""Utilities for authenticating with and using the Gmail API."""

import base64
import json
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

from src.config import DEFAULT_CREDENTIALS_PATH, DEFAULT_TOKEN_PATH, DEFAULT_USER_ID, GMAIL_SCOPES

# Type alias for the Gmail service
GmailService = Resource


def get_gmail_service(
    credentials_path: str = DEFAULT_CREDENTIALS_PATH,
    token_path: str = DEFAULT_TOKEN_PATH,
    scopes: list[str] = GMAIL_SCOPES,
) -> GmailService:
    """
    Authenticate with Gmail API and return the service object.

    Args:
        credentials_path: Path to the credentials JSON file
        token_path: Path to save/load the token
        scopes: OAuth scopes to request

    Returns:
        Authenticated Gmail API service
    """
    creds = None

    # Look for token file with stored credentials
    if os.path.exists(token_path):
        with open(token_path, 'r') as token:
            token_data = json.load(token)
            creds = Credentials.from_authorized_user_info(token_data)

    # If credentials don't exist or are invalid, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Check if credentials file exists
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f'Credentials file not found at {credentials_path}. '
                    'Please download your OAuth credentials from Google Cloud Console.'
                )

            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
            creds = flow.run_local_server(port=0)

        # Save credentials for future runs
        token_json = json.loads(creds.to_json())
        with open(token_path, 'w') as token:
            json.dump(token_json, token)

    # Build the Gmail service
    return build('gmail', 'v1', credentials=creds)


def create_message(
    sender: str,
    to: str,
    subject: str,
    message_text: str,
    cc: str | None = None,
    bcc: str | None = None,
) -> dict[str, Any]:
    """
    Create a message for the Gmail API.

    Args:
        sender: Email sender
        to: Email recipient
        subject: Email subject
        message_text: Email body text
        cc: Carbon copy recipients (optional)
        bcc: Blind carbon copy recipients (optional)

    Returns:
        A dictionary containing a base64url encoded email object
    """
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject

    if cc:
        message['cc'] = cc
    if bcc:
        message['bcc'] = bcc

    # Encode the message
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    return {'raw': encoded_message}


def create_multipart_message(
    sender: str,
    to: str,
    subject: str,
    text_part: str,
    html_part: str | None = None,
    cc: str | None = None,
    bcc: str | None = None,
) -> dict[str, Any]:
    """
    Create a multipart MIME message (text and HTML).

    Args:
        sender: Email sender
        to: Email recipient
        subject: Email subject
        text_part: Plain text email body
        html_part: HTML email body (optional)
        cc: Carbon copy recipients (optional)
        bcc: Blind carbon copy recipients (optional)

    Returns:
        A dictionary containing a base64url encoded email object
    """
    message = MIMEMultipart('alternative')
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject

    if cc:
        message['cc'] = cc
    if bcc:
        message['bcc'] = bcc

    # Attach text part
    text_mime = MIMEText(text_part, 'plain')
    message.attach(text_mime)

    # Attach HTML part if provided
    if html_part:
        html_mime = MIMEText(html_part, 'html')
        message.attach(html_mime)

    # Encode the message
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    return {'raw': encoded_message}


def parse_message_body(message: dict[str, Any]) -> str:
    """
    Parse the body of a Gmail message.

    Args:
        message: The Gmail message object

    Returns:
        The extracted message body text
    """

    # Helper function to find text/plain parts
    def get_text_part(parts):
        text = ''
        for part in parts:
            if part['mimeType'] == 'text/plain':
                if 'data' in part['body']:
                    text += base64.urlsafe_b64decode(part['body']['data']).decode()
            elif 'parts' in part:
                text += get_text_part(part['parts'])
        return text

    # Check if the message is multipart
    if 'parts' in message['payload']:
        return get_text_part(message['payload']['parts'])
    else:
        # Handle single part messages
        if 'data' in message['payload']['body']:
            data = message['payload']['body']['data']
            return base64.urlsafe_b64decode(data).decode()
        return ''


def send_email(
    service: GmailService,
    sender: str,
    to: str,
    subject: str,
    body: str,
    user_id: str = DEFAULT_USER_ID,
    cc: str | None = None,
    bcc: str | None = None,
) -> dict[str, Any]:
    """
    Compose and send an email.

    Args:
        service: Gmail API service instance
        sender: Email sender
        to: Email recipient
        subject: Email subject
        body: Email body text
        user_id: Gmail user ID (default: 'me')
        cc: Carbon copy recipients (optional)
        bcc: Blind carbon copy recipients (optional)

    Returns:
        Sent message object
    """
    message = create_message(sender, to, subject, body, cc, bcc)
    return service.users().messages().send(userId=user_id, body=message).execute()


def get_labels(service: GmailService, user_id: str = DEFAULT_USER_ID) -> list[dict[str, Any]]:
    """
    Get all labels for the specified user.

    Args:
        service: Gmail API service instance
        user_id: Gmail user ID (default: 'me')

    Returns:
        List of label objects
    """
    response = service.users().labels().list(userId=user_id).execute()
    return response.get('labels', [])


def list_messages(
    service: GmailService,
    user_id: str = DEFAULT_USER_ID,
    max_results: int = 10,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """
    List messages in the user's mailbox.

    Args:
        service: Gmail API service instance
        user_id: Gmail user ID (default: 'me')
        max_results: Maximum number of messages to return (default: 10)
        query: Search query (default: None)

    Returns:
        List of message objects
    """
    response = (
        service.users().messages().list(userId=user_id, maxResults=max_results, q=query or '').execute()
    )
    messages = response.get('messages', [])
    return messages


def search_messages(
    service: GmailService,
    user_id: str = DEFAULT_USER_ID,
    max_results: int = 10,
    read_status: str | None = None,
    labels: list[str] | None = None,
    from_email: str | None = None,
    to_email: str | None = None,
    subject: str | None = None,
    after: str | None = None,
    before: str | None = None,
    has_attachment: bool | None = None,
    is_starred: bool | None = None,
    is_important: bool | None = None,
    in_trash: bool | None = None,
) -> list[dict[str, Any]]:
    """
    Search for messages in the user's mailbox using various criteria.

    Args:
        service: Gmail API service instance
        user_id: Gmail user ID (default: 'me')
        max_results: Maximum number of messages to return (default: 10)
        read_status: Filter by read status - "read", "unread", or None for all (optional)
        labels: List of label names to search for (optional)
        from_email: Sender email address (optional)
        to_email: Recipient email address (optional)
        subject: Subject text to search for (optional)
        after: Only return messages after this date (format: YYYY/MM/DD) (optional)
        before: Only return messages before this date (format: YYYY/MM/DD) (optional)
        has_attachment: If True, only return messages with attachments (optional)
        is_starred: If True, only return starred messages (optional)
        is_important: If True, only return important messages (optional)
        in_trash: If True, only search in trash (optional)

    Returns:
        List of message objects matching the search criteria
    """
    query_parts = []

    # Handle read/unread status
    if read_status is not None:
        if read_status == 'read':
            query_parts.append('is:read')
        elif read_status == 'unread':
            query_parts.append('is:unread')

    # Handle labels
    if labels:
        for label in labels:
            query_parts.append(f'label:{label}')

    # Handle from and to
    if from_email:
        query_parts.append(f'from:{from_email}')
    if to_email:
        query_parts.append(f'to:{to_email}')

    # Handle subject
    if subject:
        query_parts.append(f'subject:{subject}')

    # Handle date filters
    if after:
        query_parts.append(f'after:{after}')
    if before:
        query_parts.append(f'before:{before}')

    # Handle attachment filter
    if has_attachment is not None and has_attachment:
        query_parts.append('has:attachment')

    # Handle starred and important flags
    if is_starred is not None and is_starred:
        query_parts.append('is:starred')
    if is_important is not None and is_important:
        query_parts.append('is:important')

    # Handle trash
    if in_trash is not None and in_trash:
        query_parts.append('in:trash')

    # Join all query parts with spaces
    query = ' '.join(query_parts)

    # Use the existing list_messages function to perform the search
    return list_messages(service, user_id, max_results, query)


def get_message(service: GmailService, message_id: str, user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
    """
    Get a specific message by ID.

    Args:
        service: Gmail API service instance
        message_id: Gmail message ID
        user_id: Gmail user ID (default: 'me')

    Returns:
        Message object
    """
    message = service.users().messages().get(userId=user_id, id=message_id).execute()
    return message


def get_thread(service: GmailService, thread_id: str, user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
    """
    Get a specific thread by ID.

    Args:
        service: Gmail API service instance
        thread_id: Gmail thread ID
        user_id: Gmail user ID (default: 'me')

    Returns:
        Thread object
    """
    thread = service.users().threads().get(userId=user_id, id=thread_id).execute()
    return thread


def create_draft(
    service: GmailService,
    sender: str,
    to: str,
    subject: str,
    body: str,
    user_id: str = DEFAULT_USER_ID,
    cc: str | None = None,
    bcc: str | None = None,
) -> dict[str, Any]:
    """
    Create a draft email.

    Args:
        service: Gmail API service instance
        sender: Email sender
        to: Email recipient
        subject: Email subject
        body: Email body text
        user_id: Gmail user ID (default: 'me')
        cc: Carbon copy recipients (optional)
        bcc: Blind carbon copy recipients (optional)

    Returns:
        Draft object
    """
    message = create_message(sender, to, subject, body, cc, bcc)
    draft_body = {'message': message}
    return service.users().drafts().create(userId=user_id, body=draft_body).execute()


def list_drafts(
    service: GmailService, user_id: str = DEFAULT_USER_ID, max_results: int = 10
) -> list[dict[str, Any]]:
    """
    List draft emails in the user's mailbox.

    Args:
        service: Gmail API service instance
        user_id: Gmail user ID (default: 'me')
        max_results: Maximum number of drafts to return (default: 10)

    Returns:
        List of draft objects
    """
    response = service.users().drafts().list(userId=user_id, maxResults=max_results).execute()
    drafts = response.get('drafts', [])
    return drafts


def get_draft(service: GmailService, draft_id: str, user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
    """
    Get a specific draft by ID.

    Args:
        service: Gmail API service instance
        draft_id: Gmail draft ID
        user_id: Gmail user ID (default: 'me')

    Returns:
        Draft object
    """
    draft = service.users().drafts().get(userId=user_id, id=draft_id).execute()
    return draft


def send_draft(service: GmailService, draft_id: str, user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
    """
    Send an existing draft email.

    Args:
        service: Gmail API service instance
        draft_id: Gmail draft ID
        user_id: Gmail user ID (default: 'me')

    Returns:
        Sent message object
    """
    draft = {'id': draft_id}
    return service.users().drafts().send(userId=user_id, body=draft).execute()


def create_label(
    service: GmailService, name: str, user_id: str = DEFAULT_USER_ID, label_type: str = 'user'
) -> dict[str, Any]:
    """
    Create a new label.

    Args:
        service: Gmail API service instance
        name: Label name
        user_id: Gmail user ID (default: 'me')
        label_type: Label type (default: 'user')

    Returns:
        Created label object
    """
    label_body = {
        'name': name,
        'labelListVisibility': 'labelShow',
        'messageListVisibility': 'show',
        'type': label_type,
    }
    return service.users().labels().create(userId=user_id, body=label_body).execute()


def update_label(
    service: GmailService,
    label_id: str,
    name: str | None = None,
    label_list_visibility: str | None = None,
    message_list_visibility: str | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    """
    Update an existing label.

    Args:
        service: Gmail API service instance
        label_id: Label ID to update
        name: New label name (optional)
        label_list_visibility: Label visibility in label list (optional)
        message_list_visibility: Label visibility in message list (optional)
        user_id: Gmail user ID (default: 'me')

    Returns:
        Updated label object
    """
    # Get the current label to update
    label = service.users().labels().get(userId=user_id, id=label_id).execute()

    # Update fields if provided
    if name:
        label['name'] = name
    if label_list_visibility:
        label['labelListVisibility'] = label_list_visibility
    if message_list_visibility:
        label['messageListVisibility'] = message_list_visibility

    return service.users().labels().update(userId=user_id, id=label_id, body=label).execute()


def delete_label(service: GmailService, label_id: str, user_id: str = DEFAULT_USER_ID) -> None:
    """
    Delete a label.

    Args:
        service: Gmail API service instance
        label_id: Label ID to delete
        user_id: Gmail user ID (default: 'me')

    Returns:
        None
    """
    service.users().labels().delete(userId=user_id, id=label_id).execute()


def modify_message_labels(
    service: GmailService,
    message_id: str,
    add_labels: list[str] | None = None,
    remove_labels: list[str] | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    """
    Modify the labels on a message.

    Args:
        service: Gmail API service instance
        message_id: Message ID
        add_labels: List of label IDs to add (optional)
        remove_labels: List of label IDs to remove (optional)
        user_id: Gmail user ID (default: 'me')

    Returns:
        Updated message object
    """
    body = {'addLabelIds': add_labels or [], 'removeLabelIds': remove_labels or []}
    return service.users().messages().modify(userId=user_id, id=message_id, body=body).execute()


def batch_modify_messages_labels(
    service: GmailService,
    message_ids: list[str],
    add_labels: list[str] | None = None,
    remove_labels: list[str] | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> None:
    """
    Batch modify the labels on multiple messages.

    Args:
        service: Gmail API service instance
        message_ids: List of message IDs
        add_labels: List of label IDs to add (optional)
        remove_labels: List of label IDs to remove (optional)
        user_id: Gmail user ID (default: 'me')

    Returns:
        None
    """
    body = {'ids': message_ids, 'addLabelIds': add_labels or [], 'removeLabelIds': remove_labels or []}
    service.users().messages().batchModify(userId=user_id, body=body).execute()


def trash_message(service: GmailService, message_id: str, user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
    """
    Move a message to trash.

    Args:
        service: Gmail API service instance
        message_id: Message ID
        user_id: Gmail user ID (default: 'me')

    Returns:
        Updated message object
    """
    return service.users().messages().trash(userId=user_id, id=message_id).execute()


def untrash_message(
    service: GmailService, message_id: str, user_id: str = DEFAULT_USER_ID
) -> dict[str, Any]:
    """
    Remove a message from trash.

    Args:
        service: Gmail API service instance
        message_id: Message ID
        user_id: Gmail user ID (default: 'me')

    Returns:
        Updated message object
    """
    return service.users().messages().untrash(userId=user_id, id=message_id).execute()


def get_message_history(
    service: GmailService, history_id: str, user_id: str = DEFAULT_USER_ID, max_results: int = 100
) -> dict[str, Any]:
    """
    Get history of changes to the mailbox.

    Args:
        service: Gmail API service instance
        history_id: Starting history ID
        user_id: Gmail user ID (default: 'me')
        max_results: Maximum number of history records to return

    Returns:
        History object
    """
    return (
        service.users()
        .history()
        .list(userId=user_id, startHistoryId=history_id, maxResults=max_results)
        .execute()
    )


def list_message_attachments(
    service: GmailService, message_id: str, user_id: str = DEFAULT_USER_ID
) -> list[dict[str, Any]]:
    """
    List all attachments in a message.

    Args:
        service: Gmail API service instance
        message_id: Gmail message ID
        user_id: Gmail user ID (default: 'me')

    Returns:
        List of attachment metadata dictionaries with keys:
        - filename: Original filename
        - attachment_id: Gmail attachment ID
        - mime_type: MIME type
        - size_bytes: Size in bytes
    """
    message = get_message(service, message_id, user_id)
    attachments = []

    def _find_attachments(parts):
        """Recursively traverse message parts to find attachments."""
        for part in parts:
            # Check if this part has a filename (indicates attachment)
            filename = part.get('filename')
            if filename and part.get('body', {}).get('attachmentId'):
                attachments.append(
                    {
                        'filename': filename,
                        'attachment_id': part['body']['attachmentId'],
                        'mime_type': part.get('mimeType', 'application/octet-stream'),
                        'size_bytes': part['body'].get('size', 0),
                    }
                )

            # Recurse into nested parts
            if 'parts' in part:
                _find_attachments(part['parts'])

    # Start traversal from payload
    payload = message.get('payload', {})
    if 'parts' in payload:
        _find_attachments(payload['parts'])
    elif payload.get('filename') and payload.get('body', {}).get('attachmentId'):
        # Single-part message with attachment
        attachments.append(
            {
                'filename': payload['filename'],
                'attachment_id': payload['body']['attachmentId'],
                'mime_type': payload.get('mimeType', 'application/octet-stream'),
                'size_bytes': payload['body'].get('size', 0),
            }
        )

    return attachments


def get_attachment_data(
    service: GmailService, message_id: str, attachment_id: str, user_id: str = DEFAULT_USER_ID
) -> bytes:
    """
    Download attachment and return raw bytes.

    Args:
        service: Gmail API service instance
        message_id: Gmail message ID
        attachment_id: Gmail attachment ID
        user_id: Gmail user ID (default: 'me')

    Returns:
        Raw attachment data as bytes
    """
    attachment = (
        service.users()
        .messages()
        .attachments()
        .get(userId=user_id, messageId=message_id, id=attachment_id)
        .execute()
    )

    # Decode base64url-encoded data
    data = attachment['data']
    return base64.urlsafe_b64decode(data)
