from __future__ import annotations

import argparse
import json

from packages.backtesting.literature_momseason_lit02_source_metadata_transport import (
    LIT02_SOURCE_METADATA_TRANSPORT_VERSION,
    MomSeasonLIT02SourceMetadataTransportSafe,
)
from packages.core.settings import load_settings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Acquire source-only Massive/SEC metadata for the frozen 199-case LIT-02 "
            "delisting-aware feasibility plan. No market-price/return outcomes are read."
        )
    )
    parser.add_argument(
        "--acquire",
        action="store_true",
        help="Explicitly permit source-metadata provider reads for the frozen feasibility cases.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild case classifications instead of reusing valid per-case checkpoints.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.acquire:
        print("ATLAS LIT-02 source metadata acquisition NOT STARTED.")
        print("Re-run with --acquire to permit source/identity/transaction metadata reads.")
        print("Market-price/return outcomes and the protected holdout remain disabled.")
        return 2

    print(
        "[LIT-02][TRANSPORT] "
        f"{LIT02_SOURCE_METADATA_TRANSPORT_VERSION} | Massive ticker-event HTTP 404 "
        "continues as source-unavailable evidence; other provider failures remain fatal"
    )
    report = MomSeasonLIT02SourceMetadataTransportSafe(load_settings()).run(force=args.force)
    print("ATLAS Literature-Anchored Alpha Exploration — LIT-02 Source Metadata")
    print(f"  status:                              {report['status']}")
    print(f"  feasibility cases:                   {report['feasibility_cases']}")
    print(f"  resolved cases:                      {report['resolved_cases']}")
    print(f"  unresolved cases:                    {report['unresolved_cases']}")
    print(f"  source coverage:                     {float(report['source_coverage']) * 100:.2f}%")
    print(f"  required source coverage:            {float(report['required_source_coverage']) * 100:.0f}%")
    print(f"  path counts:                         {json.dumps(report['path_counts'], sort_keys=True)}")
    print(
        "  unresolved reason counts:            "
        f"{json.dumps(report['unresolved_reason_counts'], sort_keys=True)}"
    )
    print(f"  source metadata provider reads:      {report['source_metadata_provider_reads']}")
    print(f"    Massive metadata reads:            {report['massive_source_metadata_reads']}")
    print(f"    SEC metadata reads:                {report['sec_source_metadata_reads']}")
    print(f"  cached case manifests reused:        {report['cached_case_manifests_reused']}")
    print(f"  economic outcome values read:        {report['economic_outcome_values_read']}")
    print(f"  new price/return provider reads:      {report['new_price_or_return_provider_reads']}")
    print(f"  protected return rows read:           {report['protected_return_rows_read']}")
    print(f"  protected holdout consumed:           {report['protected_holdout_consumed']}")
    print(f"  LIT-02 economic design unblocked:     {report['lit02_economic_design_unblocked']}")
    print(f"  Phase33 signal-to-trade authority:    {report['phase33_signal_to_trade_authority']}")
    print(f"  classification fingerprint:          {report['classification_fingerprint']}")
    print(f"  report fingerprint:                  {report['report_fingerprint']}")
    print(f"  next action:                          {report['next_action']}")
    print(f"  report:                               {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
