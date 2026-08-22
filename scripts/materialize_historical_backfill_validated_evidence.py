from __future__ import annotations

import argparse

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_validated_evidence import (
    AlpacaBackfillValidatedEvidenceBuilder,
    AlpacaBackfillValidatedEvidenceValidator,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build/resume and validate the ATLAS historical validated-evidence cache."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild every year even when fingerprints and Parquet hashes match.",
    )
    args = parser.parse_args()

    settings = load_settings()
    report = AlpacaBackfillValidatedEvidenceBuilder(settings).run(force=args.force)
    validation = AlpacaBackfillValidatedEvidenceValidator(settings).run()

    print("ATLAS Historical Backfill Validated Evidence Performance Checkpoint")
    print("  safety: derived evidence only; raw provider files immutable; canonical history untouched")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  cache role:                       {report['cache_role']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print("  resume policy:                    reuse year only when source fingerprint + Parquet SHA match")
    print(f"  retained unit manifests:          {int(report['retained_unit_manifests']):,}")
    print(f"  retained raw bar pages:           {int(report['retained_raw_bar_pages']):,}")
    print(f"  raw payload hash failures:        {int(report['raw_payload_hash_failures']):,}")
    print(f"  identity-safe evidence rows:      {int(report['identity_safe_rows']):,}")
    print(f"  trade-backed rows:                {int(report['trade_backed_rows']):,}")
    print(f"  zero-activity placeholder rows:   {int(report['zero_activity_placeholder_rows']):,}")
    print(f"  quarantined response rows:        {int(report['quarantined_response_rows']):,}")
    print(f"  observed exact symbols:           {int(report['observed_symbols']):,}")
    print("  year partitions:")
    for partition in report["partitions"]:
        print(
            f"    {int(partition['year'])}: rows={int(partition['rows']):,} "
            f"trade={int(partition['trade_backed_rows']):,} "
            f"placeholder={int(partition['zero_activity_placeholder_rows']):,} "
            f"sha={str(partition['parquet_sha256'])[:16]}..."
        )
    print("  materialization accounting:")
    print(f"    row accounting exact:           {report['row_accounting_exact']}")
    print(f"    classification accounting:      {report['classification_accounting_exact']}")
    print("  fast cache validation:")
    for name, value in validation["checks"].items():
        print(f"    {name}: {value}")
    counts = validation["counts"]
    print("  fast-query counts:")
    print(f"    rows:                            {int(counts['rows']):,}")
    print(f"    trade-backed:                    {int(counts['trade']):,}")
    print(f"    zero-activity placeholders:      {int(counts['placeholder']):,}")
    print(f"    exact symbols:                   {int(counts['symbols']):,}")
    print(f"    duplicate symbol/session keys:   {int(counts['duplicates']):,}")
    print(f"    unknown bar classes:             {int(counts['unknown_classes']):,}")
    print(f"  cache manifest:                    {report['report_path']}")
    print(f"  canonical data modified:           {report['canonical_data_modified']}")
    if validation["pass"] is not True:
        raise SystemExit("Historical validated-evidence performance checkpoint: FAIL")
    print("  Historical validated-evidence performance checkpoint: PASS")
    print("  Historical Backfill Gate 5 provider completeness / quality: CURRENT")


if __name__ == "__main__":
    main()
