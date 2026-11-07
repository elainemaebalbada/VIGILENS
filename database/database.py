"""SQLite access layer. One shared connection guarded by a lock so the
monitoring thread and the UI thread can both use it safely."""
import os
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from config import DB_PATH

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
EVENT_TYPES = ("DROWSINESS_ALERT", "YAWNING")


class DatabaseError(RuntimeError):
    """Raised for any database problem, with a readable message."""


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._open()

    # ------------------------------------------------------------ lifecycle
    def _open(self) -> None:
        try:
            if self.path != ":memory:":
                os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            conn = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            with open(SCHEMA_PATH, "r", encoding="utf-8") as handle:
                conn.executescript(handle.read())
            conn.commit()
        except (sqlite3.Error, OSError) as exc:
            raise DatabaseError(f"Could not open database '{self.path}': {exc}") from exc
        self._conn = conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except sqlite3.Error:
                    pass
                self._conn = None

    # -------------------------------------------------------------- helpers
    def _write(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            if self._conn is None:
                raise DatabaseError("Database is closed.")
            try:
                with self._conn:  # commits on success, rolls back on error
                    return self._conn.execute(sql, params)
            except sqlite3.Error as exc:
                raise DatabaseError(f"Database write failed: {exc}") from exc

    def _write_many(self, sql: str, rows: Iterable[Sequence[Any]]) -> None:
        with self._lock:
            if self._conn is None:
                raise DatabaseError("Database is closed.")
            try:
                with self._conn:
                    self._conn.executemany(sql, list(rows))
            except sqlite3.Error as exc:
                raise DatabaseError(f"Database write failed: {exc}") from exc

    def _read(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        with self._lock:
            if self._conn is None:
                raise DatabaseError("Database is closed.")
            try:
                return [dict(r) for r in self._conn.execute(sql, params).fetchall()]
            except sqlite3.Error as exc:
                raise DatabaseError(f"Database read failed: {exc}") from exc

    # ------------------------------------------------------------- sessions
    def create_session(self, start_time: Optional[str] = None) -> int:
        cur = self._write("INSERT INTO sessions (start_time) VALUES (?)",
                          (start_time or now_iso(),))
        return int(cur.lastrowid)

    def end_session(self, session_id: int, duration: Optional[float] = None,
                    end_time: Optional[str] = None) -> None:
        """Close a session. Alert/yawn totals are recounted from the events
        table so the session row can never disagree with its events."""
        end_time = end_time or now_iso()
        if duration is None:
            row = self.get_session(session_id)
            if row is None:
                raise DatabaseError(f"Session {session_id} does not exist.")
            delta = parse_iso(end_time) - parse_iso(row["start_time"])
            duration = max(0.0, delta.total_seconds())
        cur = self._write(
            """UPDATE sessions SET end_time = ?, duration = ?,
                 total_drowsiness_alerts = (SELECT COUNT(*) FROM detection_events
                     WHERE session_id = ? AND event_type = 'DROWSINESS_ALERT'),
                 total_yawning_events = (SELECT COUNT(*) FROM detection_events
                     WHERE session_id = ? AND event_type = 'YAWNING')
               WHERE session_id = ?""",
            (end_time, float(duration), session_id, session_id, session_id))
        if cur.rowcount == 0:
            raise DatabaseError(f"Session {session_id} does not exist.")

    def close_unfinished_sessions(self) -> int:
        """Recover sessions left open by a crash or power loss."""
        count = 0
        for row in self._read("SELECT session_id, start_time FROM sessions WHERE end_time IS NULL"):
            last = self._read("SELECT MAX(timestamp) AS t FROM detection_events WHERE session_id = ?",
                              (row["session_id"],))[0]["t"]
            self.end_session(row["session_id"], end_time=last or row["start_time"])
            count += 1
        return count

    def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        rows = self._read("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        return rows[0] if rows else None

    def get_sessions(self, limit: Optional[int] = None,
                     finished_only: bool = True) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM sessions"
        if finished_only:
            sql += " WHERE end_time IS NOT NULL"
        sql += " ORDER BY session_id DESC"
        params: Tuple[Any, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (int(limit),)
        return self._read(sql, params)

    def delete_session(self, session_id: int) -> None:
        self._write("DELETE FROM sessions WHERE session_id = ?", (session_id,))

    def get_totals(self) -> Dict[str, float]:
        return self._read(
            """SELECT COUNT(*) AS total_sessions,
                      COALESCE(SUM(total_drowsiness_alerts), 0) AS total_alerts,
                      COALESCE(SUM(total_yawning_events), 0) AS total_yawns,
                      COALESCE(AVG(duration), 0) AS avg_duration,
                      COALESCE(SUM(duration), 0) AS total_duration
               FROM sessions WHERE end_time IS NOT NULL""")[0]

    # --------------------------------------------------------------- events
    def add_event(self, session_id: int, event_type: str, ear: Optional[float],
                  mar: Optional[float], closure_duration: float = 0.0,
                  timestamp: Optional[str] = None) -> int:
        if event_type not in EVENT_TYPES:
            raise DatabaseError(f"Unknown event type '{event_type}'.")
        cur = self._write(
            """INSERT INTO detection_events
               (session_id, event_type, timestamp, ear_value, mar_value, eye_closure_duration)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, event_type, timestamp or now_iso(), ear, mar, float(closure_duration)))
        return int(cur.lastrowid)

    def get_events(self, session_id: int) -> List[Dict[str, Any]]:
        return self._read("SELECT * FROM detection_events WHERE session_id = ? ORDER BY event_id",
                          (session_id,))

    def add_ear_samples(self, session_id: int, samples: Iterable[Tuple[float, float]]) -> None:
        self._write_many(
            "INSERT INTO ear_samples (session_id, elapsed_seconds, ear_value) VALUES (?, ?, ?)",
            [(session_id, float(t), float(e)) for t, e in samples])

    def get_ear_samples(self, session_id: int) -> List[Tuple[float, float]]:
        rows = self._read("SELECT elapsed_seconds, ear_value FROM ear_samples "
                          "WHERE session_id = ? ORDER BY elapsed_seconds", (session_id,))
        return [(r["elapsed_seconds"], r["ear_value"]) for r in rows]

    # ------------------------------------------------------------- settings
    def get_settings(self) -> Dict[str, str]:
        return {r["key"]: r["value"] for r in self._read("SELECT key, value FROM app_settings")}

    def set_settings(self, values: Dict[str, Any]) -> None:
        self._write_many(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [(k, str(v)) for k, v in values.items()])
