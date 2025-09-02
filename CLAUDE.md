# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the MCP Server
```bash
# Development mode with inspector
uv run mcp dev mcp_gmail/server.py

# Install for Claude Desktop
uv run mcp install \
    --with-editable . \
    --name gmail \
    --env-var MCP_GMAIL_CREDENTIALS_PATH=$(pwd)/credentials.json \
    --env-var MCP_GMAIL_TOKEN_PATH=$(pwd)/token.json \
    mcp_gmail/server.py
```

### Code Quality
```bash
# Format code
uv run ruff format .

# Lint with auto-fixes
uv run ruff check --fix .

# Run tests
uv run pytest tests/

# Run a single test
uv run pytest tests/test_config.py::test_settings_from_file

# Run pre-commit hooks
pre-commit run --all-files
```

### Testing Gmail Setup
```bash
uv run python scripts/test_gmail_setup.py
```

## Architecture Overview

This is a Model Context Protocol (MCP) server that provides Gmail integration for LLMs. The architecture follows a modular design:

### Core Components

1. **mcp_gmail/server.py**: Main MCP server implementation using FastMCP. Exposes Gmail messages/threads as resources and provides tools for email operations (compose, send, search, manage labels).

2. **mcp_gmail/gmail.py**: Gmail API client wrapper that handles:
   - OAuth 2.0 authentication flow
   - Service initialization
   - Core Gmail operations (messages, threads, drafts, labels)
   - Message parsing and formatting

3. **mcp_gmail/config.py**: Pydantic-based configuration management that reads from environment variables with defaults:
   - `MCP_GMAIL_CREDENTIALS_PATH`: OAuth credentials file
   - `MCP_GMAIL_TOKEN_PATH`: Token storage location
   - `MCP_GMAIL_MAX_RESULTS`: Default search result limit

### Authentication Flow

The server uses OAuth 2.0 with the Gmail API scope `.../auth/gmail.modify`. On first run, it opens a browser for authorization and stores the token locally for reuse.

### MCP Resources and Tools

Resources exposed:
- `gmail://messages/{message_id}`: Individual email messages
- `gmail://threads/{thread_id}`: Email conversation threads

Tools provided:
- Email operations: compose_email, send_email, get_emails
- Search: search_emails (structured), query_emails (raw Gmail queries)
- Management: list_available_labels, mark_message_read, add/remove_label_to_message

### Code Standards

- Python 3.10+ with type hints
- Line length: 108 characters
- Formatting: ruff (configured in pyproject.toml)
- Pre-commit hooks enforce formatting and linting before commits
- All new code should include appropriate error handling for Gmail API failures