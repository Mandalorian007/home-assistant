"""Home Assistant - Voice assistant with wake word detection."""

import argparse
import os
import threading
import time
import warnings
import logging
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")
logging.getLogger("root").setLevel(logging.ERROR)

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

from assistant import process_message
from history_store import save_conversation
from tools.timer import get_expired_timers

# Configuration
MODEL = os.getenv("MODEL", "gpt-4o")
DEBUG = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")


def process_and_print(client: OpenAI, text: str) -> None:
    """Process a message and print the response."""
    result = process_message(client, text, model=MODEL)
    print(f"Assistant: {result.final_response}")
    save_conversation(result.user_input, result.final_response, result.tool_calls)


def run_text(client: OpenAI, text: str) -> None:
    """One-shot text mode."""
    print(f"You: {text}")
    process_and_print(client, text)


def run_repl(client: OpenAI) -> None:
    """Interactive text REPL."""
    print("Home Assistant (text mode). Type 'quit' to exit.\n")
    while True:
        try:
            text = input("You: ").strip()
        except EOFError:
            break
        if not text or text.lower() in ("quit", "exit"):
            break
        process_and_print(client, text)
        print()


def start_timer_daemon(
    client: OpenAI,
    tts_voice: str,
    stop_event: threading.Event,
    audio_lock: threading.Lock,
) -> None:
    """Background thread that announces expired timers."""
    from tts import speak

    while not stop_event.is_set():
        try:
            expired = get_expired_timers()
            for timer in expired:
                label = timer.get("label")
                if label:
                    message = f"Your {label} timer is done."
                else:
                    message = "Your timer is done."
                print(f"[Timer] {message}")
                if audio_lock.locked():
                    print("[Timer] Waiting for audio...")
                with audio_lock:
                    speak(client, message, voice=tts_voice)
        except Exception as e:
            if DEBUG:
                print(f"[Timer error] {e}")
        stop_event.wait(1)  # Check every second


def run_voice(client: OpenAI) -> None:
    """Voice mode with wake word detection."""
    import webrtcvad
    from audio import AudioStream, record_until_silence, audio_to_wav_buffer
    from wake_word import WakeWordDetector, wait_for_wake_word
    from transcribe import transcribe
    from tts import speak

    wake_word = os.getenv("WAKE_WORD", "hey_jarvis")
    tts_voice = os.getenv("TTS_VOICE", "alloy")
    silence_threshold = float(os.getenv("SILENCE_THRESHOLD", "0.5"))

    detector = WakeWordDetector(model_name=wake_word)
    vad = webrtcvad.Vad(2)

    # Start timer daemon with shared audio lock
    stop_event = threading.Event()
    audio_lock = threading.Lock()
    timer_thread = threading.Thread(
        target=start_timer_daemon,
        args=(client, tts_voice, stop_event, audio_lock),
        daemon=True
    )
    timer_thread.start()

    print("Starting Home Assistant...")
    print(f"Listening for '{wake_word.replace('_', ' ')}'...\n")

    try:
        with AudioStream() as stream:
            while True:
                wait_for_wake_word(stream, detector, debug=DEBUG)
                print("[Activated]")

                audio_bytes = record_until_silence(stream, vad, silence_duration=silence_threshold)
                if len(audio_bytes) < 1000:
                    print("(No speech detected)\n")
                    continue

                text = transcribe(client, audio_to_wav_buffer(audio_bytes))
                if not text.strip():
                    print("(Empty transcription)\n")
                    continue

                print(f"You: {text}")
                result = process_message(client, text, model=MODEL)
                print(f"Assistant: {result.final_response}\n")
                save_conversation(result.user_input, result.final_response, result.tool_calls)
                with audio_lock:
                    speak(client, result.final_response, voice=tts_voice)
    finally:
        stop_event.set()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Home Assistant")
    parser.add_argument("text", nargs="?", help="Text to process (one-shot mode)")
    parser.add_argument("--repl", action="store_true", help="Interactive text mode")
    args = parser.parse_args()

    client = OpenAI()

    if args.text:
        run_text(client, args.text)
    elif args.repl:
        run_repl(client)
    else:
        run_voice(client)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nGoodbye.")
        exit(0)
