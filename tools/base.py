"""Tool registry with dual-mode support: CLI + OpenAI function calling.

Each tool file can be:
1. Run directly: `uv run tools/weather.py "New York"`
2. Imported as OpenAI tool: `from tools import weather`
"""

import sys
import types
import argparse
from typing import Callable, TypeVar, get_origin, get_args, Union
from pydantic import BaseModel
from pydantic_core import PydanticUndefined
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


def run(model: type[T], handler: Callable[[T], str]) -> None:
    """Run as CLI. Call this in `if __name__ == '__main__'` block.

    Automatically generates CLI arguments from Pydantic model fields:
    - Required fields -> positional arguments
    - Optional fields -> --flag arguments

    Usage:
        if __name__ == "__main__":
            from tools.base import run
            run(GetWeather, get_weather)
    """
    parser = argparse.ArgumentParser(
        description=model.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    for name, field in model.model_fields.items():
        annotation = model.__annotations__[name]
        _add_argument(parser, name, annotation, field)

    args = parser.parse_args()
    params = model(**vars(args))
    print(handler(params))


def _add_argument(
    parser: argparse.ArgumentParser,
    name: str,
    annotation: type,
    field,
) -> None:
    """Convert Pydantic field to argparse argument."""
    help_text = field.description or ""
    # Check if field has a real default value (not PydanticUndefined)
    has_default = (
        field.default is not PydanticUndefined
        and field.default is not None
        or field.default is None and _is_optional_type(annotation)
    )
    is_optional = has_default or _is_optional_type(annotation)

    # Get the base type (unwrap Optional)
    base_type = _get_base_type(annotation)

    if is_optional:
        # Optional fields become --flags
        flag = f"--{name.replace('_', '-')}"
        default = field.default if field.default is not PydanticUndefined else None

        kwargs = {"default": default, "help": help_text}
        if base_type == bool:
            kwargs["action"] = "store_true"
        elif base_type == int:
            kwargs["type"] = int
        elif base_type == float:
            kwargs["type"] = float
        else:
            kwargs["type"] = str

        parser.add_argument(flag, **kwargs)
    else:
        # Required fields become positional arguments
        kwargs = {"help": help_text}
        if base_type == int:
            kwargs["type"] = int
        elif base_type == float:
            kwargs["type"] = float

        parser.add_argument(name, **kwargs)


def _is_optional_type(annotation: type) -> bool:
    """Check if type is Optional[X] (Union[X, None] or X | None)."""
    origin = get_origin(annotation)
    # Handle both typing.Union and types.UnionType (Python 3.10+ | syntax)
    if origin is Union or isinstance(annotation, types.UnionType):
        args = get_args(annotation)
        return type(None) in args
    return False


def _get_base_type(annotation: type) -> type:
    """Get base type, unwrapping Optional if present."""
    origin = get_origin(annotation)
    # Handle both typing.Union and types.UnionType (Python 3.10+ | syntax)
    if origin is Union or isinstance(annotation, types.UnionType):
        args = [a for a in get_args(annotation) if a is not type(None)]
        return args[0] if args else str
    return annotation if isinstance(annotation, type) else str


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
