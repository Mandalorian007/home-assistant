"""Speech-to-text using OpenAI Whisper API."""

import io
from openai import OpenAI


def transcribe(client: OpenAI, audio_buffer: io.BytesIO) -> str:
    """Transcribe audio to text using Whisper.

    Args:
        client: OpenAI client instance
        audio_buffer: WAV audio in memory buffer

    Returns:
        Transcribed text
    """
    response = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_buffer,
    )
    return response.text
