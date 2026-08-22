from __future__ import annotations

import argparse

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_candidate_canonical import (
    AlpacaBackfillCandidateCanonicalBuilder,
    AlpacaBackfillCandidateCanonicalValidator,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and validate Historical Backfill Gate 6 candidate canonical history."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild all isolated candidate year partitions even when fingerprints match.",
    )
    args = parser.parse_args()

    settings = load_settings()
    builder = AlpacaBackfillCandidateCanonicalBuilder(settings)
    report = builder.run(force=args.force)
    validation = AlpacaBackfillCandidateCanonicalValidator(settings).run()

    print("ATLAS Historical Backfill Gate 6 Candidate Canonical Validation")
    print("  safety: isolated derived candidate only; production canonical history untouched")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  production schema contract:       {report['production_materialization_contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  validated-evidence fingerprint:   {report['validated_evidence_source_fingerprint']}")
    print(f"  candidate role:                   {report['candidate_role']}")
    print(f"  provider/feed:                    {report['provider']} / {report['feed']}")
    print(f"  timeframe/dataset:                {report['timeframe']} / {report['dataset']}")
    print(f"  adjustment/asof:                  {report['adjustment']} / {report['asof']}")
    print(f"  candidate rows:                   {report['candidate_rows']:,}")
    print(f"  expected trade-backed rows:       {report['expected_trade_backed_rows']:,}")
    print(f"  excluded zero-activity rows:      {report['excluded_zero_activity_placeholder_rows']:,}")
    print(f"  candidate sessions:               {report['candidate_sessions']:,}")
    print(f"  expected XNYS sessions:           {report['expected_exchange_sessions']:,}")
    print(f"  exact provider symbols:           {report['observed_symbols']:,}")
    print(f"  rebuilt years this run:           {report['rebuilt_years']}")
    print("  identity sidecars:")
    identity = report["identity"]
    print(f"    segments:                       {identity['identity_segments']:,}")
    print(f"    chains:                         {identity['identity_chains']:,}")
    print(f"    CUSIP-ambiguous symbols:        {identity['identity_ambiguous_symbols']:,}")
    print(f"    segment candidate rows:         {identity['identity_segment_candidate_rows']:,}")
    print(f"    chain candidate rows:           {identity['identity_chain_candidate_rows']:,}")
    print("  year partitions:")
    for item in report["year_manifests"]:
        print(
            f"    {item['year']}: rows={int(item['rows']):,} "
            f"sessions={int(item['session_count']):,} symbols={int(item['symbols']):,}"
        )
    print("  validation counts:")
    for key, value in validation["counts"].items():
        if isinstance(value, int) and not isinstance(value, bool):
            print(f"    {key}: {value:,}")
        else:
            print(f"    {key}: {value}")
    print("  checks:")
    for key, value in validation["checks"].items():
        print(f"    {key}: {value}")
    print(f"  candidate root:                   {report['candidate_root']}")
    print(f"  production canonical root:        {report['production_canonical_root']}")
    print(f"  canonical data modified:          {report['canonical_data_modified']}")

    if validation.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 6 candidate canonical materialization: FAIL")
    print("  Historical Backfill Gate 6 candidate canonical materialization: PASS")
    print("  Historical Backfill Gate 7 Massive seam reconciliation: CURRENT")


if __name__ == "__main__":
    main()
