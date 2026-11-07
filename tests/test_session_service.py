import pytest

from database.database import Database
from services.session_service import SessionService, format_duration


def test_format_duration():
    assert format_duration(5) == "5s"
    assert format_duration(125) == "2m 05s"
    assert format_duration(3723) == "1h 02m 03s"


def test_empty_database_gives_empty_state(tmp_path):
    db = Database(str(tmp_path / "e.db"))
    svc = SessionService(db)
    stats = svc.get_dashboard_stats()
    assert stats["total_sessions"] == 0 and stats["latest_session"] is None
    analytics = svc.get_analytics()
    assert analytics["per_session"] == [] and analytics["ear_series"] is None
    db.close()


def test_rows_events_and_analytics_reflect_stored_data(tmp_path):
    db = Database(str(tmp_path / "d.db"))
    sid = db.create_session("2026-10-31T09:00:00")
    db.add_event(sid, "DROWSINESS_ALERT", 0.12, 0.3, 2.5, timestamp="2026-10-31T09:01:00")
    db.add_event(sid, "YAWNING", 0.3, 0.8, timestamp="2026-10-31T09:02:00")
    db.add_ear_samples(sid, [(0.0, 0.3), (0.5, 0.2), (1.0, 0.1)])
    db.end_session(sid, duration=3600, end_time="2026-10-31T10:00:00")
    svc = SessionService(db)
    row = svc.list_sessions()[0]
    assert (row.date, row.start_time, row.end_time) == ("2026-10-31", "09:00:00", "10:00:00")
    assert (row.alerts, row.yawns, row.duration_text) == (1, 1, "1h 00m 00s")
    events = svc.get_session_events(sid)
    assert [e["type"] for e in events] == ["Drowsiness alert", "Possible yawning"]
    analytics = svc.get_analytics()
    assert analytics["events_per_hour"] == pytest.approx(2.0)
    assert analytics["ear_series"]["ear"] == [0.3, 0.2, 0.1]
    assert svc.get_dashboard_stats()["latest_session"].session_id == sid
    db.close()
