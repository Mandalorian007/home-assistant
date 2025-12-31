---
name: Playwright
description: Browser automation using Playwright. Use for web scraping, UI testing, taking screenshots, form interaction, and any browser-based tasks. Keywords: browser, playwright, chromium, screenshot, scrape, test, click, type, navigate.
---

# Playwright

Browser automation using Playwright's isolated Chromium. Runs locally without affecting your Chrome browser.

## Variables

- **PLAYWRIGHT_CLI_PATH**: `.claude/skills/playwright/playwright_cli/`

## Instructions

Run from PLAYWRIGHT_CLI_PATH:
```bash
cd .claude/skills/playwright/playwright_cli/
uv run pw --help                   # Discover all commands
uv run pw <command> --help         # Detailed usage
```

**Rules:**
- **Initialize once**: `uv run pw init` (installs Chromium)
- **Stateful sessions**: Start browser, run commands, then close
- **Use `--port` for parallel sessions** - each needs unique port (9222-9999)

## Multi-Agent Safety

Each agent MUST use a unique port and close only its own browser:
```bash
uv run pw start --port 9223
uv run pw nav <url> --port 9223
uv run pw close --port 9223
```

## Troubleshooting

- **"Browser not initialized"**: Run `uv run pw init`
- **"Port in use"**: Use different port or `uv run pw close --port XXXX`
- **"Could not connect"**: Start browser first with `uv run pw start`
- **"Failed to click/type"**: Use `uv run pw a11y` to understand page structure
