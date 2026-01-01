"""SQLite-based conversation history storage."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "history.db"
MAX_HISTORY = 20


def _get_connection() -> sqlite3.Connection:
    """Get database connection, creating table if needed."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            user_input TEXT NOT NULL,
            final_response TEXT NOT NULL,
            tool_calls TEXT
        )
    """)
    conn.commit()
    return conn


def save_conversation(
    user_input: str,
    final_response: str,
    tool_calls: list[dict[str, Any]] | None = None,
) -> None:
    """Save a conversation and prune to MAX_HISTORY records."""
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO history (timestamp, user_input, final_response, tool_calls)
            VALUES (?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(),
                user_input,
                final_response,
                json.dumps(tool_calls) if tool_calls else None,
            ),
        )
        # Prune old records
        conn.execute(
            """
            DELETE FROM history WHERE id NOT IN (
                SELECT id FROM history ORDER BY id DESC LIMIT ?
            )
            """,
            (MAX_HISTORY,),
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_history(limit: int = 20) -> list[dict[str, Any]]:
    """Get recent conversation history, newest first."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            """
            SELECT timestamp, user_input, final_response, tool_calls
            FROM history ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                "timestamp": row["timestamp"],
                "user_input": row["user_input"],
                "final_response": row["final_response"],
                "tool_calls": json.loads(row["tool_calls"]) if row["tool_calls"] else [],
            }
            for row in rows
        ]
    finally:
        conn.close()


def search_history(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search history by user input or response text."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            """
            SELECT timestamp, user_input, final_response, tool_calls
            FROM history
            WHERE user_input LIKE ? OR final_response LIKE ?
            ORDER BY id DESC LIMIT ?
            """,
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        return [
            {
                "timestamp": row["timestamp"],
                "user_input": row["user_input"],
                "final_response": row["final_response"],
                "tool_calls": json.loads(row["tool_calls"]) if row["tool_calls"] else [],
            }
            for row in rows
        ]
    finally:
        conn.close()
