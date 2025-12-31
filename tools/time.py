"""Time tool."""

from datetime import datetime
from pydantic import BaseModel
from tools.base import tool


class GetCurrentTime(BaseModel):
    """Get the current date and time."""

    pass


@tool(GetCurrentTime)
def get_current_time(_: GetCurrentTime) -> str:
    now = datetime.now()
    return now.strftime("It is %I:%M %p on %A, %B %d, %Y")
