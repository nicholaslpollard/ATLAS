from __future__ import annotations

import hashlib
import json
from datetime import date

from packages.data.alpaca_backfill_policy import (
    ALPACA_BACKFILL_END,
    ALPACA_BACKFILL_START,
    ALPACA_MASSIVE_SEAM_START,
)
from packages.regimes.split_origin_policy import (
    INTRADAY_POLICY,
    MARKET_SECTOR_HISTORY_ORIGIN_DATE,
    TICKER_HISTORY_ORIGIN_DATE,
)


CUMULATIVE_FOUNDATION_AUDIT_CONTRACT_VERSION = (
    "cumulative-foundation-audit-v1-readonly-2016-provider-seam-features-regimes"
)
CUMULATIVE_FOUNDATION_ACCEPTANCE_VERSION = (
    "cumulative-foundation-acceptance-v1-hash-bound-cross-layer"
)

# This audit is intentionally read-only with respect to accepted market data,
# features, regimes, model artifacts, and broker state. It may write only its own
# reports beneath data/derived/validation/cumulative_foundation/v1.
CUMULATIVE_AUDIT_CANONICAL_WRITES = 0
CUMULATIVE_AUDIT_FEATURE_WRITES = 0
CUMULATIVE_AUDIT_REGIME_WRITES = 0
CUMULATIVE_AUDIT_MODEL_WRITES = 0
CUMULATIVE_AUDIT_BROKER_WRITES = 0
CUMULATIVE_AUDIT_EXTERNAL_PROVIDER_CALLS = 0

# Structural authority boundaries inherited from accepted historical-backfill
# evidence. These are pass/fail invariants, not post-hoc thresholds.
CUMULATIVE_HISTORY_START = ALPACA_BACKFILL_START
CUMULATIVE_ALPACA_AUTHORITY_END = ALPACA_BACKFILL_END
CUMULATIVE_MASSIVE_AUTHORITY_START = ALPACA_MASSIVE_SEAM_START
CUMULATIVE_MARKET_SECTOR_REGIME_ORIGIN = MARKET_SECTOR_HISTORY_ORIGIN_DATE
CUMULATIVE_TICKER_REGIME_ORIGIN = TICKER_HISTORY_ORIGIN_DATE
CUMULATIVE_INTRADAY_POLICY = INTRADAY_POLICY

# Deterministic bounded content replay. Full daily canonical integrity is exhaustive;
# potentially massive intraday content replay is deterministic and stratified while
# file/manifest presence and forbidden pre-origin intraday are exhaustive.
CUMULATIVE_INTRADAY_SAMPLE_SESSIONS_PER_YEAR = 4
CUMULATIVE_INTRADAY_SAMPLE_SYMBOLS_PER_SESSION = 12
CUMULATIVE_FEATURE_SAMPLE_SYMBOLS_PER_TIMEFRAME = 12
CUMULATIVE_FEATURE_SAMPLE_OBSERVATIONS_PER_SYMBOL = 8
CUMULATIVE_FEATURE_NUMERIC_ABS_TOLERANCE = 1e-9
CUMULATIVE_FEATURE_NUMERIC_REL_TOLERANCE = 1e-8
CUMULATIVE_BAR_NUMERIC_ABS_TOLERANCE = 1e-9
CUMULATIVE_BAR_NUMERIC_REL_TOLERANCE = 1e-8

# Diagnostics are reported but do not become new acceptance thresholds. Only
# structural violations and mismatches against already accepted contracts fail v1.
CUMULATIVE_STATISTICAL_DIAGNOSTICS_ARE_NONAUTHORITATIVE = True
CUMULATIVE_ANOMALY_THRESHOLDS_POSTHOC_FORBIDDEN = True


def cumulative_policy_payload() -> dict[str, object]:
    return {
        "contract_version": CUMULATIVE_FOUNDATION_AUDIT_CONTRACT_VERSION,
        "history": {
            "start": CUMULATIVE_HISTORY_START.isoformat(),
            "alpaca_authority_end": CUMULATIVE_ALPACA_AUTHORITY_END.isoformat(),
            "massive_authority_start": CUMULATIVE_MASSIVE_AUTHORITY_START.isoformat(),
        },
        "regimes": {
            "market_sector_origin": CUMULATIVE_MARKET_SECTOR_REGIME_ORIGIN.isoformat(),
            "ticker_origin": CUMULATIVE_TICKER_REGIME_ORIGIN.isoformat(),
            "intraday_policy": CUMULATIVE_INTRADAY_POLICY,
        },
        "sampling": {
            "intraday_sessions_per_year": CUMULATIVE_INTRADAY_SAMPLE_SESSIONS_PER_YEAR,
            "intraday_symbols_per_session": CUMULATIVE_INTRADAY_SAMPLE_SYMBOLS_PER_SESSION,
            "feature_symbols_per_timeframe": CUMULATIVE_FEATURE_SAMPLE_SYMBOLS_PER_TIMEFRAME,
            "feature_observations_per_symbol": CUMULATIVE_FEATURE_SAMPLE_OBSERVATIONS_PER_SYMBOL,
        },
        "tolerances": {
            "feature_abs": CUMULATIVE_FEATURE_NUMERIC_ABS_TOLERANCE,
            "feature_rel": CUMULATIVE_FEATURE_NUMERIC_REL_TOLERANCE,
            "bar_abs": CUMULATIVE_BAR_NUMERIC_ABS_TOLERANCE,
            "bar_rel": CUMULATIVE_BAR_NUMERIC_REL_TOLERANCE,
        },
        "authority": {
            "canonical_writes": CUMULATIVE_AUDIT_CANONICAL_WRITES,
            "feature_writes": CUMULATIVE_AUDIT_FEATURE_WRITES,
            "regime_writes": CUMULATIVE_AUDIT_REGIME_WRITES,
            "model_writes": CUMULATIVE_AUDIT_MODEL_WRITES,
            "broker_writes": CUMULATIVE_AUDIT_BROKER_WRITES,
            "external_provider_calls": CUMULATIVE_AUDIT_EXTERNAL_PROVIDER_CALLS,
        },
        "diagnostics": {
            "statistical_diagnostics_are_nonauthoritative": CUMULATIVE_STATISTICAL_DIAGNOSTICS_ARE_NONAUTHORITATIVE,
            "posthoc_anomaly_thresholds_forbidden": CUMULATIVE_ANOMALY_THRESHOLDS_POSTHOC_FORBIDDEN,
        },
    }


def cumulative_policy_fingerprint() -> str:
    raw = json.dumps(
        cumulative_policy_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_cumulative_policy() -> None:
    assert CUMULATIVE_HISTORY_START == date(2016, 1, 4)
    assert CUMULATIVE_ALPACA_AUTHORITY_END < CUMULATIVE_MASSIVE_AUTHORITY_START
    assert CUMULATIVE_MARKET_SECTOR_REGIME_ORIGIN == CUMULATIVE_HISTORY_START
    assert CUMULATIVE_TICKER_REGIME_ORIGIN == CUMULATIVE_MASSIVE_AUTHORITY_START
    assert CUMULATIVE_INTRADAY_POLICY == "NO_SYNTHETIC_PRE2021_4H_OR_1H_FROM_DAILY_BACKFILL"
    assert CUMULATIVE_AUDIT_CANONICAL_WRITES == 0
    assert CUMULATIVE_AUDIT_FEATURE_WRITES == 0
    assert CUMULATIVE_AUDIT_REGIME_WRITES == 0
    assert CUMULATIVE_AUDIT_MODEL_WRITES == 0
    assert CUMULATIVE_AUDIT_BROKER_WRITES == 0
    assert CUMULATIVE_AUDIT_EXTERNAL_PROVIDER_CALLS == 0
    assert CUMULATIVE_STATISTICAL_DIAGNOSTICS_ARE_NONAUTHORITATIVE
    assert CUMULATIVE_ANOMALY_THRESHOLDS_POSTHOC_FORBIDDEN
