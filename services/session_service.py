"""Read-side helpers that turn database rows into UI-ready data."""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from database.database import Database, parse_iso

EVENT_LABELS = {"DROWSINESS_ALERT": "Drowsiness alert", "YAWNING": "Possible yawning"}


def format_duration(seconds: float) -> str:
    total = int(round(seconds or 0))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _time_text(value: Optional[str]) -> str:
    return parse_iso(value).strftime("%H:%M:%S") if value else "-"


@dataclass
class SessionRow:
    session_id: int
    date: str
    start_time: str
    end_time: str
    duration_seconds: float
    duration_text: str
    alerts: int
    yawns: int


def _to_row(raw: Dict[str, Any]) -> SessionRow:
    return SessionRow(
        session_id=raw["session_id"],
        date=parse_iso(raw["start_time"]).strftime("%Y-%m-%d"),
        start_time=_time_text(raw["start_time"]),
        end_time=_time_text(raw["end_time"]),
        duration_seconds=raw["duration"],
        duration_text=format_duration(raw["duration"]),
        alerts=raw["total_drowsiness_alerts"],
        yawns=raw["total_yawning_events"])


class SessionService:
    def __init__(self, db: Database):
        self.db = db

    def list_sessions(self, limit: Optional[int] = None) -> List[SessionRow]:
        return [_to_row(r) for r in self.db.get_sessions(limit)]

    def get_session_events(self, session_id: int) -> List[Dict[str, Any]]:
        return [{"event_id": e["event_id"],
                 "time": _time_text(e["timestamp"]),
                 "type": EVENT_LABELS.get(e["event_type"], e["event_type"]),
                 "ear": e["ear_value"], "mar": e["mar_value"],
                 "closure_seconds": e["eye_closure_duration"]}
                for e in self.db.get_events(session_id)]

    def delete_session(self, session_id: int) -> None:
        self.db.delete_session(session_id)

    def get_dashboard_stats(self) -> Dict[str, Any]:
        totals = self.db.get_totals()
        latest = self.db.get_sessions(limit=1)
        return {"total_sessions": int(totals["total_sessions"]),
                "total_alerts": int(totals["total_alerts"]),
                "total_yawns": int(totals["total_yawns"]),
                "latest_session": _to_row(latest[0]) if latest else None}

    def get_analytics(self, max_sessions: int = 15) -> Dict[str, Any]:
        """Everything the Analytics page plots; all values come from the database."""
        totals = self.db.get_totals()
        sessions = list(reversed(self.db.get_sessions(limit=max_sessions)))  # oldest first
        hours = totals["total_duration"] / 3600.0
        events_total = totals["total_alerts"] + totals["total_yawns"]
        ear_series = None
        for raw in reversed(sessions):  # newest session that has enough samples
            samples = self.db.get_ear_samples(raw["session_id"])
            if len(samples) >= 2:
                ear_series = {"session_id": raw["session_id"],
                              "seconds": [s[0] for s in samples],
                              "ear": [s[1] for s in samples]}
                break
        return {"total_sessions": int(totals["total_sessions"]),
                "total_alerts": int(totals["total_alerts"]),
                "total_yawns": int(totals["total_yawns"]),
                "avg_duration_seconds": totals["avg_duration"],
                "avg_duration_text": format_duration(totals["avg_duration"]),
                "events_per_hour": (events_total / hours) if hours > 0 else 0.0,
                "per_session": [{"label": f"#{r['session_id']}",
                                 "alerts": r["total_drowsiness_alerts"],
                                 "yawns": r["total_yawning_events"],
                                 "minutes": r["duration"] / 60.0} for r in sessions],
                "ear_series": ear_series}
