"""Tool registry."""

# Import base functionality
from tools.base import execute_tool, get_tools

# Import tools to trigger registration
from tools import weather  # noqa: F401
from tools import search  # noqa: F401
from tools import news  # noqa: F401
from tools import history  # noqa: F401
from tools import device_volume  # noqa: F401

# Export registered tools
TOOLS = get_tools()

__all__ = ["TOOLS", "execute_tool"]
