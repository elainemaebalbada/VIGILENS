"""Lightweight checks for Part 3's launch entry point and UI module structure."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_main_entry_point_exists():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "run_app" in source
    assert 'if __name__ == "__main__"' in source


def test_all_navigation_pages_are_defined():
    source = (ROOT / "ui" / "app.py").read_text(encoding="utf-8")
    for page in ("Dashboard", "Live Monitoring", "Session History", "Analytics", "Settings", "About"):
        assert page in source


def test_ui_uses_existing_services():
    source = (ROOT / "ui" / "app.py").read_text(encoding="utf-8")
    for component in ("MonitoringService", "SessionService", "SettingsService", "Database"):
        assert component in source
