"""Wake word detection using openWakeWord."""

from pathlib import Path

import numpy as np
from openwakeword.model import Model

from audio import AudioStream, SAMPLE_RATE

DEFAULT_THRESHOLD = 0.5
WAKEWORDS_DIR = Path(__file__).parent / "wakewords"


def _resolve_model(model_name: str) -> tuple[str, str]:
    """Resolve model name to path and inference framework.

    For custom models, checks wakewords/ directory for .onnx or .tflite files.
    Built-in models (hey_jarvis, alexa, etc.) are returned as-is.

    Returns:
        Tuple of (model_path, inference_framework)
    """
    # Check for custom model in wakewords directory (prefer tflite for efficiency)
    for ext, framework in [(".tflite", "tflite"), (".onnx", "onnx")]:
        custom_path = WAKEWORDS_DIR / f"{model_name}{ext}"
        if custom_path.exists():
            return str(custom_path), framework

    # Return as-is for built-in models (use default tflite framework)
    return model_name, "tflite"


class WakeWordDetector:
    """Detects wake words in audio stream."""

    def __init__(
        self,
        model_name: str = "hey_jarvis",
        threshold: float = DEFAULT_THRESHOLD,
    ):
        self.model_name = model_name
        self.threshold = threshold
        model_path, framework = _resolve_model(model_name)
        self.model = Model(
            wakeword_models=[model_path],
            inference_framework=framework,
        )

    def detect(self, audio: np.ndarray, debug: bool = False) -> bool:
        """Check if wake word is present in audio frame.

        Args:
            audio: Audio samples as numpy array (16-bit PCM, 16kHz)
            debug: Print scores for debugging

        Returns:
            True if wake word detected above threshold
        """
        # Pass raw int16 audio directly
        prediction = self.model.predict(audio.flatten())

        if debug:
            for name, score in prediction.items():
                if score > 0.1:
                    print(f"  >> {name}: {score:.2f}", flush=True)

        for name, score in prediction.items():
            if score >= self.threshold:
                return True

        return False

    def reset(self) -> None:
        """Reset model state between activations."""
        self.model.reset()


def wait_for_wake_word(
    stream: AudioStream,
    detector: WakeWordDetector,
    debug: bool = False,
) -> None:
    """Block until wake word is detected.

    Args:
        stream: Active audio stream
        detector: Wake word detector instance
        debug: Print detection scores
    """

    # Accumulate audio into larger chunks for wake word detection
    # openWakeWord expects ~80ms chunks (1280 samples at 16kHz)
    chunk_size = 1280
    audio_buffer = np.array([], dtype=np.int16)
    frame_count = 0

    while True:
        audio = stream.read(timeout=1.0)
        if audio is None:
            if debug:
                print("[DEBUG] No audio received", flush=True)
            continue

        audio_buffer = np.concatenate([audio_buffer, audio.flatten()])

        # Process when we have enough samples
        while len(audio_buffer) >= chunk_size:
            chunk = audio_buffer[:chunk_size]
            audio_buffer = audio_buffer[chunk_size:]

            frame_count += 1
            if debug and frame_count % 20 == 0:
                level = np.abs(chunk).mean()
                print(f"[DEBUG] Audio level: {level:.0f} (chunk {frame_count})", flush=True)

            if detector.detect(chunk, debug=debug):
                detector.reset()
                return
