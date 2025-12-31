"""Tool registry base with decorator pattern."""

from typing import Callable, TypeVar
from pydantic import BaseModel
from openai import pydantic_function_tool

T = TypeVar("T", bound=BaseModel)

# Internal registries
_TOOLS: list = []
_HANDLERS: dict[str, tuple[type[BaseModel], Callable]] = {}


def tool(model: type[T]) -> Callable[[Callable[[T], str]], Callable[[T], str]]:
    """Decorator to register a tool with its Pydantic model.

    Usage:
        @tool(GetWeather)
        def get_weather(params: GetWeather) -> str:
            return f"Weather in {params.location}..."
    """
    def decorator(func: Callable[[T], str]) -> Callable[[T], str]:
        _TOOLS.append(pydantic_function_tool(model))
        _HANDLERS[model.__name__] = (model, func)
        return func
    return decorator


def execute_tool(name: str, args: dict) -> str:
    """Execute a tool by name with given arguments."""
    if name not in _HANDLERS:
        return f"Error: Unknown tool '{name}'"

    model_class, handler = _HANDLERS[name]
    try:
        params = model_class(**args)
        return handler(params)
    except Exception as e:
        return f"Error executing {name}: {e}"


def get_tools() -> list:
    """Get all registered tools."""
    return _TOOLS
