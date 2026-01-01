#!/usr/bin/env python3
"""History lookup tool for recalling past conversations.

CLI: uv run history                    # show recent conversations
     uv run history --query "weather"  # search for specific topic
     uv run history --limit 10         # show more results
Tool: Registered as GetHistory for OpenAI function calling
"""

from pydantic import BaseModel, Field

from history_store import get_recent_history, search_history


class GetHistory(BaseModel):
    """Look up past conversations with the user. Use when the user references previous interactions or asks about something discussed before."""

    query: str | None = Field(
        default=None,
        description="Search term to find specific conversations, or omit for recent history",
    )
    limit: int = Field(
        default=5,
        description="Number of conversations to return (max 20)",
    )


def get_history(params: GetHistory) -> str:
    """Retrieve past conversations from history."""
    limit = min(params.limit, 20)

    if params.query:
        records = search_history(params.query, limit=limit)
        if not records:
            return f"No past conversations found matching '{params.query}'."
    else:
        records = get_recent_history(limit=limit)
        if not records:
            return "No conversation history available yet."

    lines = []
    for i, record in enumerate(records, 1):
        lines.append(f"[{i}] {record['timestamp']}")
        lines.append(f"User: {record['user_input']}")
        lines.append(f"Assistant: {record['final_response']}")
        if record["tool_calls"]:
            tools_used = ", ".join(tc["name"] for tc in record["tool_calls"])
            lines.append(f"Tools used: {tools_used}")
        lines.append("")

    return "\n".join(lines).strip()


# ─── Dual Mode: CLI + Tool ─────────────────────────────────────────────────

def main() -> None:
    """CLI entry point."""
    from tools.base import run
    run(GetHistory, get_history)


if __name__ == "__main__":
    main()
else:
    from tools.base import tool
    tool(GetHistory)(get_history)
