from __future__ import annotations

import argparse
import json

from packages.backtesting.literature_momseason_lit02_source_metadata_repair_v2_certified import (
    LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION,
)
from packages.backtesting.literature_momseason_lit02_source_metadata_repair_v3 import (
    LIT02_SOURCE_METADATA_REPAIR_V3_CONTRACT,
    lit02_repair_v3_source_expansion_fingerprint,
)
from packages.backtesting.literature_momseason_lit02_source_metadata_repair_v3_certified import (
    LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION,
)
from packages.backtesting.literature_momseason_lit02_source_metadata_repair_v3_freeze import (
    LIT02_SOURCE_METADATA_REPAIR_V3_FREEZE_CONTRACT,
    MomSeasonLIT02SourceMetadataRepairV3Frozen,
    lit02_repair_v3_freeze_fingerprint,
)
from packages.core.settings import load_settings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Retry only the accepted LIT-02 repair-v2 source-unresolved cases against the "
            "prospectively frozen official-SEC final transaction amendment forms. The frozen "
            "return paths are unchanged; a certified v3 wrapper adds only explicit executed-event "
            "to explicit defined-term linkage. No market-price/return outcomes are read."
        )
    )
    parser.add_argument(
        "--acquire",
        action="store_true",
        help="Explicitly permit official source/identity/transaction metadata reads for repair-v3.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild repair-v3 checkpoints instead of reusing valid repair-v3 manifests.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.acquire:
        print("ATLAS LIT-02 source metadata repair-v3 NOT STARTED.")
        print("Re-run with --acquire to permit official source-metadata reads.")
        print("Market-price/return outcomes and the protected holdout remain disabled.")
        return 2

    print(
        "[LIT-02][REPAIR-V3] "
        f"contract={LIT02_SOURCE_METADATA_REPAIR_V3_CONTRACT} | "
        f"freeze_contract={LIT02_SOURCE_METADATA_REPAIR_V3_FREEZE_CONTRACT} | "
        f"freeze={lit02_repair_v3_freeze_fingerprint()} | "
        f"source_expansion={lit02_repair_v3_source_expansion_fingerprint()} | "
        f"base_parser={LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION} | "
        f"v3_parser={LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION} | "
        "repair-v2 resolved cases are immutable/reused; only repair-v2 unresolved cases are retried"
    )
    report = MomSeasonLIT02SourceMetadataRepairV3Frozen(load_settings()).run(force=args.force)

    print("ATLAS Literature-Anchored Alpha Exploration — LIT-02 Source Metadata Repair v3")
    print(f"  status:                              {report['status']}")
    print(f"  repair-v3 freeze fingerprint:        {report['repair_v3_freeze_fingerprint']}")
    print(f"  source expansion fingerprint:        {report['source_expansion_fingerprint']}")
    print(f"  base parser certification:           {LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION}")
    print(f"  v3 parser certification:             {report['repair_v3_parser_certification']}")
    print(f"  feasibility cases:                   {report['feasibility_cases']}")
    print(f"  base resolved cases:                 {report['base_resolved_cases']}")
    print(f"  base unresolved cases:               {report['base_unresolved_cases']}")
    print(f"  resolved cases after repair-v3:      {report['resolved_cases']}")
    print(f"  newly resolved cases:                {report['newly_resolved_cases']}")
    print(f"  unresolved cases after repair-v3:    {report['unresolved_cases']}")
    print(f"  source coverage:                     {float(report['source_coverage']) * 100:.2f}%")
    print(f"  required source coverage:            {float(report['required_source_coverage']) * 100:.0f}%")
    print(f"  path counts:                         {json.dumps(report['path_counts'], sort_keys=True)}")
    print(
        "  unresolved reason counts:            "
        f"{json.dumps(report['unresolved_reason_counts'], sort_keys=True)}"
    )
    print(f"  SEC lookback days:                   {report['repair_v3_sec_lookback_days']}")
    print(f"  SEC allowed added forms:             {json.dumps(report['repair_v3_sec_allowed_forms'])}")
    print(f"  source metadata provider reads:      {report['source_metadata_provider_reads']}")
    print(f"    Massive metadata reads:            {report['massive_source_metadata_reads']}")
    print(f"    SEC metadata reads:                {report['sec_source_metadata_reads']}")
    print(f"  repair-v3 cached cases reused:       {report['cached_case_manifests_reused']}")
    print(f"  repair-v2 resolved cases reused:     {report['v2_resolved_cases_reused']}")
    print(f"  repair-v2 unresolved cases retried:  {report['v2_unresolved_cases_retried']}")
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
