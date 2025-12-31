"""Firecrawl CLI - Web scraping and URL discovery."""

import json
import os
import sys
from pathlib import Path

import click
from firecrawl import Firecrawl


def get_api_key() -> str | None:
    """Get API key from environment or .env file."""
    if key := os.environ.get("FIRECRAWL_API_KEY"):
        return key

    current = Path.cwd()
    for _ in range(10):
        env_file = current / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                if k.strip() == "FIRECRAWL_API_KEY":
                    value = v.strip().strip('"').strip("'")
                    if value:
                        return value
            break
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def get_client() -> Firecrawl:
    """Get authenticated Firecrawl client."""
    api_key = get_api_key()
    if not api_key:
        click.echo("Error: FIRECRAWL_API_KEY not found", err=True)
        click.echo("Add to .env: FIRECRAWL_API_KEY=fc-...", err=True)
        sys.exit(1)
    return Firecrawl(api_key=api_key)


@click.group()
def cli():
    """Firecrawl CLI - Web scraping and URL discovery."""
    pass


@cli.command()
@click.argument("url")
@click.option("--only-main", is_flag=True, help="Extract only main content (skip nav, footer, etc.)")
def scrape(url: str, only_main: bool):
    """
    Scrape a URL and return markdown content.

    \b
    EXAMPLES
    --------
    uv run fc scrape https://example.com
    uv run fc scrape https://docs.example.com/api --only-main
    """
    client = get_client()

    try:
        result = client.scrape(
            url,
            formats=["markdown"],
            only_main_content=only_main if only_main else None,
        )

        # Handle both dict and object responses
        if hasattr(result, "markdown"):
            markdown = result.markdown
        elif isinstance(result, dict):
            markdown = result.get("markdown", "")
        else:
            markdown = str(result)

        if markdown:
            click.echo(markdown)
        else:
            click.echo("No content extracted", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("url")
@click.option("--search", "-s", help="Filter URLs by search term (ranked by relevance)")
@click.option("--limit", "-l", default=100, help="Maximum URLs to return (default: 100)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON with titles/descriptions")
def map(url: str, search: str | None, limit: int, as_json: bool):
    """
    Discover all URLs on a website.

    \b
    EXAMPLES
    --------
    uv run fc map https://example.com
    uv run fc map https://docs.example.com --search "authentication"
    uv run fc map https://example.com --limit 50 --json
    """
    client = get_client()

    try:
        options = {"limit": limit}
        if search:
            options["search"] = search

        result = client.map(url, **options)

        # Handle response format
        if hasattr(result, "links"):
            links = result.links
        elif isinstance(result, dict):
            links = result.get("links", [])
        elif isinstance(result, list):
            links = result
        else:
            links = []

        if not links:
            click.echo("No URLs found", err=True)
            sys.exit(1)

        if as_json:
            # Output full details as JSON
            output = []
            for link in links:
                if isinstance(link, dict):
                    output.append(link)
                elif hasattr(link, "url"):
                    output.append({
                        "url": link.url,
                        "title": getattr(link, "title", None),
                        "description": getattr(link, "description", None),
                    })
                else:
                    output.append({"url": str(link)})
            click.echo(json.dumps(output, indent=2))
        else:
            # Output just URLs, one per line
            for link in links:
                if isinstance(link, dict):
                    click.echo(link.get("url", link))
                elif hasattr(link, "url"):
                    click.echo(link.url)
                else:
                    click.echo(str(link))

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
