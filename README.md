# Home Assistant

A minimal voice assistant with wake word detection, speech-to-text, and LLM-powered responses.

## Architecture

```
Microphone → openWakeWord → Record Speech → Whisper STT → GPT-4o → TTS → Speaker
                 ↑                              ↓    ↑
            "Hey Jarvis"                     Tools ──┘
```

| Component | Implementation |
|-----------|----------------|
| Wake Word | [openWakeWord](https://github.com/dscripka/openWakeWord) |
| Speech-to-Text | OpenAI Whisper API |
| LLM | OpenAI Chat API with tools |
| Text-to-Speech | OpenAI TTS API |

## Setup

```bash
# Install dependencies
uv sync

# Configure API keys
cp .env.example .env
# Edit .env with your keys

# Download wake word models
uv run python -c "from openwakeword import utils; utils.download_models()"

# Run
uv run assistant
```

Say "Hey Jarvis" to activate, then speak your command.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *required* | OpenAI API key |
| `PERPLEXITY_API_KEY` | *optional* | Perplexity API key for internet search |
| `WAKE_WORD` | `hey_jarvis` | Wake word (`alexa`, `hey_mycroft`, `hey_jarvis`, `hey_rhasspy`) |
| `SILENCE_THRESHOLD` | `0.5` | Seconds of silence to end recording |
| `MODEL` | `gpt-4o` | OpenAI chat model |
| `TTS_VOICE` | `alloy` | TTS voice (`alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`) |

## Tools

Tools are dual-mode: each works as both a standalone CLI and an OpenAI function tool from a single Pydantic model definition.

### Available Tools

| CLI Command | Tool Name | Description |
|-------------|-----------|-------------|
| `uv run weather` | `GetWeather` | Current weather by location or IP |
| `uv run news` | `GetNews` | Latest BBC news headlines |
| `uv run search <query>` | `SearchInternet` | Internet search via Perplexity |
| `uv run volume [level]` | `GetDeviceVolume` / `SetDeviceVolume` | macOS volume control |
| `uv run history` | `GetHistory` | Past conversation lookup |

### CLI Examples

```bash
uv run weather                        # Weather at current location
uv run weather --location "Tokyo"     # Weather in Tokyo
uv run news                           # Latest headlines
uv run search "Python 3.12 features"  # Internet search
uv run volume                         # Get current volume
uv run volume 50                      # Set volume to 50%
uv run history --query "weather"      # Search past conversations
```

### Adding Tools

Tools use a dual-mode pattern: Pydantic model defines both CLI args and OpenAI function schema.

```python
#!/usr/bin/env python3
"""tools/example.py - Example tool."""

from pydantic import BaseModel, Field

class MyTool(BaseModel):
    """Description shown to LLM and CLI help."""
    query: str = Field(description="Required param (positional in CLI)")
    count: int = Field(default=5, description="Optional param (--count in CLI)")

def my_tool(params: MyTool) -> str:
    return f"Result for {params.query}, count={params.count}"

def main() -> None:
    from tools.base import run
    run(MyTool, my_tool)

if __name__ == "__main__":
    main()
else:
    from tools.base import tool
    tool(MyTool)(my_tool)
```

Register in `tools/__init__.py`:

```python
from tools import example  # noqa: F401
```

Add CLI entry point in `pyproject.toml`:

```toml
[project.scripts]
example = "tools.example:main"
```

The Pydantic model is the single source of truth:
- `Field(description=...)` → CLI `--help` and OpenAI function schema
- Required fields → positional CLI arguments
- Fields with defaults → optional `--flag` arguments

## Testing

Live integration tests against real APIs:

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test class
uv run pytest tests/ -v -k TestWeather

# Run with coverage
uv run pytest tests/ -v --cov=tools
```

Tests cover:
- Weather API (multiple locations, error handling)
- News API (article retrieval)
- Search API (Perplexity integration)
- Device volume (get/set/boundaries)
- History lookup
- CLI invocation

## License

MIT
