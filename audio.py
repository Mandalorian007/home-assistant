"""Audio capture and playback utilities."""

import io
import queue
import numpy as np
import sounddevice as sd
import webrtcvad

SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_DURATION_MS = 30
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)


class AudioStream:
    """Continuous audio stream for wake word detection."""

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.queue: queue.Queue[np.ndarray] = queue.Queue()
        self.stream: sd.InputStream | None = None

    def _callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            print(f"Audio stream status: {status}")
        self.queue.put(indata.copy())

    def start(self) -> None:
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=CHANNELS,
            dtype=np.int16,
            blocksize=FRAME_SIZE,
            callback=self._callback,
        )
        self.stream.start()

    def stop(self) -> None:
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def read(self, timeout: float = 1.0) -> np.ndarray | None:
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def __enter__(self) -> "AudioStream":
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()


def record_until_silence(
    stream: AudioStream,
    vad: webrtcvad.Vad,
    silence_duration: float = 0.5,
    max_duration: float = 30.0,
) -> bytes:
    """Record audio until silence is detected.

    Args:
        stream: Active audio stream
        vad: Voice activity detector
        silence_duration: Seconds of silence to stop recording
        max_duration: Maximum recording duration in seconds

    Returns:
        Raw audio bytes (16-bit PCM, 16kHz mono)
    """
    frames: list[bytes] = []
    silent_frames = 0
    max_silent_frames = int(silence_duration * 1000 / FRAME_DURATION_MS)
    max_frames = int(max_duration * 1000 / FRAME_DURATION_MS)

    print("Listening...")

    for _ in range(max_frames):
        audio = stream.read(timeout=1.0)
        if audio is None:
            continue

        frame_bytes = audio.flatten().tobytes()
        frames.append(frame_bytes)

        is_speech = vad.is_speech(frame_bytes, SAMPLE_RATE)

        if is_speech:
            silent_frames = 0
        else:
            silent_frames += 1

        if silent_frames >= max_silent_frames and len(frames) > max_silent_frames:
            break

    print("Done listening.")
    return b"".join(frames)


def audio_to_wav_buffer(audio_bytes: bytes, sample_rate: int = SAMPLE_RATE) -> io.BytesIO:
    """Convert raw audio bytes to WAV format in memory."""
    import wave

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate)
        wav.writeframes(audio_bytes)
    buffer.seek(0)
    buffer.name = "audio.wav"
    return buffer


def play_audio(audio_data: bytes, sample_rate: int = 24000) -> None:
    """Play audio bytes through speakers.

    Args:
        audio_data: Raw audio bytes (expected PCM format from OpenAI TTS)
        sample_rate: Sample rate of audio (OpenAI TTS uses 24kHz)
    """
    audio_array = np.frombuffer(audio_data, dtype=np.int16)
    sd.play(audio_array, samplerate=sample_rate)
    sd.wait()
