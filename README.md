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

# Configure API key
echo "OPENAI_API_KEY=sk-..." > .env

# Download wake word models
uv run python -c "from openwakeword import utils; utils.download_models()"

# Run
uv run main.py
```

Say "Hey Jarvis" to activate, then speak your command.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *required* | OpenAI API key |
| `WAKE_WORD` | `hey_jarvis` | Wake word (`alexa`, `hey_mycroft`, `hey_jarvis`, `hey_rhasspy`) |
| `SILENCE_THRESHOLD` | `0.5` | Seconds of silence to end recording |
| `MODEL` | `gpt-4o` | OpenAI chat model |
| `TTS_VOICE` | `alloy` | TTS voice (`alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`) |

## Adding Tools

Tools use Pydantic models with the `@tool` decorator:

```python
# tools/example.py
from pydantic import BaseModel, Field
from tools.base import tool

class MyTool(BaseModel):
    """Description shown to the LLM."""
    param: str = Field(description="Parameter description")

@tool(MyTool)
def my_tool(params: MyTool) -> str:
    return f"Result for {params.param}"
```

Register in `tools/__init__.py`:

```python
from tools import example  # noqa: F401
```

## License

MIT
