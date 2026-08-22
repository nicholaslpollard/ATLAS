from __future__ import annotations

from datetime import date

from .threshold_policy import REGIME_HISTORY_ORIGIN_DATE


MARKET_SECTOR_HISTORY_ORIGIN_DATE = date(2016, 1, 4)
TICKER_HISTORY_ORIGIN_DATE = REGIME_HISTORY_ORIGIN_DATE

SPLIT_ORIGIN_POLICY_VERSION = (
    "historical-backfill-regime-split-policy-v1-market-sector-daily-2016-ticker-intraday-2021"
)
MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION = (
    "regime-state-policy-v2-expanding252-confirm2-dimensional-daily-origin-2016"
)
MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION = (
    "regime-state-snapshot-v2-market-sector-proxies-daily-origin-2016"
)
MARKET_SECTOR_MANIFEST_VERSION = "regime-state-manifest-v2-split-origin-source-lineage"
INTRADAY_POLICY = "NO_SYNTHETIC_PRE2021_4H_OR_1H_FROM_DAILY_BACKFILL"

# Gate 10-A is the accepted evidence that established this production policy.  It is
# intentionally retained as immutable policy provenance so future v2 materializations
# remain lineage-compatible with the accepted Gate 10-B candidate.
MARKET_SECTOR_POLICY_GENESIS_FINGERPRINT = (
    "df85452f596808d0962d9f666dc4a1f27727edc8e2732b772a46873743cfdf54"
)

REGIME_HISTORY_DATASET_VERSION = "split_origin_v1"
