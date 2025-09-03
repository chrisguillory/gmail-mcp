#!/bin/bash

# MCP server wrapper that runs the Gmail MCP server in Docker with live logs
# This version uses Docker Compose for better log visibility and management

# Unofficial bash strict mode - http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The script is in .cursor/, so go up one level to get to the mcp-gmail root
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to the repo root to ensure we're in the right context
cd "$REPO_ROOT"

# Load direnv environment (this will load .envrc-personal and any other .envrc files)
eval "$(direnv export bash)"

# Check if Gmail credentials environment variables are available
if [ -z "${MCP_GMAIL_CREDENTIALS_PATH:-}" ] || [ -z "${MCP_GMAIL_TOKEN_PATH:-}" ]; then
    echo "Error: Gmail MCP environment variables not found" >&2
    # Show dialog to user
    osascript -e 'display dialog "Missing Gmail MCP Configuration\n\nAdd the following to mcp-gmail/.envrc-personal:\nexport MCP_GMAIL_CREDENTIALS_PATH=\"./credentials.json\"\nexport MCP_GMAIL_TOKEN_PATH=\"./token.json\"\n\nOr set them directly in your shell environment." buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

# Verify Docker is available
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in PATH" >&2
    osascript -e 'display dialog "Docker Not Found\n\nDocker is not installed or not in PATH.\n\nPlease install Docker Desktop from:\nhttps://www.docker.com/products/docker-desktop\n\nOr ensure it is in your PATH." buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

# Verify Docker daemon is running
if ! docker info &> /dev/null; then
    echo "Error: Docker daemon is not running" >&2
    osascript -e 'display dialog "Docker Not Running\n\nDocker is installed but not running.\n\nPlease start Docker Desktop and try again." buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

# Verify Docker Compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "Error: Docker Compose is not installed" >&2
    osascript -e 'display dialog "Docker Compose Not Found\n\nDocker Compose is not installed.\n\nIt should come with Docker Desktop.\n\nPlease ensure Docker Desktop is properly installed." buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

# Determine docker-compose command (v1 vs v2)
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# Pull/update the uv image if needed
echo "Ensuring uv Docker image is up to date..."
docker pull ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Clean up any existing container
echo "Cleaning up any existing container..."
$DOCKER_COMPOSE -f docker-compose.local.yml down 2>/dev/null || true

# Start the MCP server with Docker Compose
echo "Starting Gmail MCP server with Docker Compose..."
echo "======================================"
echo "Configuration:"
echo "  Credentials: ${MCP_GMAIL_CREDENTIALS_PATH}"
echo "  Token: ${MCP_GMAIL_TOKEN_PATH}"
echo "  User ID: ${MCP_GMAIL_USER_ID:-me}"
echo "  Max Results: ${MCP_GMAIL_MAX_RESULTS:-10}"
echo "======================================"
echo "Logs will appear below. Press Ctrl+C to stop."
echo "======================================"
echo ""

# Run with docker-compose run for proper stdio handling with Cursor
# The 'run' command connects stdin/stdout properly for MCP communication
exec $DOCKER_COMPOSE -f docker-compose.local.yml run --rm gmail-mcp-local
