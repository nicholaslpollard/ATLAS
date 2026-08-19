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


class DataConfig(BaseModel):
    calendar: CalendarConfig
    canonical: CanonicalConfig
    parquet: ParquetConfig = Field(default_factory=ParquetConfig)
    staging: StagingConfig = Field(default_factory=StagingConfig)
    materialized_derived_bars: list[str]
    on_demand_bars: list[str]
    paths: DataPaths


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
    request_timeout_seconds: float = Field(default=30.0, gt=0)
    max_attempts: int = Field(default=4, ge=1, le=20)
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
    logging: LoggingConfig

    def resolved_path(self, relative: Path | str) -> Path:
        path = Path(relative)
        return path if path.is_absolute() else (self.project_root / path).resolve()


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
    logging_doc = _load_yaml(config_dir / "logging.yaml")

    env_name = str(environment or os.getenv("ATLAS_ENV") or app_doc.get("app", {}).get("environment", "development"))
    env_path = config_dir / "environments" / f"{env_name}.yaml"
    overlay = _load_yaml(env_path)

    merged: dict[str, Any] = {}
    for doc in (app_doc, data_doc, massive_doc, alpaca_doc, logging_doc):
        merged = _deep_merge(merged, doc)
    merged = _deep_merge(merged, overlay)
    merged["project_root"] = root

    try:
        return AtlasSettings.model_validate(merged)
    except Exception as exc:
        raise ConfigurationError(f"ATLAS configuration validation failed: {exc}") from exc
