from packages.core.config import get_settings


def test_config_loading_from_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "unit-test-api")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/test_db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/9")
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy")
    monkeypatch.setenv("DEEPSEEK_RESEARCH_MODEL", "deepseek-reasoner")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.app_name == "unit-test-api"
    assert settings.app_env == "test"
    assert settings.database_url == "postgresql+psycopg://user:pass@localhost:5432/test_db"
    assert settings.redis_url == "redis://localhost:6379/9"
    assert settings.llm_provider == "deepseek"
    assert settings.deepseek_api_key == "dummy"
    assert settings.deepseek_research_model == "deepseek-reasoner"

    get_settings.cache_clear()
