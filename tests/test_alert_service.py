from services.alert_service import AlertService
from services.sound_generator import ensure_default_sounds


class FakeBackend:
    def __init__(self, fail_init=False):
        self.fail_init = fail_init
        self.plays = []
        self.busy = False
        self.stops = 0

    def initialize(self):
        if self.fail_init:
            raise RuntimeError("no audio device")

    def play(self, path):
        self.plays.append(path)

    def is_busy(self):
        return self.busy

    def stop(self):
        self.stops += 1

    def shutdown(self):
        pass


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def make(tmp_path, **kw):
    backend = kw.pop("backend", None) or FakeBackend()
    clock = Clock()
    svc = AlertService(sounds_dir=str(tmp_path), backend=backend, min_interval=3.0, clock=clock)
    return svc, backend, clock


def test_sounds_are_generated_and_played(tmp_path):
    svc, backend, _ = make(tmp_path)
    assert svc.trigger() is True
    assert backend.plays[0].endswith("alarm.wav")
    assert "alarm.wav" in ensure_default_sounds(str(tmp_path))


def test_disabled_audio_never_plays(tmp_path):
    svc, backend, _ = make(tmp_path)
    svc.configure(False, "alarm.wav")
    assert svc.trigger() is False and backend.plays == []
    assert svc.status_text() == "Audio alerts: OFF"
    svc.set_enabled(True)
    assert svc.trigger() is True


def test_no_overlap_while_sound_is_playing(tmp_path):
    svc, backend, clock = make(tmp_path)
    assert svc.trigger() is True
    clock.t += 10
    backend.busy = True
    assert svc.trigger() is False
    backend.busy = False
    assert svc.trigger() is True
    assert len(backend.plays) == 2


def test_rapid_repeat_is_suppressed(tmp_path):
    svc, backend, clock = make(tmp_path)
    assert svc.trigger() is True
    clock.t += 1.0
    assert svc.trigger() is False
    clock.t += 3.0
    assert svc.trigger() is True
    assert len(backend.plays) == 2


def test_missing_selected_sound_falls_back_to_default(tmp_path):
    svc, backend, _ = make(tmp_path)
    svc.configure(True, "gone.wav")
    assert svc.trigger() is True
    assert backend.plays[0].endswith("alarm.wav")


def test_audio_failure_is_reported_not_raised(tmp_path):
    svc, backend, _ = make(tmp_path, backend=FakeBackend(fail_init=True))
    assert svc.trigger() is False
    assert "Audio unavailable" in svc.status_text()
    assert svc.trigger() is False  # stays quiet, never crashes
