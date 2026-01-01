#!/usr/bin/env python3
"""News tool using BBC News API.

CLI: uv run news
Tool: Registered as GetNews for OpenAI function calling
"""

import httpx
from pydantic import BaseModel

BBC_NEWS_URL = "https://bbc-news-api.vercel.app/news?lang=english"

# Interest profile for selecting top stories
INTEREST_GUIDANCE = """
Select the top 5 most interesting articles based on this profile:

HIGH PRIORITY (report these first):
- AI, agentic engineering, big tech (OpenAI, Anthropic, Meta, Google AI, agents, models, chips, regulation)
- Major world events, breaking news, significant geopolitical developments
- US politics and policy with real impact
- NYC/NJ local: transit (MTA, PATH, NJ Transit), housing, zoning, mayor
- Finance, markets, business regulation, crypto, layoffs

MEDIUM PRIORITY:
- Gaming industry, live-service games, creator economy
- Science and technology breakthroughs
- Business operations, startups, acquisitions

LOW PRIORITY (skip unless exceptional):
- Celebrity news, entertainment gossip
- Sports (unless historic/major upset)
- Generic travel, food, lifestyle listicles
- Repeated coverage of same story (pick best one)

When reporting, be concise: give headline + 1 sentence on why it matters.
"""


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    if not url:
        return ""
    # Fix common BBC URL bugs
    url = url.replace("bbc.comhttps://", "https://")
    # Strip tracking parameters
    if "?" in url:
        url = url.split("?")[0]
    return url.strip()


def _extract_articles(data: dict) -> list[dict]:
    """Extract and dedupe articles from BBC API response."""
    seen_urls: set[str] = set()
    articles: list[dict] = []

    # API returns sections as top-level keys (e.g., "Latest", "World", etc.)
    for section, items in data.items():
        if section == "status" or not isinstance(items, list):
            continue

        for item in items:
            # Get the URL for deduplication
            url = _normalize_url(item.get("news_link", ""))
            if not url or url in seen_urls:
                continue

            title = (item.get("title") or "").strip()
            if not title:
                continue

            seen_urls.add(url)
            articles.append({
                "title": title,
                "summary": (item.get("summary") or "").strip(),
                "section": section,
                "url": url,
            })

    return articles


class GetNews(BaseModel):
    """Get the latest news headlines. Returns top stories for you to select the most interesting."""

    pass


def get_news(params: GetNews) -> str:
    """Fetch news from BBC and return with selection guidance."""
    try:
        resp = httpx.get(BBC_NEWS_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        articles = _extract_articles(data)

        if not articles:
            return "No news articles found."

        # Build response with all articles and guidance
        lines = [f"Found {len(articles)} articles.\n"]
        lines.append(INTEREST_GUIDANCE)
        lines.append("\n--- ARTICLES ---\n")

        for i, article in enumerate(articles, 1):
            lines.append(f"{i}. [{article['section']}] {article['title']}")
            if article["summary"]:
                lines.append(f"   {article['summary']}")
            lines.append("")

        return "\n".join(lines)

    except httpx.HTTPError as e:
        return f"News service error: {e}"


# ─── Dual Mode: CLI + Tool ─────────────────────────────────────────────────

def main() -> None:
    """CLI entry point."""
    from tools.base import run
    run(GetNews, get_news)


if __name__ == "__main__":
    main()
else:
    from tools.base import tool
    tool(GetNews)(get_news)
