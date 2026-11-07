import sqlite3

import pytest

from database.database import Database, DatabaseError


def make_db(tmp_path, name="test.db"):
    return Database(str(tmp_path / name))


def test_database_file_and_tables_created_automatically(tmp_path):
    path = tmp_path / "sub" / "new.db"
    db = Database(str(path))
    db.close()
    assert path.exists()
    conn = sqlite3.connect(str(path))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert {"sessions", "detection_events", "ear_samples", "app_settings"} <= tables


def test_reopening_existing_database_keeps_data(tmp_path):
    db = make_db(tmp_path)
    sid = db.create_session()
    db.close()
    db2 = make_db(tmp_path)
    assert db2.get_session(sid) is not None
    db2.close()


def test_session_lifecycle_counts_come_from_events(tmp_path):
    db = make_db(tmp_path)
    sid = db.create_session("2026-10-31T10:00:00")
    db.add_event(sid, "DROWSINESS_ALERT", 0.15, 0.3, 2.4)
    db.add_event(sid, "YAWNING", 0.30, 0.8)
    db.add_event(sid, "YAWNING", 0.28, 0.9)
    db.end_session(sid, duration=125.0, end_time="2026-10-31T10:02:05")
    row = db.get_session(sid)
    assert row["end_time"] == "2026-10-31T10:02:05"
    assert row["duration"] == 125.0
    assert row["total_drowsiness_alerts"] == 1
    assert row["total_yawning_events"] == 2
    events = db.get_events(sid)
    assert [e["event_type"] for e in events] == ["DROWSINESS_ALERT", "YAWNING", "YAWNING"]
    assert events[0]["eye_closure_duration"] == pytest.approx(2.4)
    db.close()


def test_duration_computed_from_timestamps_when_not_given(tmp_path):
    db = make_db(tmp_path)
    sid = db.create_session("2026-10-31T10:00:00")
    db.end_session(sid, end_time="2026-10-31T10:01:30")
    assert db.get_session(sid)["duration"] == pytest.approx(90.0)
    db.close()


def test_unfinished_sessions_hidden_until_finished(tmp_path):
    db = make_db(tmp_path)
    sid = db.create_session()
    assert db.get_sessions() == []
    assert len(db.get_sessions(finished_only=False)) == 1
    db.end_session(sid, duration=5)
    assert len(db.get_sessions()) == 1
    db.close()


def test_invalid_event_type_and_unknown_session_rejected(tmp_path):
    db = make_db(tmp_path)
    sid = db.create_session()
    with pytest.raises(DatabaseError):
        db.add_event(sid, "NOT_A_TYPE", 0.1, 0.1)
    with pytest.raises(DatabaseError):
        db.add_event(9999, "YAWNING", 0.1, 0.1)  # foreign key enforced
    with pytest.raises(DatabaseError):
        db.end_session(9999, duration=1)
    db.close()


def test_delete_session_cascades_to_events_and_samples(tmp_path):
    db = make_db(tmp_path)
    sid = db.create_session()
    db.add_event(sid, "YAWNING", 0.3, 0.8)
    db.add_ear_samples(sid, [(0.0, 0.3), (0.5, 0.29)])
    db.delete_session(sid)
    assert db.get_session(sid) is None
    assert db.get_events(sid) == []
    assert db.get_ear_samples(sid) == []
    db.close()


def test_ear_samples_roundtrip_in_order(tmp_path):
    db = make_db(tmp_path)
    sid = db.create_session()
    db.add_ear_samples(sid, [(1.0, 0.25), (0.0, 0.30), (0.5, 0.28)])
    assert [t for t, _ in db.get_ear_samples(sid)] == [0.0, 0.5, 1.0]
    db.close()


def test_totals(tmp_path):
    db = make_db(tmp_path)
    assert db.get_totals()["total_sessions"] == 0
    a = db.create_session()
    db.add_event(a, "DROWSINESS_ALERT", 0.1, 0.2, 2.0)
    db.end_session(a, duration=60)
    b = db.create_session()
    db.add_event(b, "YAWNING", 0.3, 0.8)
    db.end_session(b, duration=120)
    totals = db.get_totals()
    assert totals["total_sessions"] == 2
    assert totals["total_alerts"] == 1
    assert totals["total_yawns"] == 1
    assert totals["avg_duration"] == pytest.approx(90.0)
    db.close()


def test_close_unfinished_sessions_recovers_crashed_session(tmp_path):
    db = make_db(tmp_path)
    sid = db.create_session("2026-10-31T10:00:00")
    db.add_event(sid, "YAWNING", 0.3, 0.8, timestamp="2026-10-31T10:00:40")
    assert db.close_unfinished_sessions() == 1
    row = db.get_session(sid)
    assert row["end_time"] == "2026-10-31T10:00:40"
    assert row["duration"] == pytest.approx(40.0)
    assert row["total_yawning_events"] == 1
    assert db.close_unfinished_sessions() == 0
    db.close()


def test_settings_persist_across_reopen(tmp_path):
    db = make_db(tmp_path)
    db.set_settings({"ear_threshold": 0.25, "audio_enabled": "0"})
    db.set_settings({"ear_threshold": 0.27})  # overwrite
    db.close()
    db2 = make_db(tmp_path)
    assert db2.get_settings() == {"ear_threshold": "0.27", "audio_enabled": "0"}
    db2.close()


def test_closed_database_raises_database_error(tmp_path):
    db = make_db(tmp_path)
    db.close()
    with pytest.raises(DatabaseError):
        db.create_session()


def test_unwritable_location_raises_database_error(tmp_path):
    blocker = tmp_path / "file.txt"
    blocker.write_text("x")
    with pytest.raises(DatabaseError):
        Database(str(blocker / "inside.db"))  # parent is a file, not a folder
