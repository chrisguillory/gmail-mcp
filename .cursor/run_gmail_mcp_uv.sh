#!/bin/bash

# MCP server wrapper that runs the Gmail MCP server with uv (no Docker)

set -euo pipefail

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to the repo root
cd "$REPO_ROOT"

# Load environment variables from .env file if it exists
if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    source "$REPO_ROOT/.env"
    set +a
fi

# Load direnv if available
if command -v direnv &> /dev/null; then
    eval "$(direnv export bash 2>/dev/null)" || true
fi

# Run the MCP server with uv
exec uv run python src/server.py
