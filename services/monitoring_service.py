"""Runs the webcam -> vision -> detector -> database/alert loop on a background
thread. The UI never touches the camera: it calls start()/stop() and polls
snapshot() (e.g. every 30 ms with Tk's after()), so it cannot freeze."""
import threading
import time
from dataclasses import dataclass, replace
from typing import Any, Callable, Optional

import cv2

from database.database import Database, DatabaseError
from services.alert_service import AlertService
from services.camera_service import CameraService, CameraUnavailableError
from services.settings_service import AppSettings, to_detection_config
from vision.drowsiness_detector import (CAMERA_UNAVAILABLE, DROWSY, EYES_CLOSED, NORMAL,
                                        YAWNING, DrowsinessDetector)
from vision.frame_processor import FrameProcessor, FrameResult
from vision.landmark_detector import LandmarkModelError

# Lifecycle states of the service
IDLE, STARTING, RUNNING, STOPPING, ERROR = "IDLE", "STARTING", "RUNNING", "STOPPING", "ERROR"
STATUS_IDLE = "NOT MONITORING"
STATUS_ERROR = "MONITORING ERROR"

# BGR colours for the on-frame overlay (palette: accent #8EDBD0, alert #D96C6C)
_BGR = {NORMAL: (208, 219, 142), EYES_CLOSED: (80, 190, 240), YAWNING: (80, 190, 240),
        DROWSY: (108, 108, 217)}


@dataclass
class MonitoringSnapshot:
    state: str = IDLE
    status: str = STATUS_IDLE
    frame: Optional[Any] = None          # annotated BGR frame (numpy array)
    ear: Optional[float] = None
    mar: Optional[float] = None
    eyes_closed: bool = False
    closure_duration: float = 0.0
    camera_ok: bool = False
    fps: float = 0.0
    session_id: Optional[int] = None
    elapsed: float = 0.0
    drowsiness_alerts: int = 0
    yawning_events: int = 0
    audio_status: str = ""
    error_message: str = ""
    warning: str = ""


class MonitoringService:
    def __init__(self, db: Database, alerts: AlertService,
                 processor_factory: Callable[[], Any] = FrameProcessor,
                 camera_factory: Callable[[int], Any] = CameraService,
                 ear_sample_interval: float = 0.5, max_read_failures: int = 30):
        self.db = db
        self.alerts = alerts
        self._processor_factory = processor_factory
        self._camera_factory = camera_factory
        self._sample_interval = ear_sample_interval
        self._max_read_failures = max_read_failures
        self._processor = None  # loaded once (the dlib model is slow to load)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._snap = MonitoringSnapshot()

    # ----------------------------------------------------------- public API
    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def snapshot(self) -> MonitoringSnapshot:
        with self._lock:
            return replace(self._snap)

    def start(self, settings: AppSettings) -> bool:
        """Begin monitoring on a worker thread. Returns False if already running.
        Camera/model problems are reported through snapshot().error_message."""
        with self._lock:
            if self.is_running:
                return False
            self._stop.clear()
            self._snap = MonitoringSnapshot(state=STARTING, status="STARTING...",
                                            audio_status=self.alerts.status_text())
            self._thread = threading.Thread(target=self._run, args=(settings,),
                                            name="vigilens-monitor", daemon=True)
            self._thread.start()
        return True

    def stop(self, timeout: float = 8.0) -> bool:
        """Stop monitoring, release the camera and save the session.
        Returns True once the worker has finished."""
        thread = self._thread
        if thread is None or not thread.is_alive():
            return True
        self._publish(state=STOPPING)
        self._stop.set()
        thread.join(timeout)
        return not thread.is_alive()

    def shutdown(self) -> None:
        self.stop()
        self.alerts.shutdown()

    # ------------------------------------------------------------ internals
    def _publish(self, **fields) -> None:
        with self._lock:
            for key, value in fields.items():
                setattr(self._snap, key, value)

    def _get_processor(self):
        if self._processor is None:
            self._processor = self._processor_factory()
        return self._processor

    def _flush_samples(self, session_id: int, samples: list) -> None:
        if samples:
            self.db.add_ear_samples(session_id, samples)
            samples.clear()

    @staticmethod
    def _annotate(frame, status: str, ear, mar, closure: float) -> None:
        color = _BGR.get(status, (200, 200, 200))
        h, w = frame.shape[:2]
        if status == DROWSY:
            cv2.rectangle(frame, (0, 0), (w - 1, h - 1), color, 8)
        cv2.putText(frame, status, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)
        if ear is not None and mar is not None:
            cv2.putText(frame, f"EAR {ear:.2f}  MAR {mar:.2f}", (12, h - 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        if closure > 0:
            cv2.putText(frame, f"Eyes closed {closure:.1f}s", (12, 58),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)

    def _run(self, settings: AppSettings) -> None:
        camera = None
        session_id: Optional[int] = None
        start = time.monotonic()
        samples: list = []
        alerts = yawns = 0
        error = ""
        error_status = STATUS_ERROR
        try:
            processor = self._get_processor()
            camera = self._camera_factory(settings.camera_index)
            camera.open()
            if self._stop.is_set():
                return
            self.alerts.configure(settings.audio_enabled, settings.alert_sound)
            detector = DrowsinessDetector(to_detection_config(settings))
            session_id = self.db.create_session()
            start = time.monotonic()
            self._publish(state=RUNNING, status=NORMAL, session_id=session_id, camera_ok=True,
                          audio_status=self.alerts.status_text())

            failures = process_errors = frames = 0
            next_sample = 0.0
            fps_start = start
            fps = 0.0
            warning = ""
            while not self._stop.is_set():
                ok, frame = camera.read()
                if not ok or frame is None:
                    failures += 1
                    if failures >= self._max_read_failures:
                        raise CameraUnavailableError(
                            "The camera stopped delivering frames. It may have been "
                            "unplugged or taken over by another program.")
                    self._stop.wait(0.03)
                    continue
                failures = 0
                frame = cv2.flip(frame, 1)  # mirror view feels natural to the user
                try:
                    result = processor.process(frame)
                    process_errors = 0
                except Exception as exc:  # one bad frame must not end the session
                    process_errors += 1
                    if process_errors >= 30:
                        raise RuntimeError(f"Frame processing keeps failing: {exc}") from exc
                    result = FrameResult(frame=frame)

                now = time.monotonic()
                if result.face_found:
                    state = detector.update(result.ear, result.mar, now)
                else:
                    state = detector.update(None, None, now)

                for event in state.events:
                    if event.event_type == "DROWSINESS_ALERT":
                        alerts += 1
                        self.alerts.trigger()  # before the DB write: sound must not wait on disk
                    else:
                        yawns += 1
                    try:
                        self.db.add_event(session_id, event.event_type, event.ear,
                                          event.mar, event.closure_duration)
                    except DatabaseError as exc:
                        warning = f"An event could not be saved: {exc}"

                elapsed = now - start
                if result.face_found and elapsed >= next_sample:
                    samples.append((round(elapsed, 2), float(state.smoothed_ear)))
                    next_sample = elapsed + self._sample_interval
                    if len(samples) >= 40:
                        try:
                            self._flush_samples(session_id, samples)
                        except DatabaseError as exc:
                            warning = f"EAR samples could not be saved: {exc}"

                frames += 1
                if now - fps_start >= 1.0:
                    fps, frames, fps_start = frames / (now - fps_start), 0, now

                ear = state.smoothed_ear if result.face_found else None
                mar = state.smoothed_mar if result.face_found else None
                self._annotate(result.frame, state.status, ear, mar, state.closure_duration)
                self._publish(frame=result.frame, status=state.status, ear=ear, mar=mar,
                              eyes_closed=state.eyes_closed, closure_duration=state.closure_duration,
                              camera_ok=True, fps=fps, elapsed=elapsed, drowsiness_alerts=alerts,
                              yawning_events=yawns, audio_status=self.alerts.status_text(),
                              warning=warning)
        except CameraUnavailableError as exc:
            error, error_status = str(exc), CAMERA_UNAVAILABLE
        except (LandmarkModelError, FileNotFoundError) as exc:
            error = str(exc)
        except DatabaseError as exc:
            error = f"Database error: {exc}"
        except Exception as exc:  # last resort: report, never crash silently
            error = f"Unexpected error: {exc!r}"
        finally:
            if camera is not None:
                try:
                    camera.release()
                except Exception:
                    pass
            if session_id is not None:  # always save the session, even after errors
                try:
                    self._flush_samples(session_id, samples)
                    self.db.end_session(session_id, duration=time.monotonic() - start)
                except DatabaseError as exc:
                    error = (error + " | " if error else "") + f"Session could not be fully saved: {exc}"
            self.alerts.stop()
            self._publish(frame=None, camera_ok=False, eyes_closed=False, closure_duration=0.0,
                          ear=None, mar=None, error_message=error,
                          state=ERROR if error else IDLE,
                          status=error_status if error else STATUS_IDLE)
