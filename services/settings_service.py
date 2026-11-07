"""Validated, persistent application settings (stored in SQLite)."""
import math
import os
from dataclasses import asdict, dataclass, fields
from typing import Any, Dict, List, Mapping, Optional, Union

from config import SOUNDS_DIR
from database.database import Database, DatabaseError
from vision.drowsiness_detector import DetectionConfig

DEFAULT_SOUND = "alarm.wav"

LIMITS = {
    "ear_threshold": (0.05, 0.40),
    "mar_threshold": (0.20, 1.50),
    "eye_closure_duration": (0.5, 10.0),
    "camera_index": (0, 9),
}
LABELS = {
    "ear_threshold": "EAR threshold",
    "mar_threshold": "MAR threshold",
    "eye_closure_duration": "Eye-closure duration",
    "audio_enabled": "Audio alerts",
    "camera_index": "Camera",
    "alert_sound": "Alert sound",
}
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


@dataclass
class AppSettings:
    ear_threshold: float = 0.21
    mar_threshold: float = 0.60
    eye_closure_duration: float = 2.0   # seconds
    audio_enabled: bool = True
    camera_index: int = 0
    alert_sound: str = DEFAULT_SOUND


class SettingsValidationError(ValueError):
    """Carries one message per invalid field: {field_name: message}."""

    def __init__(self, errors: Dict[str, str]):
        self.errors = errors
        super().__init__("; ".join(f"{LABELS.get(k, k)}: {v}" for k, v in errors.items()))


def _parse_field(name: str, value: Any, available_sounds: Optional[List[str]] = None):
    if name in ("ear_threshold", "mar_threshold", "eye_closure_duration"):
        try:
            number = float(str(value).strip())
        except (TypeError, ValueError):
            raise ValueError("must be a number")
        if not math.isfinite(number):
            raise ValueError("must be a finite number")
        low, high = LIMITS[name]
        if not low <= number <= high:
            raise ValueError(f"must be between {low} and {high}")
        return number
    if name == "camera_index":
        try:
            number = int(str(value).strip())
        except (TypeError, ValueError):
            raise ValueError("must be a whole number")
        low, high = LIMITS[name]
        if not low <= number <= high:
            raise ValueError(f"must be between {low} and {high}")
        return number
    if name == "audio_enabled":
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        raise ValueError("must be on or off")
    if name == "alert_sound":
        text = str(value).strip()
        if not text or os.path.basename(text) != text or not text.lower().endswith(".wav"):
            raise ValueError("must be the name of a .wav file")
        if available_sounds is not None and text not in available_sounds:
            raise ValueError("sound file not found in assets/sounds")
        return text
    raise ValueError("unknown setting")


def parse_settings(raw: Mapping[str, Any], available_sounds: Optional[List[str]] = None,
                   base: Optional[AppSettings] = None) -> AppSettings:
    """Validate raw (possibly string) values. Raises SettingsValidationError
    listing every invalid field. Missing keys come from `base` or defaults."""
    base = base or AppSettings()
    result: Dict[str, Any] = {}
    errors: Dict[str, str] = {}
    for f in fields(AppSettings):
        value = raw[f.name] if f.name in raw else getattr(base, f.name)
        try:
            result[f.name] = _parse_field(f.name, value, available_sounds)
        except ValueError as exc:
            errors[f.name] = str(exc)
    if errors:
        raise SettingsValidationError(errors)
    return AppSettings(**result)


def to_detection_config(settings: AppSettings) -> DetectionConfig:
    return DetectionConfig(ear_threshold=settings.ear_threshold,
                           mar_threshold=settings.mar_threshold,
                           eye_closure_duration=settings.eye_closure_duration)


class SettingsService:
    def __init__(self, db: Database, sounds_dir: str = SOUNDS_DIR):
        self.db = db
        self.sounds_dir = sounds_dir

    def available_sounds(self) -> List[str]:
        try:
            return sorted(n for n in os.listdir(self.sounds_dir) if n.lower().endswith(".wav"))
        except OSError:
            return []

    def load(self) -> AppSettings:
        """Stored settings; any missing or corrupt value falls back to its default."""
        try:
            stored = self.db.get_settings()
        except DatabaseError:
            stored = {}
        defaults = AppSettings()
        values = {}
        for f in fields(AppSettings):
            try:
                values[f.name] = _parse_field(f.name, stored[f.name]) if f.name in stored \
                    else getattr(defaults, f.name)
            except ValueError:
                values[f.name] = getattr(defaults, f.name)
        return AppSettings(**values)

    def save(self, new: Union[AppSettings, Mapping[str, Any]]) -> AppSettings:
        raw = asdict(new) if isinstance(new, AppSettings) else dict(new)
        sounds = self.available_sounds() or None
        parsed = parse_settings(raw, sounds, base=self.load())
        serial = {k: ("1" if v is True else "0" if v is False else v)
                  for k, v in asdict(parsed).items()}
        self.db.set_settings(serial)
        return parsed

    def reset_defaults(self) -> AppSettings:
        defaults = AppSettings()
        serial = {k: ("1" if v is True else "0" if v is False else v)
                  for k, v in asdict(defaults).items()}
        self.db.set_settings(serial)
        return defaults
