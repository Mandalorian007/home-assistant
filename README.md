# Home Assistant

A minimal voice assistant using wake word detection, speech-to-text, and LLM-powered responses with extensible tools.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Audio Input                              │
│                     (Microphone Stream)                         │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     openWakeWord                                │
│              (Listens for "Hey Jarvis" etc.)                    │
│                                                                 │
│  - Runs continuously on audio stream                            │
│  - Low resource usage until wake word detected                  │
│  - Triggers recording on activation                             │
└─────────────────────────┬───────────────────────────────────────┘
                          │ Wake word detected
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Audio Capture                                 │
│             (Record until silence/timeout)                      │
│                                                                 │
│  - Captures user speech after wake word                         │
│  - Voice activity detection for end-of-speech                   │
│  - Outputs audio buffer                                         │
└─────────────────────────┬───────────────────────────────────────┘
                          │ Audio buffer
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   OpenAI Whisper                                │
│                (Speech-to-Text via API)                         │
│                                                                 │
│  - Transcribes audio to text                                    │
│  - Uses openai.audio.transcriptions.create()                    │
└─────────────────────────┬───────────────────────────────────────┘
                          │ Transcribed text
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   OpenAI Chat Completion                        │
│                 (LLM with Tool Support)                         │
│                                                                 │
│  - Single conversation loop                                     │
│  - Tools defined as functions                                   │
│  - Executes tool calls and returns results                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │ Response (text or tool call)
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Response Handler                            │
│                                                                 │
│  - Text response → TTS output (speaker)                         │
│  - Tool call → Execute and loop back to LLM                     │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      OpenAI TTS                                 │
│                  (Text-to-Speech API)                           │
│                                                                 │
│  - Converts response text to audio                              │
│  - Uses openai.audio.speech.create()                            │
│  - Plays through speaker                                        │
└─────────────────────────────────────────────────────────────────┘
```

## Components

| Component | Library | Purpose |
|-----------|---------|---------|
| Wake Word | [openWakeWord](https://github.com/dscripka/openWakeWord) | Detects activation phrase |
| Speech-to-Text | OpenAI Whisper API | Transcribes speech |
| LLM | OpenAI Chat API | Processes commands with tools |
| Text-to-Speech | OpenAI TTS API | Speaks responses |
| Audio I/O | pyaudio / sounddevice | Microphone capture and playback |

## Main Loop

```python
# Pseudocode
while True:
    # 1. Listen for wake word
    audio_stream = get_audio_stream()
    if wake_word_detected(audio_stream):

        # 2. Capture speech
        audio = record_until_silence()

        # 3. Transcribe
        text = openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio
        )

        # 4. Process with LLM (tool loop)
        messages = [{"role": "user", "content": text}]
        while True:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=TOOLS
            )

            if response.has_tool_calls:
                results = execute_tools(response.tool_calls)
                messages.extend(results)
            else:
                # 5. Speak response
                audio = openai.audio.speech.create(
                    model="tts-1",
                    voice="alloy",
                    input=response.content
                )
                play_audio(audio)
                break
```

## Tools

Tools are defined using Pydantic models with the `@tool` decorator. The model's docstring becomes the tool description, and `Field()` descriptions document parameters.

### Defining a Tool

Create a new file in `tools/`:

```python
# tools/weather.py
from pydantic import BaseModel, Field
from tools.base import tool


class GetWeather(BaseModel):
    """Get the current weather for a location."""

    location: str = Field(description="City and country e.g. Paris, France")


@tool(GetWeather)
def get_weather(params: GetWeather) -> str:
    # Your implementation here
    return f"The weather in {params.location} is sunny and 72°F."
```

### Registering the Tool

Import your tool module in `tools/__init__.py`:

```python
from tools import weather  # noqa: F401
from tools import time     # noqa: F401
from tools import my_tool  # Add your new tool here
```

### How It Works

1. `@tool(Model)` registers the Pydantic model with OpenAI's `pydantic_function_tool()`
2. The LLM sees the tool name, description, and parameter schema
3. When called, arguments are validated through Pydantic
4. Your handler receives a typed `params` object

## Setup

### 1. Install Dependencies

```bash
uv sync
```

### 2. Configure Environment

Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=sk-...
```

### 3. Download Wake Word Models

```bash
uv run python -c "from openwakeword import utils; utils.download_models()"
```

This downloads models for: `alexa`, `hey_mycroft`, `hey_jarvis`, `hey_rhasspy`, `timer`, `weather`.

### 4. Run

```bash
uv run main.py
```

Say "Hey Jarvis" to activate, then speak your command.

## Configuration

Optional environment variables (set in `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *required* | OpenAI API key |
| `WAKE_WORD` | `hey_jarvis` | Wake word model (`alexa`, `hey_mycroft`, `hey_jarvis`, `hey_rhasspy`) |
| `SILENCE_THRESHOLD` | `0.5` | Seconds of silence to end recording |
| `MODEL` | `gpt-4o` | OpenAI model for chat |
| `TTS_VOICE` | `alloy` | TTS voice (`alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`) |

## File Structure

```
home-assistant/
├── main.py              # Entry point and main loop
├── audio.py             # Audio capture and playback
├── wake_word.py         # openWakeWord integration
├── transcribe.py        # Whisper API wrapper
├── tts.py               # TTS API wrapper and playback
├── assistant.py         # Chat completion with tools
├── tools/               # Tool implementations
│   ├── __init__.py      # Tool registry
│   ├── base.py          # @tool decorator
│   ├── weather.py
│   └── time.py
└── pyproject.toml
```

## License

MIT
