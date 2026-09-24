from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

from .enums import Environment, MarketScope, TradingMode
from .exceptions import ConfigurationError


class ProjectConfig(BaseModel):
    name: str = "ATLAS"
    acronym: str
    version: str


class AppConfig(BaseModel):
    environment: Environment = Environment.DEVELOPMENT
    trading_mode: TradingMode = TradingMode.SHADOW
    market_scope: MarketScope = MarketScope.FULL_MARKET
    timezone: str = "America/New_York"
    canonical_timezone: str = "UTC"


class CalendarConfig(BaseModel):
    exchange: str = "XNYS"
    market_timezone: str = "America/New_York"
    canonical_timezone: str = "UTC"
    premarket_start_local: str = "04:00"
    after_hours_end_local: str = "20:00"


class DataPaths(BaseModel):
    provider: Path
    staging: Path
    canonical: Path
    derived: Path
    live: Path
    models: Path
    cache: Path
    duckdb: Path
    manifests: Path
    checkpoints: Path


class ExternalStorageBindingConfig(BaseModel):
    project_subdir: Path
    external_subdir: Path


class ExternalStorageConfig(BaseModel):
    root_env: str = "ATLAS_EXTERNAL_DATA_ROOT"
    marker_name: str = ".atlas_external_storage_v1.json"
    bindings: dict[str, ExternalStorageBindingConfig] = Field(default_factory=dict)


class CanonicalConfig(BaseModel):
    stock_timeframes: list[str]
    preserve_provider_vwap: bool = True
    preserve_transaction_count: bool = True
    partitioning: dict[str, str] = Field(default_factory=dict)


class ParquetConfig(BaseModel):
    compression: str = "zstd"
    row_group_size: int = Field(default=122_880, ge=10_000)


class StagingConfig(BaseModel):
    retain_normalized_after_success: bool = False


class ResearchStorageCategoryConfig(BaseModel):
    local_subdir: str
    quota_gib: float = Field(gt=0)
    external_quota_gib: float | None = Field(default=None, gt=0)


class ResearchStorageConfig(BaseModel):
    minimum_free_gib: float = Field(default=50.0, gt=0)
    warning_free_gib: float = Field(default=65.0, gt=0)
    acquisition_budget_gib: float = Field(default=40.0, gt=0)
    external_minimum_free_gib: float = Field(default=25.0, gt=0)
    external_warning_free_gib: float = Field(default=40.0, gt=0)
    external_acquisition_budget_gib: float = Field(default=190.0, gt=0)
    categories: dict[str, ResearchStorageCategoryConfig] = Field(default_factory=dict)


class HistoricalNewsResearchConfig(BaseModel):
    provider: str = "alpaca"
    start_date: str = "2015-01-01"
    endpoint_path: str = "/v1beta1/news"
    page_limit: int = Field(default=50, ge=1, le=50)
    raw_subdir: str = "news/raw"
    normalized_subdir: str = "news/normalized"
    features_subdir: str = "news/features"
    manifests_subdir: str = "news/manifests"


class HistoricalOptionsResearchConfig(BaseModel):
    primary_historical_provider: str = "massive"
    alpaca_candidate_provider_start_date: str = "2024-02-01"
    reference_endpoint_path: str = "/v3/reference/options/contracts"
    massive_day_prefix: str = "us_options_opra/day_aggs_v1"
    massive_minute_prefix: str = "us_options_opra/minute_aggs_v1"
    massive_trade_prefix: str = "us_options_opra/trades_v1"
    massive_quote_prefix: str = "us_options_opra/quotes_v1"
    reference_subdir: str = "options/reference"
    daily_subdir: str = "options/daily"
    candidate_chain_subdir: str = "options/candidate_cache/chains"
    candidate_minute_subdir: str = "options/candidate_cache/minute_bars"
    candidate_quote_subdir: str = "options/candidate_cache/quotes"
    candidate_trade_subdir: str = "options/candidate_cache/trades"
    derived_iv_subdir: str = "options/derived/implied_volatility"
    derived_greeks_subdir: str = "options/derived/greeks"
    manifests_subdir: str = "options/manifests"


class ResearchDataConfig(BaseModel):
    storage: ResearchStorageConfig = Field(default_factory=ResearchStorageConfig)
    news: HistoricalNewsResearchConfig = Field(default_factory=HistoricalNewsResearchConfig)
    options: HistoricalOptionsResearchConfig = Field(default_factory=HistoricalOptionsResearchConfig)


class DataConfig(BaseModel):
    calendar: CalendarConfig
    external_storage: ExternalStorageConfig = Field(default_factory=ExternalStorageConfig)
    canonical: CanonicalConfig
    parquet: ParquetConfig = Field(default_factory=ParquetConfig)
    staging: StagingConfig = Field(default_factory=StagingConfig)
    materialized_derived_bars: list[str]
    on_demand_bars: list[str]
    paths: DataPaths
    research: ResearchDataConfig = Field(default_factory=ResearchDataConfig)


class MassiveProviderConfig(BaseModel):
    name: str = "massive"
    rest_base_url: str
    websocket_delayed_url: str
    websocket_realtime_url: str
    flat_file_endpoint: str
    flat_file_bucket: str


class MassiveCredentialsConfig(BaseModel):
    api_key_env: str
    s3_access_key_env: str
    s3_secret_key_env: str


class MassiveStocksConfig(BaseModel):
    websocket_minute_channel: str = "AM"
    websocket_quote_channel: str = "Q"
    websocket_default_subscription: str = "*"
    use_delayed_feed_initially: bool = True
    delayed_feed_expected_delay_seconds: int = Field(default=900, ge=0)
    realtime_feed_expected_delay_seconds: int = Field(default=0, ge=0)
    websocket_open_timeout_seconds: float = Field(default=10.0, gt=0)
    websocket_auth_timeout_seconds: float = Field(default=10.0, gt=0)
    websocket_ping_interval_seconds: float = Field(default=20.0, gt=0)
    websocket_ping_timeout_seconds: float = Field(default=20.0, gt=0)
    websocket_ingress_queue_size: int = Field(default=10_000, ge=100)
    live_state_snapshot_interval_seconds: float = Field(default=5.0, gt=0)
    freshness_fresh_seconds: int = Field(default=90, ge=0)
    freshness_aging_seconds: int = Field(default=300, ge=1)


class MassiveFlatFileDatasetConfig(BaseModel):
    prefix: str
    local_subdir: str
    expected_columns: list[str]


class MassiveFlatFilesConfig(BaseModel):
    datasets: dict[str, MassiveFlatFileDatasetConfig]
    chunk_size_bytes: int = Field(default=4 * 1024 * 1024, ge=64 * 1024)
    max_attempts: int = Field(default=4, ge=1, le=20)
    initial_retry_seconds: float = Field(default=1.0, ge=0)
    max_retry_seconds: float = Field(default=20.0, ge=0)
    validate_gzip_crc: bool = True
    count_rows_during_validation: bool = False


class MassiveReferenceConfig(BaseModel):
    page_limit: int = Field(default=1000, ge=1, le=1000)
    requests_per_minute: int = Field(default=5, ge=1, le=10_000)
    request_timeout_seconds: float = Field(default=30.0, gt=0)
    max_attempts: int = Field(default=8, ge=1, le=20)
    initial_retry_seconds: float = Field(default=1.0, ge=0)
    max_retry_seconds: float = Field(default=20.0, ge=0)


class MassiveConfig(BaseModel):
    provider: MassiveProviderConfig
    credentials: MassiveCredentialsConfig
    stocks: MassiveStocksConfig
    flat_files: MassiveFlatFilesConfig
    reference: MassiveReferenceConfig = Field(default_factory=MassiveReferenceConfig)


class AlpacaMarketDataConfig(BaseModel):
    base_url: str = "https://data.alpaca.markets"
    feed: str = "sip"
    adjustment: str = "raw"
    asof: str = "-"
    timeframe: str = "1Day"
    page_limit: int = Field(default=10_000, ge=1, le=10_000)
    symbol_batch_size: int = Field(default=100, ge=1, le=500)
    requests_per_minute: int = Field(default=180, ge=1, le=10_000)
    request_timeout_seconds: float = Field(default=60.0, gt=0)
    max_attempts: int = Field(default=5, ge=1, le=20)
    initial_retry_seconds: float = Field(default=1.0, ge=0)
    max_retry_seconds: float = Field(default=30.0, ge=0)
    backfill_start: str = "2016-01-04"
    backfill_end: str = "2021-08-15"


class AlpacaCredentialsConfig(BaseModel):
    preferred_profile: str = "paper"
    paper_api_key_env: str = "ALPACA_PAPER_API_KEY"
    paper_api_secret_env: str = "ALPACA_PAPER_API_SECRET"
    paper_endpoint_env: str = "ALPACA_PAPER_ENDPOINT"
    live_api_key_env: str = "ALPACA_LIVE_API_KEY"
    live_api_secret_env: str = "ALPACA_LIVE_API_SECRET"
    live_endpoint_env: str = "ALPACA_LIVE_ENDPOINT"


class AlpacaBackfillConfig(BaseModel):
    provider_name: str = "alpaca"
    market_data: AlpacaMarketDataConfig = Field(default_factory=AlpacaMarketDataConfig)
    credentials: AlpacaCredentialsConfig = Field(default_factory=AlpacaCredentialsConfig)


class TradierProviderConfig(BaseModel):
    name: str = "tradier"
    production_base_url: str = "https://api.tradier.com/v1"
    websocket_market_url: str = "wss://ws.tradier.com/v1/markets/events"


class TradierCredentialsConfig(BaseModel):
    api_key_env: str = "TRADIER_API_KEY"


class TradierMarketDataConfig(BaseModel):
    requests_per_minute: int = Field(default=120, ge=1, le=1000)
    request_timeout_seconds: float = Field(default=30.0, gt=0)
    max_attempts: int = Field(default=4, ge=1, le=20)
    initial_retry_seconds: float = Field(default=1.0, ge=0)
    max_retry_seconds: float = Field(default=15.0, ge=0)
    qualification_batch_sizes: list[int] = Field(
        default_factory=lambda: [1, 10, 100, 250, 500, 1000]
    )


class TradierConfig(BaseModel):
    provider: TradierProviderConfig = Field(default_factory=TradierProviderConfig)
    credentials: TradierCredentialsConfig = Field(default_factory=TradierCredentialsConfig)
    market_data: TradierMarketDataConfig = Field(default_factory=TradierMarketDataConfig)


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str
    utc_timestamps: bool = True
    redact_secrets: bool = True


class AtlasSettings(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    project_root: Path
    project: ProjectConfig
    app: AppConfig
    data: DataConfig
    massive: MassiveConfig
    alpaca: AlpacaBackfillConfig
    tradier: TradierConfig
    logging: LoggingConfig

    def external_data_root(self) -> Path | None:
        value = os.getenv(self.data.external_storage.root_env)
        if value is None or not value.strip():
            return None
        return Path(value).expanduser().resolve()

    def external_storage_binding_paths(
        self,
        name: str,
        *,
        root_override: Path | None = None,
    ) -> tuple[Path, Path]:
        try:
            binding = self.data.external_storage.bindings[name]
        except KeyError as exc:
            raise ConfigurationError(f"Unknown external-storage binding: {name}") from exc
        external_root = (
            Path(root_override).expanduser().resolve()
            if root_override is not None
            else self.external_data_root()
        )
        if external_root is None:
            raise ConfigurationError(
                f"{self.data.external_storage.root_env} is not configured"
            )
        project_path = Path(
            os.path.abspath(self.project_root / binding.project_subdir)
        )
        external_path = (external_root / binding.external_subdir).resolve()
        return project_path, external_path

    def assert_external_storage_binding(self, name: str) -> None:
        external_root = self.external_data_root()
        if external_root is None:
            return
        if not external_root.is_dir():
            raise ConfigurationError(
                f"Configured external ATLAS data root is unavailable: {external_root}"
            )
        project_path, external_path = self.external_storage_binding_paths(name)
        if not external_path.is_dir() or not project_path.exists():
            raise ConfigurationError(
                f"External-storage binding {name!r} is not ready: "
                f"{project_path} -> {external_path}"
            )
        try:
            same = os.path.samefile(project_path, external_path)
        except OSError:
            same = False
        if not same:
            raise ConfigurationError(
                f"External-storage binding {name!r} does not point to its configured "
                f"external target: {project_path} -> {external_path}"
            )

    def _binding_for_relative_path(self, path: Path) -> str | None:
        if path.is_absolute():
            return None
        candidate = Path(*path.parts)
        for name, binding in self.data.external_storage.bindings.items():
            project_subdir = Path(binding.project_subdir)
            try:
                candidate.relative_to(project_subdir)
            except ValueError:
                continue
            return name
        return None

    def resolved_path(self, relative: Path | str) -> Path:
        path = Path(relative)
        if path.is_absolute():
            return path
        binding = self._binding_for_relative_path(path)
        if binding is not None:
            self.assert_external_storage_binding(binding)
        return (self.project_root / path).resolve()


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(f"Required configuration file does not exist: {path}")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigurationError(f"Configuration root must be a mapping: {path}")
    return value


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def find_project_root(start: Path | None = None) -> Path:
    explicit = os.getenv("ATLAS_ROOT")
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if not (root / "config" / "app.yaml").exists():
            raise ConfigurationError(f"ATLAS_ROOT does not point to a valid ATLAS repository: {root}")
        return root

    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "config" / "app.yaml").exists():
            return candidate
    raise ConfigurationError("Could not locate ATLAS project root. Run from the repository or set ATLAS_ROOT.")


def load_settings(project_root: Path | None = None, environment: str | Environment | None = None) -> AtlasSettings:
    root = (project_root.resolve() if project_root else find_project_root())

    load_dotenv(dotenv_path=root / ".env", override=False)

    config_dir = root / "config"
    app_doc = _load_yaml(config_dir / "app.yaml")
    data_doc = _load_yaml(config_dir / "data.yaml")
    massive_doc = _load_yaml(config_dir / "massive.yaml")
    alpaca_doc = _load_yaml(config_dir / "alpaca.yaml")
    tradier_doc = _load_yaml(config_dir / "tradier.yaml")
    logging_doc = _load_yaml(config_dir / "logging.yaml")

    env_name = str(environment or os.getenv("ATLAS_ENV") or app_doc.get("app", {}).get("environment", "development"))
    env_path = config_dir / "environments" / f"{env_name}.yaml"
    overlay = _load_yaml(env_path)

    merged: dict[str, Any] = {}
    for doc in (app_doc, data_doc, massive_doc, alpaca_doc, tradier_doc, logging_doc):
        merged = _deep_merge(merged, doc)
    merged = _deep_merge(merged, overlay)
    merged["project_root"] = root

    try:
        return AtlasSettings.model_validate(merged)
    except Exception as exc:
        raise ConfigurationError(f"ATLAS configuration validation failed: {exc}") from exc
