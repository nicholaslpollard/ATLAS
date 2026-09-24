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
    assert settings.tradier.credentials.api_key_env == "TRADIER_API_KEY"
    assert settings.tradier.market_data.requests_per_minute == 120
    assert settings.tradier.provider.production_base_url == "https://api.tradier.com/v1"


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


def test_massive_reference_settings_are_bounded():
    settings = load_settings(ROOT, "development")
    assert settings.massive.reference.page_limit == 1000
    assert settings.massive.reference.max_attempts >= 1


def test_external_storage_configuration_keeps_primary_stock_paths_local():
    settings = load_settings(ROOT, "development")
    bindings = settings.data.external_storage.bindings
    assert settings.data.external_storage.root_env == "ATLAS_EXTERNAL_DATA_ROOT"
    assert bindings["options"].project_subdir == Path("data/options")
    assert bindings["news"].project_subdir == Path("data/news")

    bound_paths = {Path(item.project_subdir) for item in bindings.values()}
    assert settings.data.paths.canonical not in bound_paths
    assert settings.data.paths.provider not in bound_paths
    assert settings.data.paths.duckdb not in bound_paths
    assert settings.data.paths.checkpoints not in bound_paths


def test_external_research_budget_is_separate_from_local_budget():
    settings = load_settings(ROOT, "development")
    storage = settings.data.research.storage
    assert storage.acquisition_budget_gib == 40
    assert storage.external_acquisition_budget_gib == 190
    assert storage.categories["options_candidate_cache"].quota_gib == 20
    assert storage.categories["options_candidate_cache"].external_quota_gib == 120
