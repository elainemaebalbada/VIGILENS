import pytest

from database.database import Database
from services.settings_service import (AppSettings, SettingsService,
                                       SettingsValidationError, parse_settings,
                                       to_detection_config)


def make(tmp_path):
    db = Database(str(tmp_path / "s.db"))
    return db, SettingsService(db, sounds_dir=str(tmp_path / "no_sounds"))


def test_defaults_when_nothing_stored(tmp_path):
    db, svc = make(tmp_path)
    assert svc.load() == AppSettings()
    db.close()


def test_save_persists_after_restart(tmp_path):
    db, svc = make(tmp_path)
    svc.save({"ear_threshold": "0.25", "mar_threshold": "0.7", "eye_closure_duration": "3",
              "audio_enabled": False, "camera_index": "1", "alert_sound": "beep.wav"})
    db.close()
    db2, svc2 = make(tmp_path)
    loaded = svc2.load()
    assert loaded == AppSettings(0.25, 0.7, 3.0, False, 1, "beep.wav")
    db2.close()


def test_reset_to_defaults(tmp_path):
    db, svc = make(tmp_path)
    svc.save({"ear_threshold": 0.3})
    assert svc.reset_defaults() == AppSettings()
    assert svc.load() == AppSettings()
    db.close()


def test_invalid_values_report_every_field(tmp_path):
    db, svc = make(tmp_path)
    with pytest.raises(SettingsValidationError) as info:
        svc.save({"ear_threshold": "abc", "mar_threshold": 9, "eye_closure_duration": 0.1,
                  "camera_index": "1.5", "alert_sound": "../evil.wav", "audio_enabled": "maybe"})
    assert set(info.value.errors) == {"ear_threshold", "mar_threshold", "eye_closure_duration",
                                      "camera_index", "alert_sound", "audio_enabled"}
    assert svc.load() == AppSettings() 
    db.close()


def test_nan_and_infinity_rejected():
    for bad in ("nan", "inf", "-inf"):
        with pytest.raises(SettingsValidationError):
            parse_settings({"ear_threshold": bad})


def test_unknown_sound_rejected_when_sound_list_known():
    with pytest.raises(SettingsValidationError):
        parse_settings({"alert_sound": "missing.wav"}, available_sounds=["alarm.wav"])


def test_corrupt_stored_value_falls_back_to_default(tmp_path):
    db, svc = make(tmp_path)
    db.set_settings({"ear_threshold": "garbage", "camera_index": "2"})
    loaded = svc.load()
    assert loaded.ear_threshold == 0.21 and loaded.camera_index == 2
    db.close()


def test_detection_config_built_from_settings():
    cfg = to_detection_config(AppSettings(ear_threshold=0.2, mar_threshold=0.5,
                                          eye_closure_duration=1.5))
    assert (cfg.ear_threshold, cfg.mar_threshold, cfg.eye_closure_duration) == (0.2, 0.5, 1.5)
