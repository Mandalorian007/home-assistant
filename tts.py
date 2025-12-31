"""Text-to-speech using OpenAI TTS API."""

from openai import OpenAI

from audio import play_audio

DEFAULT_VOICE = "alloy"
VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]


def speak(client: OpenAI, text: str, voice: str = DEFAULT_VOICE) -> None:
    """Convert text to speech and play through speakers.

    Args:
        client: OpenAI client instance
        text: Text to speak
        voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
    """
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
        response_format="pcm",
    )

    play_audio(response.content)
