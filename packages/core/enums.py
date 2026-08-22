from enum import StrEnum


class Environment(StrEnum):
    DEVELOPMENT = "development"
    SHADOW = "shadow"
    APPROVAL = "approval"
    LIVE = "live"


class TradingMode(StrEnum):
    SHADOW = "shadow"
    APPROVAL = "approval"
    AUTONOMOUS = "autonomous"
    PAUSED = "paused"


class MarketScope(StrEnum):
    POSITIONS = "positions"
    POSITIONS_WATCHLIST = "positions_watchlist"
    FULL_MARKET = "full_market"
    CUSTOM = "custom"


class DataProvider(StrEnum):
    MASSIVE = "massive"
    ALPACA = "alpaca"
    ROBINHOOD = "robinhood"
    INTERNAL = "internal"


class DatasetType(StrEnum):
    STOCK_MINUTE_AGGREGATES = "stock_minute_aggregates"
    STOCK_DAILY_AGGREGATES = "stock_daily_aggregates"
    STOCK_REFERENCE = "stock_reference"
    CORPORATE_ACTIONS = "corporate_actions"
    DERIVED_STOCK_BARS = "derived_stock_bars"


class AssetClass(StrEnum):
    EQUITY = "equity"
    OPTION = "option"
    INDEX = "index"
    ETF = "etf"
    UNKNOWN = "unknown"


class InstrumentIdentityQuality(StrEnum):
    STRONG = "strong"
    MEDIUM = "medium"
    FALLBACK = "fallback"


class Timeframe(StrEnum):
    MINUTE_1 = "1m"
    MINUTE_15 = "15m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1mo"


class SessionSegment(StrEnum):
    PREMARKET = "premarket"
    REGULAR = "regular"
    AFTER_HOURS = "after_hours"
    FULL_DAY = "full_day"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class LiveFeedMode(StrEnum):
    DELAYED = "delayed"
    REALTIME = "realtime"


class LiveFreshness(StrEnum):
    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    UNKNOWN = "unknown"


class LiveConnectionState(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    SUBSCRIBED = "subscribed"
    DEGRADED = "degraded"
    STOPPED = "stopped"


class IngestionStatus(StrEnum):
    PLANNED = "planned"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    VALIDATING = "validating"
    VALIDATED = "validated"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


class ValidationStatus(StrEnum):
    UNKNOWN = "unknown"
    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"


class DataQualitySeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DataQualityCode(StrEnum):
    DUPLICATE_BAR = "duplicate_bar"
    MISSING_BAR = "missing_bar"
    INVALID_OHLC = "invalid_ohlc"
    NEGATIVE_VOLUME = "negative_volume"
    INVALID_TIMESTAMP = "invalid_timestamp"
    STALE_DATA = "stale_data"
    OUTLIER = "outlier"
    CORPORATE_ACTION_REVIEW = "corporate_action_review"
    SESSION_MISMATCH = "session_mismatch"
    SOURCE_MISMATCH = "source_mismatch"
    SYMBOL_CONFLICT = "symbol_conflict"
    INVALID_SYMBOL = "invalid_symbol"
    NULL_VALUE = "null_value"
    NEGATIVE_TRANSACTIONS = "negative_transactions"


class MaterializationStatus(StrEnum):
    PLANNED = "planned"
    NORMALIZING = "normalizing"
    VALIDATING = "validating"
    WRITING_CANONICAL = "writing_canonical"
    BUILDING_DERIVED = "building_derived"
    COMPLETE = "complete"
    FAILED = "failed"
