# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the MCP Server
```bash
# Development mode with inspector
uv run mcp dev src/server.py

# Install for Claude Desktop
uv run mcp install \
    --with-editable . \
    --name gmail \
    --env-var MCP_GMAIL_CREDENTIALS_PATH=$(pwd)/credentials.json \
    --env-var MCP_GMAIL_TOKEN_PATH=$(pwd)/token.json \
    src/server.py
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

This is a Model Context Protocol (MCP) server that provides Gmail integration for LLMs. The architecture follows modern Python best practices with file-based responses to optimize token usage.

### Core Components

1. **src/server.py**: Main MCP server implementation using FastMCP with async/await patterns
   - Exposes Gmail messages/threads as MCP resources
   - Provides tools for email operations (compose, send, search, manage labels)
   - Downloads email content to temporary files instead of returning in tool responses
   - Uses lifespan context manager for resource management (temp directories, Gmail service)
   - All tools return structured Pydantic models

2. **src/gmail.py**: Gmail API client wrapper (thin layer over Google's API)
   - OAuth 2.0 authentication flow
   - Service initialization and management
   - Core Gmail operations (messages, threads, drafts, labels, attachments)
   - Message parsing (extracting body text from complex MIME structures)
   - Returns raw `dict` responses from Gmail API

3. **src/config.py**: Pydantic-based configuration management
   - Reads from environment variables with `MCP_GMAIL_` prefix
   - Supports `.env` file loading
   - Modern Python syntax (`list[str]`, `str | None`)
   - Key settings:
     - `MCP_GMAIL_CREDENTIALS_PATH`: OAuth credentials file
     - `MCP_GMAIL_TOKEN_PATH`: Token storage location
     - `MCP_GMAIL_MAX_RESULTS`: Default search result limit

4. **src/models.py**: Strict Pydantic models for all tool responses
   - Strict validation with `extra='forbid'`, `strict=True`
   - Models: `EmailDownloadResult`, `ThreadDownloadResult`, `SearchResult`, etc.
   - Ensures type safety and fail-fast validation

5. **src/helpers.py**: Utility functions
   - Email formatting (markdown conversion)
   - Date parsing and formatting
   - Metadata extraction
   - Filename sanitization

6. **src/dual_logger.py**: Dual logging implementation
   - `DualLogger` class logs to both stdout (for debugging) and MCP context (for user visibility)
   - Async-compatible logging with timestamps

### Authentication Flow

The server uses OAuth 2.0 with Gmail API scopes for full access. On first run, it opens a browser for authorization and stores the token locally for reuse.

### File-Based Response Pattern

**Key Innovation**: Instead of returning large email content in tool responses (consuming many tokens), emails are downloaded to temporary files:

1. **Tools download to temp files**: `search_emails()`, `get_emails()`, `get_thread()` write email content to markdown files in a temporary directory
2. **Tool responses return metadata**: File path, size, and structured metadata (subject, from, date, etc.)
3. **User reads files as needed**: Use the `Read` tool to access downloaded files selectively
4. **Automatic cleanup**: Temp directory is automatically cleaned up when server shuts down

**Benefits:**
- Dramatically reduces token usage for large email threads
- User has control over what content to read
- Full email content always preserved in files
- Metadata immediately available in tool responses

### MCP Resources and Tools

**Resources** (return full content directly):
- `gmail://messages/{message_id}`: Individual email message as markdown
- `gmail://threads/{thread_id}`: Email conversation thread as markdown

**Tools** (async, return Pydantic models):

*Email retrieval (file-based):*
- `search_emails()` → `SearchResult` (path to file with all results + metadata list)
- `get_emails()` → `list[EmailDownloadResult]` (path for each email + metadata)
- `get_thread()` → `ThreadDownloadResult` (path to thread file + metadata)

*Email operations:*
- `create_draft()` → `DraftCreatedResult`
- `send_email()` → `EmailSentResult`

*Label management:*
- `list_labels()` → `list[LabelInfo]`
- `add_label()` → `LabelOperationResult`
- `remove_label()` → `LabelOperationResult`

*Attachment handling:*
- `list_attachments()` → `list[AttachmentInfo]`
- `download_attachment()` → `DownloadedAttachment` (path to temp file)

### Code Standards

- **Python 3.11+** with modern type hints
- **Modern syntax**: Use `str | None` (not `Optional[str]`), `list[str]` (not `List[str]`), `dict[str, Any]` (not `Dict[str, Any]`)
- **Async everywhere**: All MCP tools are async functions
- **Strict Pydantic models**: All tool responses use Pydantic models with strict validation
- **Type hints on all functions**: Full typing throughout codebase
- **Line length**: 108 characters
- **Formatting**: ruff (configured in pyproject.toml)
- **Pre-commit hooks**: Enforce formatting and linting before commits
- **Error handling**: All Gmail API calls should have appropriate error handling
- **Dual logging**: Use `DualLogger(ctx)` in all tools for visibility

### Project Structure

```
gmail-mcp/
├── src/                      # Main source code (replaces old mcp_gmail/)
│   ├── __init__.py          # Package initialization
│   ├── server.py            # MCP server with file-based responses
│   ├── gmail.py             # Gmail API client wrapper
│   ├── config.py            # Configuration management
│   ├── models.py            # Pydantic models (strict validation)
│   ├── helpers.py           # Utility functions
│   └── dual_logger.py       # Dual logging implementation
├── tests/                   # Test suite
│   ├── test_config.py       # Configuration tests
│   └── conftest.py          # Pytest configuration
├── scripts/                 # Utility scripts
│   └── test_gmail_setup.py  # Test Gmail API connection
├── pyproject.toml           # Project configuration
├── CLAUDE.md                # This file
└── README.md                # User documentation
```

### Key Design Patterns

1. **Lifespan management**: FastMCP lifespan context manager handles resource initialization and cleanup
2. **Temporary file pattern**: Download large content to temp files, return paths + metadata
3. **Strict validation**: Pydantic models with `extra='forbid'` catch API changes immediately
4. **Dual logging**: Log to both stdout (debugging) and MCP context (user visibility)
5. **Async by default**: All tools are async for better performance
6. **Tool annotations**: Use `ToolAnnotations` to indicate read-only and idempotent operations
7. **Separation of concerns**: Low-level Gmail wrappers (dict responses) vs high-level MCP tools (Pydantic models)

### Breaking Changes from Previous Version

- **File-based responses**: `search_emails()` and `get_emails()` now return file paths instead of inline content
- **No `fields` parameter**: All tools return full metadata + file paths; files contain complete email content
- **Pydantic return types**: All tools return Pydantic models instead of formatted strings
- **Async tools**: All tools now require `await` and take `Context` parameter
- **Import path**: Changed from `mcp_gmail.*` to `src.*`
