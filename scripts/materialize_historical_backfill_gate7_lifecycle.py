from __future__ import annotations

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_seam_lifecycle import (
    ALPACA_BACKFILL_SEAM_LIFECYCLE_CONTRACT_VERSION,
    AlpacaBackfillSeamLifecycleAudit,
)


def main() -> None:
    report = AlpacaBackfillSeamLifecycleAudit(load_settings()).run()
    print("ATLAS Historical Backfill Gate 7-B Seam Lifecycle Reconciliation")
    print("  safety: local derived evidence only; candidate/production canonical untouched")
    print(f"  contract:                         {ALPACA_BACKFILL_SEAM_LIFECYCLE_CONTRACT_VERSION}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  Gate 7-A fingerprint:             {report['gate7a_source_fingerprint']}")
    print(f"  boundary:                         {report['candidate_boundary_session']} -> {report['massive_boundary_session']}")
    print(f"  provider price bridge compatible: {report['provider_price_bridge_compatible']}")
    print("  boundary accounting:")
    print(f"    symbols:                        {report['boundary_symbols']:,} / {report['expected_boundary_symbols']:,}")
    print("  presence classes:")
    for key, value in report['presence_class_counts'].items():
        print(f"    {key}: {value:,}")
    print("  identity classes:")
    for key, value in report['identity_status_counts'].items():
        print(f"    {key}: {value:,}")
    print("  bridge evidence:")
    print(f"    safe exact-literal bridges:     {report['safe_exact_literal_bridges']:,}")
    print(f"    Massive coverage discontinuity: {report['massive_coverage_discontinuities']:,}")
    print(f"    identity review rows:           {report['identity_review_rows']:,}")
    print(f"    corporate-action events scanned:{report['corporate_action_events_scanned']:,}")
    print(f"    seam name-change evidence rows: {report['cross_seam_name_change_evidence_rows']:,}")
    print(f"    safe seam rename edges:         {report['safe_cross_seam_rename_edges']:,}")
    print(f"    rename review rows:             {report['cross_seam_rename_review_rows']:,}")
    print("  diagnostics:")
    print(f"    >=25% boundary moves:           {report['large_boundary_move_rows']:,}")
    print(f"    provider price outlier rows:    {report['same_session_provider_price_outlier_rows']:,}")
    print(f"    Massive reference present:      {report['massive_reference_snapshot_present']}")
    print(f"    Massive instrument IDs resolved:{report['massive_reference_symbols_resolved']:,}")
    print("  structural checks:")
    for key, value in report['structural_checks'].items():
        print(f"    {key}: {value}")
    print(f"  lifecycle classification:         {report['classification_path']}")
    print(f"  seam rename evidence:             {report['rename_evidence_path']}")
    print(f"  large boundary moves:             {report['large_moves_path']}")
    print(f"  provider price outliers:          {report['provider_outliers_path']}")
    print(f"  report:                           {report['report_path']}")
    print(f"  canonical data modified:          {report['canonical_data_modified']}")
    if report.get('structural_pass') is not True:
        raise SystemExit("Historical Backfill Gate 7-B seam lifecycle reconciliation: FAIL")
    print("  Historical Backfill Gate 7-B seam lifecycle reconciliation: PASS")
    print("  Historical Backfill Gate 7 Massive seam reconciliation: CURRENT")


if __name__ == '__main__':
    main()
