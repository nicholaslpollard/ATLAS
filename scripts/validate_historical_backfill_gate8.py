from __future__ import annotations

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_canonical_promotion_validation import (
    AlpacaBackfillCanonicalPromotionValidator,
    GATE8_REVALIDATION_CONTRACT_VERSION,
)


def main() -> None:
    report = AlpacaBackfillCanonicalPromotionValidator(load_settings()).run()
    print("ATLAS Historical Backfill Gate 8 Independent Canonical Revalidation")
    print("  safety: read-only proof over current candidate, production canonical, and frozen Massive baseline")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  revalidation contract:            {GATE8_REVALIDATION_CONTRACT_VERSION}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  Gate 6 candidate fingerprint:     {report['candidate_source_fingerprint']}")
    print(f"  Gate 7 seam fingerprint:          {report['gate7_source_fingerprint']}")
    print("  current production evidence:")
    print(f"    rows:                           {int(report['promoted_rows']):,}")
    print(f"    sessions:                       {int(report['promoted_sessions']):,}")
    print(f"    symbols:                        {int(report['promoted_symbols']):,}")
    print(f"    first session:                  {report['first_session']}")
    print(f"    last session:                   {report['last_session']}")
    print(f"    duplicate keys:                 {int(report['duplicate_keys']):,}")
    print(f"    semantic mismatches:            {int(report['semantic_mismatches']):,}")
    print("  independently recomputed checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  promotion manifest:               {report['promotion_manifest_path']}")
    print(f"  preflight report:                 {report['preflight_report_path']}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 8 independent canonical revalidation: FAIL")
    print("  Historical Backfill Gate 8 independent canonical revalidation: PASS")
    print("  Historical Backfill Gate 9 feature replay from 2016: CURRENT")


if __name__ == "__main__":
    main()
