from __future__ import annotations

import json
import math
from pathlib import Path

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_acquisition import (
    ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION,
)
from packages.data.alpaca_backfill_inventory import ALPACA_BACKFILL_INVENTORY_CONTRACT_VERSION
from packages.data.alpaca_backfill_policy import (
    ALPACA_BACKFILL_ADJUSTMENT,
    ALPACA_BACKFILL_ASOF,
    ALPACA_BACKFILL_CONTRACT_VERSION,
    ALPACA_BACKFILL_END,
    ALPACA_BACKFILL_FEED,
    ALPACA_BACKFILL_PAGE_LIMIT,
    ALPACA_BACKFILL_REQUESTS_PER_MINUTE,
    ALPACA_BACKFILL_START,
    ALPACA_BACKFILL_SYMBOL_BATCH_SIZE,
    ALPACA_BACKFILL_TIMEFRAME,
    validate_backfill_contract,
)


def main() -> None:
    settings = load_settings()
    validate_backfill_contract()
    root = settings.resolved_path(settings.data.paths.derived) / "historical_backfill" / "alpaca"
    inventory_report_path = root / "inventory" / "inventory_report.json"
    report_path = root / "acquisition" / "acquisition_report.json"

    print("ATLAS Historical Backfill Gate 3 Validation")
    print(f"  parent contract:             {ALPACA_BACKFILL_CONTRACT_VERSION}")
    print("  Historical Backfill Gate 1 acquisition/storage contract: PASS")
    print("  Historical Backfill Gate 2 historical symbol inventory: PASS")

    if not report_path.is_file():
        print("  Historical Backfill Gate 3 raw historical acquisition: CURRENT; target-machine full acquisition not yet materialized")
        return
    if not inventory_report_path.is_file():
        raise SystemExit("Historical Backfill Gate 3: FAIL; Gate 2 inventory report is missing")

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    inventory = json.loads(inventory_report_path.read_text(encoding="utf-8"))
    candidate_symbols = int(payload.get("candidate_symbols", 0))
    inventory_candidates = int(inventory.get("sip_candidate_symbols", 0))
    expected_year_partitions = ALPACA_BACKFILL_END.year - ALPACA_BACKFILL_START.year + 1
    expected_units = math.ceil(inventory_candidates / ALPACA_BACKFILL_SYMBOL_BATCH_SIZE) * expected_year_partitions
    observed_path = Path(str(payload.get("observed_summary_path", "")))
    unit_root = Path(str(payload.get("unit_manifest_root", "")))
    manifest_count = len(list(unit_root.glob("*/*.json"))) if unit_root.is_dir() else 0

    checks = {
        "acquisition_contract": payload.get("contract_version") == ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION,
        "parent_contract": payload.get("parent_contract_version") == ALPACA_BACKFILL_CONTRACT_VERSION,
        "inventory_contract": payload.get("inventory_contract_version") == ALPACA_BACKFILL_INVENTORY_CONTRACT_VERSION,
        "canonical_untouched": payload.get("canonical_data_modified") is False,
        "sip_raw_literal_daily": (
            payload.get("feed") == ALPACA_BACKFILL_FEED
            and payload.get("adjustment") == ALPACA_BACKFILL_ADJUSTMENT
            and payload.get("asof") == ALPACA_BACKFILL_ASOF
            and payload.get("timeframe") == ALPACA_BACKFILL_TIMEFRAME
        ),
        "page_limit_locked": int(payload.get("page_limit", 0)) == ALPACA_BACKFILL_PAGE_LIMIT,
        "symbol_batch_locked": int(payload.get("symbol_batch_size", 0)) == ALPACA_BACKFILL_SYMBOL_BATCH_SIZE,
        "request_rate_locked": int(payload.get("requests_per_minute", 0)) == ALPACA_BACKFILL_REQUESTS_PER_MINUTE,
        "range_locked": (
            payload.get("backfill_start") == ALPACA_BACKFILL_START.isoformat()
            and payload.get("backfill_end") == ALPACA_BACKFILL_END.isoformat()
        ),
        "candidate_count_matches_gate2": candidate_symbols == inventory_candidates and candidate_symbols > 0,
        "year_partition_count": int(payload.get("year_partitions", 0)) == expected_year_partitions,
        "planned_units_exact": int(payload.get("planned_units", 0)) == expected_units,
        "all_units_complete": (
            payload.get("complete") is True
            and int(payload.get("completed_units", 0)) == expected_units
            and int(payload.get("missing_units", -1)) == 0
        ),
        "unit_manifests_present": manifest_count == expected_units,
        "raw_payload_pages_present": int(payload.get("raw_payload_pages", 0)) >= expected_units,
        "historical_bars_observed": int(payload.get("bar_rows", 0)) > 0 and int(payload.get("observed_symbols", 0)) > 0,
        "observation_accounting": (
            int(payload.get("observed_symbols", 0)) + int(payload.get("zero_bar_symbols", 0)) == candidate_symbols
        ),
        "observed_summary_present": observed_path.is_file(),
        "inventory_fingerprint_present": len(str(payload.get("inventory_fingerprint", ""))) == 64,
    }

    print(f"  report:                      {report_path}")
    print(f"  candidates:                  {candidate_symbols:,}")
    print(f"  planned units:               {int(payload.get('planned_units', 0)):,}")
    print(f"  completed units:             {int(payload.get('completed_units', 0)):,}")
    print(f"  raw payload pages:           {int(payload.get('raw_payload_pages', 0)):,}")
    print(f"  observed symbols:            {int(payload.get('observed_symbols', 0)):,}")
    print(f"  zero-bar symbols:            {int(payload.get('zero_bar_symbols', 0)):,}")
    print(f"  bar rows:                    {int(payload.get('bar_rows', 0)):,}")
    print("  checks:")
    for name, passed in checks.items():
        print(f"    {name}: {passed}")

    if not all(checks.values()):
        raise SystemExit("Historical Backfill Gate 3: FAIL")

    print("  Historical Backfill Gate 3 raw historical acquisition: PASS")
    print("  Historical Backfill Gate 4 corporate action / identity segmentation: CURRENT")


if __name__ == "__main__":
    main()
