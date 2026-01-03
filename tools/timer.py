#!/usr/bin/env python3
"""Timer and alarm tool with SQLite persistence.

CLI:
    uv run timer 5m                      # Timer for 5 minutes
    uv run timer 5m --label "eggs"       # Timer with label
    uv run timer 7:00am                  # Alarm for 7:00 AM
    uv run timer 7:00am --label "wakeup" # Alarm with label
    uv run timer --list                  # List active timers
    uv run timer --cancel eggs           # Cancel by label or ID
    uv run timer --edit eggs 10m         # Edit timer duration

Tool: Registered as SetTimer, ListTimers, CancelTimer, EditTimer
"""

import argparse
import re
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, Field

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "timers.db"


def _ensure_db() -> sqlite3.Connection:
    """Ensure database and table exist, return connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS timers (
            id TEXT PRIMARY KEY,
            label TEXT,
            fire_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _parse_time_input(time_str: str) -> datetime:
    """Parse duration (5m, 1h30m) or time (7:00am, 14:30) to absolute datetime."""
    time_str = time_str.strip().lower()
    now = datetime.now()

    # Duration pattern: 5m, 1h, 1h30m, 90s, etc.
    duration_pattern = r'^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$'
    match = re.match(duration_pattern, time_str)
    if match and any(match.groups()):
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return now + timedelta(hours=hours, minutes=minutes, seconds=seconds)

    # Time pattern: 7:00, 7:00am, 7:00pm, 14:30
    time_pattern = r'^(\d{1,2}):(\d{2})\s*(am|pm)?$'
    match = re.match(time_pattern, time_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        period = match.group(3)

        if period == 'pm' and hour != 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0

        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # If time already passed today, schedule for tomorrow
        if target <= now:
            target += timedelta(days=1)
        return target

    raise ValueError(f"Cannot parse time: '{time_str}'. Use duration (5m, 1h30m) or time (7:00am, 14:30)")


def _format_remaining(fire_at: datetime) -> str:
    """Format time remaining as human-readable string."""
    now = datetime.now()
    if fire_at <= now:
        return "now"

    delta = fire_at - now
    total_seconds = int(delta.total_seconds())

    if total_seconds < 60:
        return f"{total_seconds}s"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}m {seconds}s" if seconds else f"{minutes}m"
    else:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"


def _generate_id() -> str:
    """Generate short unique ID."""
    return uuid.uuid4().hex[:8]


# ─── Core Functions ─────────────────────────────────────────────────────────


def create_timer(time_input: str, label: str | None = None) -> str:
    """Create a new timer or alarm."""
    try:
        fire_at = _parse_time_input(time_input)
    except ValueError as e:
        return str(e)

    timer_id = _generate_id()
    now = datetime.now()

    conn = _ensure_db()
    try:
        conn.execute(
            "INSERT INTO timers (id, label, fire_at, created_at) VALUES (?, ?, ?, ?)",
            (timer_id, label, fire_at.isoformat(), now.isoformat())
        )
        conn.commit()
    finally:
        conn.close()

    remaining = _format_remaining(fire_at)
    label_str = f" '{label}'" if label else ""
    time_str = fire_at.strftime("%I:%M %p").lstrip("0")

    return f"Timer{label_str} set for {remaining} (fires at {time_str})"


def list_timers() -> str:
    """List all active timers."""
    conn = _ensure_db()
    try:
        now = datetime.now()
        # Clean up expired timers
        conn.execute("DELETE FROM timers WHERE fire_at < ?", (now.isoformat(),))
        conn.commit()

        rows = conn.execute(
            "SELECT id, label, fire_at FROM timers ORDER BY fire_at"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return "No active timers"

    lines = []
    for row in rows:
        fire_at = datetime.fromisoformat(row["fire_at"])
        remaining = _format_remaining(fire_at)
        time_str = fire_at.strftime("%I:%M %p").lstrip("0")

        if row["label"]:
            lines.append(f"• {row['label']} - {remaining} (at {time_str}) [{row['id']}]")
        else:
            lines.append(f"• {remaining} (at {time_str}) [{row['id']}]")

    return "\n".join(lines)


def cancel_timer(identifier: str) -> str:
    """Cancel a timer by label or ID."""
    conn = _ensure_db()
    try:
        # Try to find by label first, then by ID
        row = conn.execute(
            "SELECT id, label FROM timers WHERE label = ? OR id = ? OR id LIKE ?",
            (identifier, identifier, f"{identifier}%")
        ).fetchone()

        if not row:
            return f"No timer found matching '{identifier}'"

        conn.execute("DELETE FROM timers WHERE id = ?", (row["id"],))
        conn.commit()
    finally:
        conn.close()

    label_str = f"'{row['label']}'" if row["label"] else row["id"]
    return f"Cancelled timer {label_str}"


def edit_timer(identifier: str, new_time: str) -> str:
    """Edit an existing timer's time."""
    try:
        fire_at = _parse_time_input(new_time)
    except ValueError as e:
        return str(e)

    conn = _ensure_db()
    try:
        row = conn.execute(
            "SELECT id, label FROM timers WHERE label = ? OR id = ? OR id LIKE ?",
            (identifier, identifier, f"{identifier}%")
        ).fetchone()

        if not row:
            return f"No timer found matching '{identifier}'"

        conn.execute(
            "UPDATE timers SET fire_at = ? WHERE id = ?",
            (fire_at.isoformat(), row["id"])
        )
        conn.commit()
    finally:
        conn.close()

    remaining = _format_remaining(fire_at)
    time_str = fire_at.strftime("%I:%M %p").lstrip("0")
    label_str = f"'{row['label']}'" if row["label"] else row["id"]

    return f"Updated timer {label_str} to {remaining} (fires at {time_str})"


def get_expired_timers() -> list[dict]:
    """Get and remove expired timers. Called by daemon."""
    conn = _ensure_db()
    try:
        now = datetime.now()
        rows = conn.execute(
            "SELECT id, label, fire_at FROM timers WHERE fire_at <= ?",
            (now.isoformat(),)
        ).fetchall()

        if rows:
            conn.execute("DELETE FROM timers WHERE fire_at <= ?", (now.isoformat(),))
            conn.commit()

        return [dict(row) for row in rows]
    finally:
        conn.close()


# ─── Pydantic Models for OpenAI Tools ───────────────────────────────────────


class SetTimer(BaseModel):
    """Set a timer (duration like 5m, 1h30m) or alarm (time like 7:00am, 14:30)."""

    time: str = Field(description="Duration (5m, 1h30m, 90s) or time (7:00am, 14:30)")
    label: str | None = Field(default=None, description="Optional label for the timer")


class ListTimers(BaseModel):
    """List all active timers and alarms."""
    pass


class CancelTimer(BaseModel):
    """Cancel a timer or alarm by its label or ID."""

    identifier: str = Field(description="Timer label or ID to cancel")


class EditTimer(BaseModel):
    """Change the time of an existing timer or alarm."""

    identifier: str = Field(description="Timer label or ID to edit")
    new_time: str = Field(description="New duration (5m, 1h30m) or time (7:00am, 14:30)")


# ─── Tool Handlers ──────────────────────────────────────────────────────────


def set_timer_handler(params: SetTimer) -> str:
    return create_timer(params.time, params.label)


def list_timers_handler(params: ListTimers) -> str:
    return list_timers()


def cancel_timer_handler(params: CancelTimer) -> str:
    return cancel_timer(params.identifier)


def edit_timer_handler(params: EditTimer) -> str:
    return edit_timer(params.identifier, params.new_time)


# ─── CLI ────────────────────────────────────────────────────────────────────


def main() -> None:
    """CLI entry point with subcommand-style interface."""
    parser = argparse.ArgumentParser(
        description="Timer and alarm management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run timer 5m                    Set 5 minute timer
  uv run timer 1h30m --label pizza   Set 1.5 hour timer with label
  uv run timer 7:00am                Set alarm for 7:00 AM
  uv run timer --list                List active timers
  uv run timer --cancel pizza        Cancel timer by label
  uv run timer --edit pizza 2h       Change timer to 2 hours
        """
    )

    parser.add_argument("time", nargs="?", help="Duration (5m, 1h30m) or time (7:00am)")
    parser.add_argument("--label", "-l", help="Label for the timer")
    parser.add_argument("--list", action="store_true", help="List active timers")
    parser.add_argument("--cancel", "-c", metavar="ID", help="Cancel timer by label or ID")
    parser.add_argument("--edit", "-e", nargs=2, metavar=("ID", "TIME"),
                        help="Edit timer: --edit <label/id> <new_time>")

    args = parser.parse_args()

    if args.list:
        print(list_timers())
    elif args.cancel:
        print(cancel_timer(args.cancel))
    elif args.edit:
        print(edit_timer(args.edit[0], args.edit[1]))
    elif args.time:
        print(create_timer(args.time, args.label))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
else:
    # Register tools when imported
    from tools.base import tool
    tool(SetTimer)(set_timer_handler)
    tool(ListTimers)(list_timers_handler)
    tool(CancelTimer)(cancel_timer_handler)
    tool(EditTimer)(edit_timer_handler)
