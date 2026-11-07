"""Time-based drowsiness state machine (no camera or UI dependencies)."""
import time
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional

NORMAL = "NORMAL"
EYES_CLOSED = "EYES CLOSED"
YAWNING = "YAWNING"
DROWSY = "DROWSINESS ALERT"
NO_FACE = "FACE NOT DETECTED"
CAMERA_UNAVAILABLE = "CAMERA UNAVAILABLE"


@dataclass
class DetectionConfig:
    ear_threshold: float = 0.21
    mar_threshold: float = 0.60
    eye_closure_duration: float = 2.0   # seconds before a drowsiness alert
    yawn_min_duration: float = 1.0      # MAR must stay high this long
    alert_cooldown: float = 5.0         # min seconds between alert events
    yawn_cooldown: float = 3.0
    smoothing_window: int = 3
    face_lost_grace: float = 0.5        # tolerate brief detection drops


@dataclass
class DetectionEvent:
    event_type: str            # "DROWSINESS_ALERT" or "YAWNING"
    timestamp: float
    ear: float
    mar: float
    closure_duration: float = 0.0


@dataclass
class DetectionState:
    status: str = NORMAL
    eyes_closed: bool = False
    closure_duration: float = 0.0
    smoothed_ear: float = 0.0
    smoothed_mar: float = 0.0
    events: List[DetectionEvent] = field(default_factory=list)


class DrowsinessDetector:
    def __init__(self, config: Optional[DetectionConfig] = None):
        self.config = config or DetectionConfig()
        self.reset()

    def reset(self):
        n = max(1, self.config.smoothing_window)
        self._ears = deque(maxlen=n)
        self._mars = deque(maxlen=n)
        self._closed_since = None
        self._mouth_open_since = None
        self._yawn_counted = False
        self._last_alert = -1e9
        self._last_yawn = -1e9
        self._last_face = None

    def update(self, ear: Optional[float], mar: Optional[float],
               now: Optional[float] = None) -> DetectionState:
        """Feed one measurement (None, None when no face/landmarks)."""
        cfg = self.config
        now = time.monotonic() if now is None else now
        state = DetectionState()

        if ear is None or mar is None:
            if self._last_face is not None and now - self._last_face <= cfg.face_lost_grace:
                state.status = NORMAL  # brief drop: keep timers, don't flicker
                return state
            self._closed_since = None
            self._mouth_open_since = None
            self._yawn_counted = False
            self._ears.clear()
            self._mars.clear()
            state.status = NO_FACE
            return state

        self._last_face = now
        self._ears.append(ear)
        self._mars.append(mar)
        s_ear = sum(self._ears) / len(self._ears)
        s_mar = sum(self._mars) / len(self._mars)
        state.smoothed_ear, state.smoothed_mar = s_ear, s_mar

        # Eye closure (duration based, independent of frame rate)
        if s_ear < cfg.ear_threshold:
            if self._closed_since is None:
                self._closed_since = now
            state.eyes_closed = True
            state.closure_duration = now - self._closed_since
        else:
            self._closed_since = None

        # Yawning: sustained wide mouth, counted once per continuous episode
        if s_mar > cfg.mar_threshold:
            if self._mouth_open_since is None:
                self._mouth_open_since = now
            if (not self._yawn_counted
                    and now - self._mouth_open_since >= cfg.yawn_min_duration
                    and now - self._last_yawn >= cfg.yawn_cooldown):
                self._yawn_counted = True
                self._last_yawn = now
                state.events.append(DetectionEvent("YAWNING", now, s_ear, s_mar))
            yawning = self._yawn_counted
        else:
            self._mouth_open_since = None
            self._yawn_counted = False
            yawning = False

        if state.eyes_closed and state.closure_duration >= cfg.eye_closure_duration:
            state.status = DROWSY
            if now - self._last_alert >= cfg.alert_cooldown:
                self._last_alert = now
                state.events.append(DetectionEvent(
                    "DROWSINESS_ALERT", now, s_ear, s_mar, state.closure_duration))
        elif state.eyes_closed:
            state.status = EYES_CLOSED
        elif yawning:
            state.status = YAWNING  # secondary indicator only
        else:
            state.status = NORMAL
        return state
