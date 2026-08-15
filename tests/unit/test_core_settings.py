from pathlib import Path

from packages.core.enums import Environment, TradingMode
from packages.core.settings import load_settings
from packages.core.secrets import redact_mapping


ROOT = Path(__file__).resolve().parents[2]


def test_development_settings_load():
    settings = load_settings(ROOT, "development")
    assert settings.project.name == "ATLAS"
    assert settings.app.environment == Environment.DEVELOPMENT
    assert settings.app.trading_mode == TradingMode.SHADOW
    assert settings.data.calendar.exchange == "XNYS"
    assert settings.massive.credentials.api_key_env == "MASSIVE_API_KEY"


def test_live_overlay_selects_autonomous_mode():
    settings = load_settings(ROOT, "live")
    assert settings.app.environment == Environment.LIVE
    assert settings.app.trading_mode == TradingMode.AUTONOMOUS


def test_resolved_path_is_under_repo():
    settings = load_settings(ROOT, "development")
    assert settings.resolved_path(settings.data.paths.canonical) == (ROOT / "data/canonical").resolve()


def test_secret_redaction_is_recursive():
    redacted = redact_mapping({"api_key": "abc", "nested": {"password": "xyz"}, "normal": 4})
    assert redacted["api_key"] == "***REDACTED***"
    assert redacted["nested"]["password"] == "***REDACTED***"
    assert redacted["normal"] == 4


def test_root_dotenv_loads_local_secrets(tmp_path, monkeypatch):
    import shutil
    import os

    project_root = tmp_path / "ATLAS"
    shutil.copytree(ROOT / "config", project_root / "config")
    (project_root / ".env").write_text(
        "MASSIVE_API_KEY=dotenv-test-key\n"
        "MASSIVE_S3_ACCESS_KEY_ID=dotenv-access\n"
        "MASSIVE_S3_SECRET_ACCESS_KEY=dotenv-secret\n",
        encoding="utf-8",
    )

    for name in ("MASSIVE_API_KEY", "MASSIVE_S3_ACCESS_KEY_ID", "MASSIVE_S3_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(name, raising=False)

    from packages.core.secrets import get_secret

    load_settings(project_root, "development")
    assert get_secret("MASSIVE_API_KEY") == "dotenv-test-key"
    assert get_secret("MASSIVE_S3_ACCESS_KEY_ID") == "dotenv-access"
    assert get_secret("MASSIVE_S3_SECRET_ACCESS_KEY") == "dotenv-secret"

    # load_dotenv mutates os.environ directly, so clean up values it introduced.
    for name in ("MASSIVE_API_KEY", "MASSIVE_S3_ACCESS_KEY_ID", "MASSIVE_S3_SECRET_ACCESS_KEY"):
        os.environ.pop(name, None)


def test_process_environment_overrides_dotenv(tmp_path, monkeypatch):
    import shutil

    project_root = tmp_path / "ATLAS"
    shutil.copytree(ROOT / "config", project_root / "config")
    (project_root / ".env").write_text("MASSIVE_API_KEY=dotenv-value\n", encoding="utf-8")
    monkeypatch.setenv("MASSIVE_API_KEY", "process-value")

    from packages.core.secrets import get_secret

    load_settings(project_root, "development")
    assert get_secret("MASSIVE_API_KEY") == "process-value"
