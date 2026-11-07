"""Creates the built-in alert sounds with the standard library + NumPy, so the
project needs no external audio files. Run: python -m services.sound_generator"""
import os
import wave

import numpy as np

from config import SOUNDS_DIR

RATE = 44100


def _tone(freq: float, seconds: float, volume: float = 0.6) -> np.ndarray:
    t = np.arange(int(RATE * seconds)) / RATE
    samples = np.sin(2 * np.pi * freq * t)
    fade = max(1, min(int(0.01 * RATE), len(t) // 2))
    envelope = np.ones_like(t)
    envelope[:fade] = np.linspace(0, 1, fade)
    envelope[-fade:] = np.linspace(1, 0, fade)
    return volume * samples * envelope


def _silence(seconds: float) -> np.ndarray:
    return np.zeros(int(RATE * seconds))


def _alarm() -> np.ndarray:  # two-tone siren, about 1.5 s
    return np.concatenate([_tone(880, 0.25), _tone(660, 0.25)] * 3)


def _beep() -> np.ndarray:  # four short beeps, about 1.2 s
    return np.concatenate([_tone(1000, 0.2), _silence(0.1)] * 4)


SOUNDS = {"alarm.wav": _alarm, "beep.wav": _beep}


def _write_wav(path: str, samples: np.ndarray) -> None:
    data = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(data.tobytes())


def ensure_default_sounds(sounds_dir: str = SOUNDS_DIR) -> list:
    """Create any missing built-in sound; returns the file names present."""
    os.makedirs(sounds_dir, exist_ok=True)
    for name, make in SOUNDS.items():
        path = os.path.join(sounds_dir, name)
        if not os.path.isfile(path):
            _write_wav(path, make())
    return sorted(SOUNDS)


if __name__ == "__main__":
    print("Sounds ready:", ensure_default_sounds())
