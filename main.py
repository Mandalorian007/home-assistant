"""Home Assistant - Voice assistant with wake word detection."""

import os
import warnings
import logging
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")
logging.getLogger("root").setLevel(logging.ERROR)

from dotenv import load_dotenv
load_dotenv()

import webrtcvad
from openai import OpenAI

from audio import AudioStream, record_until_silence, audio_to_wav_buffer
from wake_word import WakeWordDetector, wait_for_wake_word
from transcribe import transcribe
# from tts import speak
# from assistant import process_message

# Configuration
WAKE_WORD = os.getenv("WAKE_WORD", "hey_jarvis")
# MODEL = os.getenv("MODEL", "gpt-4o")
# TTS_VOICE = os.getenv("TTS_VOICE", "alloy")
SILENCE_THRESHOLD = float(os.getenv("SILENCE_THRESHOLD", "0.5"))
DEBUG = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")


def log(msg: str) -> None:
    """Print log message with flush."""
    print(msg, flush=True)


def main() -> None:
    """Main entry point."""
    log("[LOG] Initializing OpenAI client...")
    client = OpenAI()

    log("[LOG] Loading wake word model...")
    detector = WakeWordDetector(model_name=WAKE_WORD)

    log("[LOG] Initializing VAD...")
    vad = webrtcvad.Vad(2)  # Aggressiveness 0-3

    log("[LOG] Starting audio stream...")
    log("")
    log("Home Assistant started.")
    log(f"Wake word: {WAKE_WORD}")
    log("")

    with AudioStream() as stream:
        log("[LOG] Audio stream active. Listening...")
        while True:
            # 1. Wait for wake word
            wait_for_wake_word(stream, detector, debug=DEBUG)
            log("[LOG] Wake word detected!")

            # 2. Record speech
            audio_bytes = record_until_silence(
                stream,
                vad,
                silence_duration=SILENCE_THRESHOLD,
            )
            log(f"[LOG] Silence detected. Recorded {len(audio_bytes)} bytes.")

            if len(audio_bytes) < 1000:
                log("[LOG] No speech detected (too short).")
                continue

            # 3. Transcribe
            log("[LOG] Transcribing...")
            wav_buffer = audio_to_wav_buffer(audio_bytes)
            text = transcribe(client, wav_buffer)
            log(f"[LOG] Transcription: {text}")

            if not text.strip():
                log("[LOG] Empty transcription.")
                continue

            # # 4. Process with LLM
            # response = process_message(client, text, model=MODEL)
            # print(f"Assistant: {response}")

            # # 5. Speak response
            # speak(client, response, voice=TTS_VOICE)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[LOG] Shutting down. Goodbye, sir.")
        exit(0)
