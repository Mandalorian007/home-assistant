"""Internet Search CLI - Web search powered by Perplexity API."""

import os
import sys
from pathlib import Path

import click
import httpx


def get_api_key() -> str | None:
    """Get API key from environment or .env file."""
    if key := os.environ.get("PERPLEXITY_API_KEY"):
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
                if k.strip() == "PERPLEXITY_API_KEY":
                    value = v.strip().strip('"').strip("'")
                    if value:
                        return value
            break
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


@click.command()
@click.argument("query")
def cli(query: str):
    """
    Search the internet and return results with sources.

    \b
    EXAMPLES
    --------
    uv run search "latest AI developments"
    uv run search "Python 3.12 new features"
    uv run search "breaking tech news today"
    """
    api_key = get_api_key()
    if not api_key:
        click.echo("Error: PERPLEXITY_API_KEY not found", err=True)
        click.echo("Add to .env: PERPLEXITY_API_KEY=pplx-...", err=True)
        sys.exit(1)

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sonar",
                    "messages": [{"role": "user", "content": query}],
                },
            )
            response.raise_for_status()
            data = response.json()

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        sources = data.get("search_results", []) or []

        click.echo(content)

        if sources:
            click.echo("\nSources:")
            for src in sources:
                click.echo(f"- {src.get('title', 'Untitled')}: {src.get('url', '')}")

    except httpx.HTTPStatusError as e:
        click.echo(f"API error: {e.response.status_code}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
