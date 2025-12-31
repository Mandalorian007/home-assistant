"""Tool registry and execution."""

from typing import Any, Callable

from tools.weather import get_weather, WEATHER_TOOL
from tools.time import get_current_time, TIME_TOOL

# Tool definitions for OpenAI API
TOOLS = [
    WEATHER_TOOL,
    TIME_TOOL,
]

# Tool function registry
_TOOL_FUNCTIONS: dict[str, Callable[..., str]] = {
    "get_weather": get_weather,
    "get_current_time": get_current_time,
}


def register_tool(name: str, func: Callable[..., str], schema: dict[str, Any]) -> None:
    """Register a new tool.

    Args:
        name: Tool function name
        func: Tool function implementation
        schema: OpenAI tool schema
    """
    _TOOL_FUNCTIONS[name] = func
    TOOLS.append(schema)


def execute_tool(name: str, args: dict[str, Any]) -> str:
    """Execute a tool by name.

    Args:
        name: Tool function name
        args: Tool arguments

    Returns:
        Tool result as string
    """
    if name not in _TOOL_FUNCTIONS:
        return f"Error: Unknown tool '{name}'"

    try:
        return _TOOL_FUNCTIONS[name](**args)
    except Exception as e:
        return f"Error executing {name}: {e}"
