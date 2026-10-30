import pytest

from app.core.config import Settings, get_settings


def test_demo_mode_without_key_ok(monkeypatch):
    monkeypatch.setenv("TASTEOS_MODE", "demo")
    monkeypatch.setenv("QLOO_API_KEY", "")
    get_settings.cache_clear()
    s = Settings()
    assert s.tasteos_mode == "demo"
    assert not s.qloo_configured


def test_live_mode_requires_key(monkeypatch):
    monkeypatch.setenv("TASTEOS_MODE", "live")
    monkeypatch.setenv("QLOO_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="QLOO_API_KEY"):
        Settings().require_live_qloo()


def test_base_url_strip(monkeypatch):
    monkeypatch.setenv("QLOO_BASE_URL", "https://hackathon.api.qloo.com/")
    s = Settings()
    assert s.qloo_base_url == "https://hackathon.api.qloo.com"


def test_database_url_normalized_for_render(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:pass@host:5432/tasteos",
    )
    s = Settings()
    assert s.database_url.startswith("postgresql+psycopg://")


def test_cors_origins_extra(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("FRONTEND_URL", "https://app.example")
    monkeypatch.setenv("CORS_ORIGINS", "https://preview.example, https://app.example/")
    get_settings.cache_clear()
    s = Settings()
    origins = s.cors_origins()
    assert "https://app.example" in origins
    assert "https://preview.example" in origins
