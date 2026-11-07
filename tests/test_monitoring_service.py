"""Exercises the real MonitoringService thread, DrowsinessDetector and SQLite
with a fake camera and fake face processor (no webcam, dlib or model needed)."""
import time

import numpy as np
import pytest

from database.database import Database
from services.alert_service import AlertService
from services.camera_service import CameraUnavailableError
from services.monitoring_service import ERROR, IDLE, RUNNING, MonitoringService
from services.settings_service import AppSettings
from vision.drowsiness_detector import CAMERA_UNAVAILABLE
from vision.frame_processor import FrameResult
from vision.landmark_detector import LandmarkModelError


class FakeAudio:
    def __init__(self):
        self.plays = []

    def initialize(self): pass
    def play(self, path): self.plays.append(path)
    def is_busy(self): return False
    def stop(self): pass
    def shutdown(self): pass


class FakeCamera:
    def __init__(self, index=0, frames_before_failure=None, fail_open=False):
        self.index, self.fail_open = index, fail_open
        self.limit, self.count, self.released = frames_before_failure, 0, False

    def open(self):
        if self.fail_open:
            raise CameraUnavailableError("Camera 0 could not be opened.")

    def read(self):
        time.sleep(0.01)
        self.count += 1
        if self.limit is not None and self.count > self.limit:
            return False, None
        return True, np.zeros((480, 640, 3), dtype=np.uint8)

    def release(self):
        self.released = True


class FakeProcessor:
    def __init__(self, ear=0.10, mar=0.20, face=True):
        self.ear, self.mar, self.face = ear, mar, face

    def process(self, frame):
        return FrameResult(frame=frame, face_found=self.face,
                           ear=self.ear if self.face else None,
                           mar=self.mar if self.face else None)


def build(tmp_path, camera=None, processor=None, processor_factory=None, **kw):
    db = Database(str(tmp_path / "m.db"))
    audio = FakeAudio()
    alerts = AlertService(sounds_dir=str(tmp_path / "snd"), backend=audio)
    cam = camera or FakeCamera()
    svc = MonitoringService(db, alerts, processor_factory=processor_factory or (lambda: processor or FakeProcessor()),
                            camera_factory=lambda index: cam, ear_sample_interval=0.1, **kw)
    return db, audio, cam, svc


def wait_for(predicate, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.02)
    return False


FAST = AppSettings(eye_closure_duration=0.3)


def test_prolonged_closure_saves_session_event_samples_and_plays_sound_once(tmp_path):
    db, audio, cam, svc = build(tmp_path)
    assert svc.start(FAST) is True
    assert wait_for(lambda: svc.snapshot().drowsiness_alerts >= 1)
    snap = svc.snapshot()
    assert snap.state == RUNNING and snap.eyes_closed and snap.frame is not None
    assert svc.stop() is True
    final = svc.snapshot()
    assert final.state == IDLE and final.frame is None and cam.released
    rows = db.get_sessions()
    assert len(rows) == 1 and rows[0]["end_time"] is not None and rows[0]["duration"] > 0
    assert rows[0]["total_drowsiness_alerts"] == 1
    events = db.get_events(rows[0]["session_id"])
    assert events[0]["event_type"] == "DROWSINESS_ALERT"
    assert events[0]["eye_closure_duration"] >= 0.3
    assert len(db.get_ear_samples(rows[0]["session_id"])) >= 2
    assert len(audio.plays) == 1  # cooldown prevents repeated alerts
    db.close()


def test_audio_disabled_still_records_alert_without_sound(tmp_path):
    db, audio, _, svc = build(tmp_path)
    svc.start(AppSettings(eye_closure_duration=0.3, audio_enabled=False))
    assert wait_for(lambda: svc.snapshot().drowsiness_alerts >= 1)
    svc.stop()
    assert audio.plays == []
    assert db.get_sessions()[0]["total_drowsiness_alerts"] == 1
    db.close()


def test_open_eyes_closed_mouth_records_no_events(tmp_path):
    db, audio, _, svc = build(tmp_path, processor=FakeProcessor(ear=0.30, mar=0.20))
    svc.start(FAST)
    time.sleep(0.8)
    svc.stop()
    row = db.get_sessions()[0]
    assert row["total_drowsiness_alerts"] == 0 and row["total_yawning_events"] == 0
    assert audio.plays == []
    db.close()


def test_yawn_is_recorded_separately_and_makes_no_sound(tmp_path):
    db, audio, _, svc = build(tmp_path, processor=FakeProcessor(ear=0.30, mar=0.90))
    svc.start(FAST)
    assert wait_for(lambda: svc.snapshot().yawning_events >= 1, timeout=6)
    svc.stop()
    row = db.get_sessions()[0]
    assert row["total_yawning_events"] == 1 and row["total_drowsiness_alerts"] == 0
    assert audio.plays == []
    db.close()


def test_no_face_reports_status(tmp_path):
    db, _, _, svc = build(tmp_path, processor=FakeProcessor(face=False))
    svc.start(FAST)
    assert wait_for(lambda: svc.snapshot().status == "FACE NOT DETECTED")
    svc.stop()
    db.close()


def test_camera_unavailable_reports_error_and_creates_no_session(tmp_path):
    db, _, _, svc = build(tmp_path, camera=FakeCamera(fail_open=True))
    svc.start(FAST)
    assert wait_for(lambda: svc.snapshot().state == ERROR)
    snap = svc.snapshot()
    assert snap.status == CAMERA_UNAVAILABLE and "could not be opened" in snap.error_message
    assert db.get_sessions(finished_only=False) == []
    db.close()


def test_missing_model_reports_clear_error_and_creates_no_session(tmp_path):
    def boom():
        raise LandmarkModelError("Landmark model not found at: models/x.dat")
    db, _, _, svc = build(tmp_path, processor_factory=boom)
    svc.start(FAST)
    assert wait_for(lambda: svc.snapshot().state == ERROR)
    assert "Landmark model not found" in svc.snapshot().error_message
    assert db.get_sessions(finished_only=False) == []
    db.close()


def test_camera_lost_mid_session_still_saves_session(tmp_path):
    db, _, cam, svc = build(tmp_path, camera=FakeCamera(frames_before_failure=20),
                            max_read_failures=3)
    svc.start(FAST)
    assert wait_for(lambda: svc.snapshot().state == ERROR)
    assert svc.snapshot().status == CAMERA_UNAVAILABLE and cam.released
    rows = db.get_sessions()
    assert len(rows) == 1 and rows[0]["end_time"] is not None
    db.close()


def test_stop_restart_creates_separate_sessions_and_double_start_is_refused(tmp_path):
    db, _, _, svc = build(tmp_path, processor=FakeProcessor(ear=0.30, mar=0.20))
    assert svc.start(FAST) is True
    assert svc.start(FAST) is False  # already running
    assert wait_for(lambda: svc.snapshot().state == RUNNING)
    svc.stop()
    assert svc.start(FAST) is True
    assert wait_for(lambda: svc.snapshot().state == RUNNING)
    svc.stop()
    assert len(db.get_sessions()) == 2
    assert svc.stop() is True  # stopping when idle is harmless
    db.close()
