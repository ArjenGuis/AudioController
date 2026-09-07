"""Settings changelog: a secret-free audit trail of settings changes."""
import pytest
from audio_controller import settings


@pytest.fixture
def changelog(tmp_path, monkeypatch, tmp_settings_file):
    path = tmp_path / "settings_changes.log"
    monkeypatch.setattr(settings, "changelog_file", path)
    return path


def _read(path):
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_settings_change_is_logged_with_diff(changelog):
    settings.settings.title = "Oud"
    settings.update_settings({"title": "Nieuw"})
    text = _read(changelog)
    assert "settings" in text
    assert "title" in text and "Nieuw" in text


def test_unchanged_settings_write_logs_nothing(changelog):
    settings.update_settings({"title": settings.settings.title})  # no real change
    assert _read(changelog) == ""


def test_user_change_logs_names_not_passwords(changelog):
    settings.update_users([
        {"username": "beheer", "password": "GeheimWachtwoord!9", "admin": True, "camera": True},
    ])
    text = _read(changelog)
    assert "beheer" in text and "admin" in text
    assert "GeheimWachtwoord" not in text          # cleartext password never logged
    assert "pbkdf2" not in text                     # hash never logged


def test_camera_change_logs_name_host_not_credentials(changelog):
    settings.update_cameras([{
        "name": "Kerk", "url_intern": "192.168.1.9", "url_extern": "x.example",
        "port_http": 80, "port_onvif": 2000, "port_ws": 8088,
        "username": "admin", "password": "CamSecret!9", "config_presets": [], "active": "0",
    }])
    text = _read(changelog)
    assert "Kerk" in text and "192.168.1.9" in text
    assert "CamSecret" not in text                  # camera password never logged


def test_changelog_is_appended_not_overwritten(changelog):
    settings.update_settings({"title": "Een"})
    settings.update_settings({"title": "Twee"})
    assert len(_read(changelog).strip().splitlines()) >= 2
