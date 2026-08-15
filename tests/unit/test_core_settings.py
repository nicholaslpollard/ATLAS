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
