from vision.drowsiness_detector import *

CFG = DetectionConfig(smoothing_window=1, eye_closure_duration=2.0,
                      yawn_min_duration=1.0, alert_cooldown=5.0)


def run(det, ear, mar, t0, t1, step=0.1):
    t, last = t0, None
    events = []
    while t <= t1 + 1e-9:
        last = det.update(ear, mar, now=t)
        events += last.events
        t += step
    return last, events


def test_blink_does_not_alert():
    d = DrowsinessDetector(CFG)
    _, ev = run(d, 0.1, 0.2, 0, 0.3)
    s, _ = run(d, 0.3, 0.2, 0.4, 1.0)
    assert not ev and s.status == NORMAL


def test_prolonged_closure_alerts_once_then_cooldown():
    d = DrowsinessDetector(CFG)
    s, ev = run(d, 0.1, 0.2, 0, 4.0)
    assert s.status == DROWSY
    assert [e.event_type for e in ev] == ["DROWSINESS_ALERT"]


def test_reopen_resets_timer():
    d = DrowsinessDetector(CFG)
    run(d, 0.1, 0.2, 0, 1.5)
    run(d, 0.3, 0.2, 1.6, 1.8)
    s, _ = run(d, 0.1, 0.2, 1.9, 3.0)
    assert s.status == EYES_CLOSED


def test_yawn_counted_once_and_is_secondary():
    d = DrowsinessDetector(CFG)
    s, ev = run(d, 0.3, 0.9, 0, 3.0)
    assert [e.event_type for e in ev] == ["YAWNING"]
    assert s.status == YAWNING


def test_brief_talking_not_yawn():
    d = DrowsinessDetector(CFG)
    _, ev = run(d, 0.3, 0.9, 0, 0.5)
    assert not ev


def test_no_face_after_grace():
    d = DrowsinessDetector(CFG)
    run(d, 0.3, 0.2, 0, 1.0)
    s = d.update(None, None, now=2.0)
    assert s.status == NO_FACE
