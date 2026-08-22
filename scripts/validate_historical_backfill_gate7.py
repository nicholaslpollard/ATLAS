from __future__ import annotations

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_seam_final import AlpacaBackfillSeamFinalValidator


def main() -> None:
    settings = load_settings()
    report = AlpacaBackfillSeamFinalValidator(settings).run()

    print("ATLAS Historical Backfill Gate 7 Final Validation")
    print("  safety: derived seam decision map only; candidate/production canonical untouched")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  Gate 7-A fingerprint:             {report['gate7a_source_fingerprint']}")
    print(f"  Gate 7-B fingerprint:             {report['gate7b_source_fingerprint']}")
    print(f"  Gate 7-C fingerprint:             {report['gate7c_source_fingerprint']}")
    print("  boundary decision accounting:")
    print(f"    boundary symbols:                {report['boundary_symbols']:,}")
    print(f"    candidate Friday symbols:        {report['candidate_friday_symbols']:,}")
    for name, value in report["decision_counts"].items():
        print(f"    {name}: {int(value):,}")
    print("  Friday candidate decisions:")
    for name, value in report["friday_decision_counts"].items():
        print(f"    {name}: {int(value):,}")
    print("  seam policy evidence:")
    print(f"    safe exact-literal bridges:      {report['safe_exact_literal_bridges']:,}")
    print(f"    coverage reset symbols:          {report['coverage_reset_symbols']:,}")
    print(f"    terminal pre-seam symbols:       {report['terminal_preseam_symbols']:,}")
    print(f"    quarantined seam symbols:        {report['quarantined_seam_symbols']:,}")
    print(f"    post-seam-only symbols:          {report['postseam_only_symbols']:,}")
    print(f"    safe cross-ticker rename edges:  {report['safe_cross_ticker_rename_edges']:,}")
    print(f"    provider price bridge compatible:{report['provider_price_bridge_compatible']}")
    print(f"    coverage reset policy:           {report['coverage_reset_policy']}")
    print("  checks:")
    for name, value in report["checks"].items():
        print(f"    {name}: {value}")
    print(f"  promotion decisions:               {report['decision_path']}")
    print(f"  report:                            {report['report_path']}")
    print(f"  canonical data modified:           {report['canonical_data_modified']}")

    if report["gate7_pass"]:
        print("  Historical Backfill Gate 7 Massive seam reconciliation: PASS")
        print("  Historical Backfill Gate 8 canonical history promotion: CURRENT")
    else:
        print("  Historical Backfill Gate 7 Massive seam reconciliation: FAIL")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
