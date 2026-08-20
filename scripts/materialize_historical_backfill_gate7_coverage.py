from __future__ import annotations

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_seam_coverage import (
    ALPACA_BACKFILL_SEAM_COVERAGE_CONTRACT_VERSION,
    AlpacaBackfillSeamCoverageAudit,
)


def main() -> None:
    report = AlpacaBackfillSeamCoverageAudit(load_settings()).run()

    print("ATLAS Historical Backfill Gate 7-C Massive Coverage Horizon Audit")
    print("  safety: local derived evidence only; candidate/production canonical untouched")
    print(f"  contract:                           {ALPACA_BACKFILL_SEAM_COVERAGE_CONTRACT_VERSION}")
    print(f"  source fingerprint:                 {report['source_fingerprint']}")
    print(f"  Gate 7-B fingerprint:               {report['gate7b_source_fingerprint']}")
    print(f"  seam session:                       {report['seam_session']}")
    print("  Massive horizon:")
    print(f"    sessions:                          {report['horizon_session_count']}")
    print(f"    first:                             {report['horizon_first_session']}")
    print(f"    last:                              {report['horizon_last_session']}")
    print("  discontinuity population:")
    print(f"    symbols:                           {report['target_discontinuity_symbols']:,} / {report['expected_discontinuity_symbols']:,}")
    print(f"    Massive coverage resumes:          {report['massive_coverage_resumes_within_horizon']:,}")
    print(f"    no Massive bar in horizon:         {report['massive_no_bar_within_horizon']:,}")
    print(f"    appears on locked seam session:    {report['targets_appearing_on_locked_seam_session']:,}")
    print("  Massive reference status:")
    print(f"    unique identity:                    {report['massive_reference_unique_symbols']:,}")
    print(f"    absent:                             {report['massive_reference_absent_symbols']:,}")
    print(f"    ambiguous exact ticker:             {report['massive_reference_ambiguous_symbols']:,}")
    print("  coverage classes:")
    for key, value in report["coverage_class_counts"].items():
        print(f"    {key}: {value:,}")
    print("  first Massive bar dates within horizon:")
    for key, value in report["first_massive_session_counts"].items():
        print(f"    {key}: {value:,}")
    print("  unique-reference exchanges:")
    for key, value in report["unique_reference_exchange_counts"].items():
        print(f"    {key}: {value:,}")
    print("  unique-reference security types:")
    for key, value in report["unique_reference_security_type_counts"].items():
        print(f"    {key}: {value:,}")
    print(f"  promotion policy:                   {report['promotion_policy']}")
    print("  structural checks:")
    for key, value in report["structural_checks"].items():
        print(f"    {key}: {value}")
    print(f"  detail:                             {report['detail_path']}")
    print(f"  report:                             {report['report_path']}")
    print(f"  canonical data modified:            {report['canonical_data_modified']}")

    if report.get("structural_pass") is not True:
        raise SystemExit("Historical Backfill Gate 7-C Massive coverage horizon audit: FAIL")
    print("  Historical Backfill Gate 7-C Massive coverage horizon audit: PASS")
    print("  Historical Backfill Gate 7 Massive seam reconciliation: CURRENT")


if __name__ == "__main__":
    main()
