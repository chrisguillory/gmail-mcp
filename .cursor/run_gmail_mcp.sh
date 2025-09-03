#!/bin/bash

# MCP server wrapper that ensures direnv is loaded before running the Gmail MCP server

# Unofficial bash strict mode - http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The script is in .cursor/, so go up one level to get to the mcp-gmail root
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to the repo root to ensure we're in the right context
cd "$REPO_ROOT"

# Load direnv environment (this will load .envrc-personal and any other .envrc files)
# Check if direnv is available, if not try to source .envrc-personal directly
if command -v direnv &> /dev/null; then
    eval "$(direnv export bash)"
else
    # Fallback: directly source the .envrc-personal file if direnv is not available
    if [ -f "$REPO_ROOT/.envrc-personal" ]; then
        source "$REPO_ROOT/.envrc-personal"
    fi
fi

# Verify the Gmail credentials are available
if [ -z "${MCP_GMAIL_CREDENTIALS_PATH:-}" ]; then
    echo "Error: MCP_GMAIL_CREDENTIALS_PATH environment variable is not set" >&2
    # Show dialog to user
    osascript -e 'display dialog "Missing Gmail Credentials Path\n\nAdd the following to mcp-gmail/.envrc-personal:\nexport MCP_GMAIL_CREDENTIALS_PATH=\"./credentials.json\"\n\nMake sure you have set up OAuth credentials as described in the README." buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

if [ -z "${MCP_GMAIL_TOKEN_PATH:-}" ]; then
    echo "Error: MCP_GMAIL_TOKEN_PATH environment variable is not set" >&2
    # Show dialog to user
    osascript -e 'display dialog "Missing Gmail Token Path\n\nAdd the following to mcp-gmail/.envrc-personal:\nexport MCP_GMAIL_TOKEN_PATH=\"./token.json\"\n\nThis file will be created after the first authentication." buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

# Check if credentials file exists
if [ ! -f "${MCP_GMAIL_CREDENTIALS_PATH}" ]; then
    echo "Error: Credentials file not found at ${MCP_GMAIL_CREDENTIALS_PATH}" >&2
    osascript -e 'display dialog "Gmail Credentials File Not Found\n\nThe credentials file was not found at:\n'${MCP_GMAIL_CREDENTIALS_PATH}'\n\nPlease follow the setup instructions in the README to create OAuth credentials:\n1. Go to Google Cloud Console\n2. Create OAuth 2.0 credentials\n3. Download the credentials JSON file\n4. Save it as credentials.json in the project root" buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

# Check if Python/uv is available
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed or not in PATH" >&2
    osascript -e 'display dialog "uv Not Found\n\nuv is required to run the Gmail MCP server.\n\nInstall uv with:\ncurl -LsSf https://astral.sh/uv/install.sh | sh\n\nOr via Homebrew:\nbrew install uv" buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Creating one..."
    uv venv
    uv pip install -e .
fi

# Run the Gmail MCP server with the loaded environment variables
echo "Starting Gmail MCP server..."
echo "======================================"
echo "Configuration:"
echo "  Credentials: ${MCP_GMAIL_CREDENTIALS_PATH}"
echo "  Token: ${MCP_GMAIL_TOKEN_PATH}"
echo "  User ID: ${MCP_GMAIL_USER_ID:-me}"
echo "  Max Results: ${MCP_GMAIL_MAX_RESULTS:-10}"
echo "======================================"
echo ""
echo "If this is your first run, a browser will open for authentication."
echo "Press Ctrl+C to stop the server."
echo ""

# Run the MCP server
exec uv run python -m mcp_gmail.server
