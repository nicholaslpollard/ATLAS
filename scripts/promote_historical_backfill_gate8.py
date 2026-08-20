from __future__ import annotations

import argparse

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_canonical_promotion import (
    ALPACA_BACKFILL_CANONICAL_PROMOTION_CONTRACT_VERSION,
    AlpacaBackfillCanonicalPromotion,
)


def _print_preflight(report: dict[str, object]) -> None:
    print("ATLAS Historical Backfill Gate 8 Canonical Promotion Preflight")
    print("  safety: preflight only; production canonical history is not written")
    print(f"  contract:                         {ALPACA_BACKFILL_CANONICAL_PROMOTION_CONTRACT_VERSION}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  Gate 6 candidate fingerprint:     {report['candidate_source_fingerprint']}")
    print(f"  Gate 7 seam fingerprint:          {report['gate7_source_fingerprint']}")
    print(f"  Gate 7 decision SHA256:           {report['gate7_decision_sha256']}")
    print("  candidate promotion inventory:")
    print(f"    rows:                           {int(report['candidate_rows']):,}")
    print(f"    sessions:                       {int(report['candidate_sessions']):,}")
    print(f"    symbols:                        {int(report['candidate_symbols']):,}")
    print(f"    first session:                  {report['candidate_first_session']}")
    print(f"    last session:                   {report['candidate_last_session']}")
    print(f"    preexisting exact sessions:     {int(report['preexisting_exact_candidate_sessions']):,}")
    print(f"    collision mismatches:           {len(report['collision_mismatch_sessions']):,}")
    print(f"    unexpected target sessions:     {len(report['unexpected_target_sessions']):,}")
    print("  protected Massive baseline:")
    print(f"    sessions:                       {int(report['massive_baseline_sessions']):,}")
    print(f"    rows:                           {int(report['massive_baseline_rows']):,}")
    print(f"    first session:                  {report['massive_baseline_first_session']}")
    print(f"    last session:                   {report['massive_baseline_last_session']}")
    print(f"    schema exact:                   {report['massive_baseline_schema_exact']}")
    print(f"    semantic mismatches:            {int(report['massive_baseline_semantic_mismatches']):,}")
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  production writes this run:       {int(report['production_writes']):,}")
    print(f"  preflight report:                 {report['preflight_report_path']}")
    print(f"  promotion manifest:               {report['promotion_manifest_path']}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 8 canonical promotion preflight: FAIL")
    print("  Historical Backfill Gate 8 canonical promotion preflight: PASS")
    print("  Gate 8 production write: NOT YET APPLIED")


def _print_apply(report: dict[str, object]) -> None:
    print("ATLAS Historical Backfill Gate 8 Canonical Promotion")
    print("  safety: accepted pre-seam Alpaca daily history only; Massive era protected by SHA baseline")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print("  promotion results:")
    print(f"    copied sessions this run:       {int(report['copied_sessions']):,}")
    print(f"    reused exact sessions:          {int(report['reused_exact_sessions']):,}")
    print(f"    promoted rows:                  {int(report['promoted_rows']):,}")
    print(f"    promoted sessions:              {int(report['promoted_sessions']):,}")
    print(f"    promoted symbols:               {int(report['promoted_symbols']):,}")
    print(f"    first session:                  {report['first_session']}")
    print(f"    last session:                   {report['last_session']}")
    print(f"    duplicate keys:                 {int(report['duplicate_keys']):,}")
    print(f"    semantic mismatches:            {int(report['semantic_mismatches']):,}")
    print("  final checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  manifest:                         {report['promotion_manifest_path']}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 8 canonical history promotion: FAIL")
    print("  Historical Backfill Gate 8 canonical history promotion: PASS")
    print("  Historical Backfill Gate 9 feature replay from 2016: CURRENT")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Preflight or apply Historical Backfill Gate 8 promotion into production canonical 1d history."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Perform the production canonical write after re-running the full Gate 8 preflight. "
            "Without this flag the command is read-only with respect to production canonical history."
        ),
    )
    args = parser.parse_args()

    promotion = AlpacaBackfillCanonicalPromotion(load_settings())
    if args.apply:
        _print_apply(promotion.apply())
    else:
        _print_preflight(promotion.preflight())


if __name__ == "__main__":
    main()
