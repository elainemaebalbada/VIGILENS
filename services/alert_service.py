"""Audio alerts. Playback is non-blocking (pygame mixer plays on its own audio
thread), so it can never freeze the UI or the monitoring loop."""
import os
import threading
import time

from config import SOUNDS_DIR
from services.settings_service import DEFAULT_SOUND
from services.sound_generator import ensure_default_sounds

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


class PygameBackend:
    """Thin wrapper so the AlertService can be tested with a fake backend."""

    def __init__(self):
        self._pygame = None
        self._channel = None
        self._cache = {}

    def initialize(self) -> None:
        import pygame  # imported lazily: a missing install must not crash startup
        pygame.mixer.init()
        self._pygame = pygame

    def play(self, path: str) -> None:
        sound = self._cache.get(path)
        if sound is None:
            sound = self._pygame.mixer.Sound(path)
            self._cache[path] = sound
        self._channel = sound.play()

    def is_busy(self) -> bool:
        return self._channel is not None and bool(self._channel.get_busy())

    def stop(self) -> None:
        if self._pygame is not None:
            self._pygame.mixer.stop()

    def shutdown(self) -> None:
        if self._pygame is not None:
            self._pygame.mixer.quit()
            self._pygame = None


class AlertService:
    def __init__(self, sounds_dir: str = SOUNDS_DIR, backend=None,
                 min_interval: float = 3.0, clock=time.monotonic):
        self.sounds_dir = sounds_dir
        self._backend = backend or PygameBackend()
        self._min_interval = min_interval
        self._clock = clock
        self._lock = threading.Lock()
        self._backend_ready = False
        self._available = True
        self._message = ""
        self._last_played = None
        self.enabled = True
        self.sound_name = DEFAULT_SOUND
        self.play_count = 0

    # -------------------------------------------------------------- config
    def configure(self, enabled: bool, sound_name: str) -> None:
        with self._lock:
            self.enabled = bool(enabled)
            self.sound_name = sound_name or DEFAULT_SOUND

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self.enabled = bool(enabled)

    # ------------------------------------------------------------ internals
    def _ensure_backend(self) -> bool:
        if self._backend_ready:
            return True
        if not self._available:
            return False
        try:
            self._backend.initialize()
            self._backend_ready = True
        except Exception as exc:  # ImportError, pygame.error (no audio device), ...
            self._available = False
            self._message = f"Audio unavailable: {exc}"
        return self._backend_ready

    def _resolve_sound(self):
        try:
            ensure_default_sounds(self.sounds_dir)
        except OSError:
            pass
        for name in (self.sound_name, DEFAULT_SOUND):
            path = os.path.join(self.sounds_dir, name)
            if os.path.isfile(path):
                return path
        return None

    # ----------------------------------------------------------------- API
    def trigger(self) -> bool:
        """Play the alert once. Returns True only if a sound actually started.
        Skipped when disabled, unavailable, still playing, or too soon after
        the previous alert (prevents overlap and rapid restarts)."""
        with self._lock:
            if not self.enabled or not self._ensure_backend():
                return False
            now = self._clock()
            if self._last_played is not None and now - self._last_played < self._min_interval:
                return False
            try:
                if self._backend.is_busy():
                    return False
                path = self._resolve_sound()
                if path is None:
                    self._message = "Alert sound file not found."
                    return False
                self._backend.play(path)
            except Exception as exc:
                self._available = False
                self._message = f"Audio unavailable: {exc}"
                return False
            self._last_played = now
            self.play_count += 1
            return True

    def status_text(self) -> str:
        if not self._available:
            return self._message or "Audio unavailable"
        return "Audio alerts: ON" if self.enabled else "Audio alerts: OFF"

    def stop(self) -> None:
        with self._lock:
            if self._backend_ready:
                try:
                    self._backend.stop()
                except Exception:
                    pass
            self._last_played = None

    def shutdown(self) -> None:
        self.stop()
        with self._lock:
            if self._backend_ready:
                try:
                    self._backend.shutdown()
                except Exception:
                    pass
                self._backend_ready = False
