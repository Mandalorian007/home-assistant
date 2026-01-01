#!/usr/bin/env python3
"""Internet search tool using Perplexity API.

CLI: uv run search "your query here"
Tool: Registered as SearchInternet for OpenAI function calling
"""

import os
import re
import httpx
from pydantic import BaseModel, Field

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"


def _clean_for_speech(text: str) -> str:
    """Remove markdown formatting for TTS output."""
    # Remove citation references like [1], [2], etc.
    text = re.sub(r"\[\d+\]", "", text)
    # Remove bold/italic markers
    text = re.sub(r"\*+", "", text)
    # Remove links but keep text: [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Clean up extra whitespace
    text = re.sub(r"  +", " ", text)
    return text.strip()


def _get_api_key() -> str | None:
    """Get Perplexity API key from environment."""
    return os.environ.get("PERPLEXITY_API_KEY")


def _search(query: str, api_key: str) -> dict:
    """Execute search via Perplexity API."""
    response = httpx.post(
        PERPLEXITY_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "sonar",
            "messages": [{"role": "user", "content": query}],
        },
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()


class SearchInternet(BaseModel):
    """Search the internet for current information, news, or to answer questions that require up-to-date knowledge."""

    query: str = Field(description="The search query")


def search_internet(params: SearchInternet) -> str:
    """Search the internet using Perplexity API."""
    api_key = _get_api_key()
    if not api_key:
        return "Search unavailable: PERPLEXITY_API_KEY not configured"

    try:
        data = _search(params.query, api_key)
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not content:
            return "No results found for your search."

        return _clean_for_speech(content)

    except httpx.HTTPStatusError as e:
        return f"Search error: API returned status {e.response.status_code}"
    except httpx.HTTPError as e:
        return f"Search error: {e}"


# ─── Dual Mode: CLI + Tool ─────────────────────────────────────────────────

def main() -> None:
    """CLI entry point."""
    from tools.base import run
    run(SearchInternet, search_internet)


if __name__ == "__main__":
    main()
else:
    from tools.base import tool
    tool(SearchInternet)(search_internet)
