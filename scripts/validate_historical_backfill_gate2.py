from __future__ import annotations

import json
from pathlib import Path

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_inventory import ALPACA_BACKFILL_INVENTORY_CONTRACT_VERSION
from packages.data.alpaca_backfill_policy import (
    ALPACA_BACKFILL_ADJUSTMENT,
    ALPACA_BACKFILL_ASOF,
    ALPACA_BACKFILL_CONTRACT_VERSION,
    ALPACA_BACKFILL_FEED,
    ALPACA_BACKFILL_TIMEFRAME,
    validate_backfill_contract,
)


def main() -> None:
    settings = load_settings()
    validate_backfill_contract()
    report_path = (
        settings.resolved_path(settings.data.paths.derived)
        / "historical_backfill"
        / "alpaca"
        / "inventory"
        / "inventory_report.json"
    )

    print("ATLAS Historical Backfill Gate 2 Validation")
    print(f"  parent contract:             {ALPACA_BACKFILL_CONTRACT_VERSION}")
    print("  Historical Backfill Gate 1 acquisition/storage contract: PASS")

    if not report_path.is_file():
        print("  Historical Backfill Gate 2 historical symbol inventory: CURRENT; target-machine inventory not yet materialized")
        return

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    inventory_path = Path(str(payload.get("inventory_path", "")))
    source_counts = payload.get("source_counts") or {}
    checks = {
        "inventory_contract": payload.get("contract_version") == ALPACA_BACKFILL_INVENTORY_CONTRACT_VERSION,
        "parent_contract": payload.get("parent_contract_version") == ALPACA_BACKFILL_CONTRACT_VERSION,
        "canonical_untouched": payload.get("canonical_data_modified") is False,
        "sip_raw_literal_daily": (
            payload.get("feed") == ALPACA_BACKFILL_FEED
            and payload.get("adjustment") == ALPACA_BACKFILL_ADJUSTMENT
            and payload.get("asof") == ALPACA_BACKFILL_ASOF
            and payload.get("timeframe") == ALPACA_BACKFILL_TIMEFRAME
        ),
        "active_discovery_present": int(source_counts.get("active_asset_symbols", 0)) > 0,
        "inactive_discovery_present": int(source_counts.get("inactive_asset_symbols", 0)) > 0,
        "massive_observed_discovery_present": int(source_counts.get("massive_observed_symbols", 0)) > 0,
        "corporate_action_discovery_present": int(source_counts.get("corporate_action_symbols", 0)) > 0,
        "inventory_nonempty": int(payload.get("inventory_rows", 0)) > 0,
        "sip_candidates_nonempty": int(payload.get("sip_candidate_symbols", 0)) > 0,
        "otc_only_evidence_retained_but_excluded": int(payload.get("known_otc_only_excluded", 0)) > 0,
        "inactive_reference_identifiers_retained_but_excluded": int(payload.get("inactive_reference_only_identifier_excluded", 0)) > 0,
        "corporate_action_pagination_completed": int(payload.get("corporate_action_pages", 0)) > 0,
        "raw_payloads_persisted": int(payload.get("raw_discovery_payloads", 0)) >= 4,
        "pilot_requested_100_symbols": int(payload.get("pilot_symbols", 0)) == 100,
        "pilot_observed_history": int(payload.get("pilot_observed_symbols", 0)) > 0 and int(payload.get("pilot_bar_rows", 0)) > 0,
        "pilot_paginated": int(payload.get("pilot_pages", 0)) > 0,
        "inventory_artifact_present": inventory_path.is_file(),
    }

    print(f"  report:                      {report_path}")
    print(f"  inventory rows:              {int(payload.get('inventory_rows', 0)):,}")
    print(f"  SIP acquisition candidates: {int(payload.get('sip_candidate_symbols', 0)):,}")
    print(f"  known OTC-only excluded:     {int(payload.get('known_otc_only_excluded', 0)):,}")
    print(f"  inactive reference-only:     {int(payload.get('inactive_reference_only_identifier_excluded', 0)):,} excluded from SIP")
    print(f"  pilot:                       symbols={int(payload.get('pilot_symbols', 0)):,} observed={int(payload.get('pilot_observed_symbols', 0)):,} bars={int(payload.get('pilot_bar_rows', 0)):,}")
    print("  checks:")
    for name, passed in checks.items():
        print(f"    {name}: {passed}")

    if not all(checks.values()):
        raise SystemExit("Historical Backfill Gate 2: FAIL")

    print("  Historical Backfill Gate 2 historical symbol inventory: PASS")
    print("  Historical Backfill Gate 3 raw historical acquisition: CURRENT; full acquisition not yet started")


if __name__ == "__main__":
    main()
