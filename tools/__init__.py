"""Tool registry."""

# Import base functionality
from tools.base import execute_tool, get_tools

# Import tools to trigger registration
from tools import weather  # noqa: F401

# Export registered tools
TOOLS = get_tools()

__all__ = ["TOOLS", "execute_tool"]
