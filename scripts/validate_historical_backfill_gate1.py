from __future__ import annotations

from packages.core.enums import DataProvider
from packages.core.settings import load_settings
from packages.data.alpaca_backfill_policy import (
    ALPACA_BACKFILL_ADJUSTMENT,
    ALPACA_BACKFILL_ASOF,
    ALPACA_BACKFILL_CANONICAL_WRITE_ENABLED,
    ALPACA_BACKFILL_CONTRACT_VERSION,
    ALPACA_BACKFILL_END,
    ALPACA_BACKFILL_FEED,
    ALPACA_BACKFILL_GATES,
    ALPACA_BACKFILL_PAGE_LIMIT,
    ALPACA_BACKFILL_REQUESTS_PER_MINUTE,
    ALPACA_BACKFILL_START,
    ALPACA_BACKFILL_TIMEFRAME,
    validate_backfill_contract,
)


def main() -> None:
    settings = load_settings()
    validate_backfill_contract()
    cfg = settings.alpaca.market_data

    checks = {
        "provider_enum_alpaca": DataProvider.ALPACA.value == "alpaca",
        "feed_is_sip": cfg.feed == ALPACA_BACKFILL_FEED == "sip",
        "adjustment_is_raw": cfg.adjustment == ALPACA_BACKFILL_ADJUSTMENT == "raw",
        "literal_symbol_mapping_disabled": cfg.asof == ALPACA_BACKFILL_ASOF == "-",
        "timeframe_is_daily": cfg.timeframe == ALPACA_BACKFILL_TIMEFRAME == "1Day",
        "page_limit_locked": cfg.page_limit == ALPACA_BACKFILL_PAGE_LIMIT == 10_000,
        "request_rate_locked": cfg.requests_per_minute == ALPACA_BACKFILL_REQUESTS_PER_MINUTE == 180,
        "backfill_start_locked": cfg.backfill_start == ALPACA_BACKFILL_START.isoformat(),
        "backfill_end_locked": cfg.backfill_end == ALPACA_BACKFILL_END.isoformat(),
        "canonical_write_disabled": not ALPACA_BACKFILL_CANONICAL_WRITE_ENABLED,
        "gate_order_locked": tuple(gate.number for gate in ALPACA_BACKFILL_GATES) == tuple(range(1, 13)),
    }

    print("ATLAS Historical Backfill Gate 1 Validation")
    print(f"  contract:                    {ALPACA_BACKFILL_CONTRACT_VERSION}")
    print(f"  range:                       {ALPACA_BACKFILL_START}->{ALPACA_BACKFILL_END}")
    print(f"  source semantics:            feed={cfg.feed} adjustment={cfg.adjustment} asof={cfg.asof} timeframe={cfg.timeframe}")
    print(f"  paging:                      limit={cfg.page_limit} symbol_batch_size={cfg.symbol_batch_size}")
    print(f"  request safety cap:          {cfg.requests_per_minute}/min")
    print(f"  canonical writes enabled:    {ALPACA_BACKFILL_CANONICAL_WRITE_ENABLED}")
    print(f"  gates locked:                {len(ALPACA_BACKFILL_GATES)}")
    print("  checks:")
    for name, passed in checks.items():
        print(f"    {name}: {passed}")
    if not all(checks.values()):
        raise SystemExit("Historical Backfill Gate 1: FAIL")
    print("  Historical Backfill Gate 1 acquisition/storage contract: PASS")
    print("  Historical Backfill Gate 2 historical symbol inventory: CURRENT; target-machine inventory not yet materialized")


if __name__ == "__main__":
    main()
