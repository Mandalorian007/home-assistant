"""Time tool."""

from datetime import datetime


TIME_TOOL = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "Get the current date and time",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}


def get_current_time() -> str:
    """Get the current date and time.

    Returns:
        Current date and time as human-readable string
    """
    now = datetime.now()
    return now.strftime("It is %I:%M %p on %A, %B %d, %Y")
