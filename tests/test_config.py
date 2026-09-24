"""Tests for configuration loading."""

from app.config.settings import Settings


def test_settings_loads_environment(monkeypatch) -> None:
    """Environment variables should populate the settings object."""
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("READ_ONLY_MODE", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "demo-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    settings = Settings()

    assert settings.app_env == "local"
    assert settings.read_only_mode is True
    assert settings.google_cloud_project == "demo-project"
    assert settings.google_cloud_location == "us-central1"
    assert settings.gemini_model == "gemini-2.0-flash"
    assert settings.log_level == "DEBUG"

    settings.validate()
