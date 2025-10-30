"""Dual logging utilities for Gmail MCP server."""

from datetime import datetime

from mcp.server.fastmcp import Context


class DualLogger:
    """Logs messages to both stdout and MCP client context."""

    def __init__(self, ctx: Context):
        self.ctx = ctx

    def _timestamp(self) -> str:
        """Generate timestamp for log messages."""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    async def info(self, msg: str):
        """Log info message to both stdout and MCP context."""
        print(f'[{self._timestamp()}] [INFO] {msg}')
        await self.ctx.info(msg)

    async def debug(self, msg: str):
        """Log debug message to both stdout and MCP context."""
        print(f'[{self._timestamp()}] [DEBUG] {msg}')
        await self.ctx.debug(msg)

    async def warning(self, msg: str):
        """Log warning message to both stdout and MCP context."""
        print(f'[{self._timestamp()}] [WARNING] {msg}')
        await self.ctx.warning(msg)

    async def error(self, msg: str):
        """Log error message to both stdout and MCP context."""
        print(f'[{self._timestamp()}] [ERROR] {msg}')
        await self.ctx.error(msg)
