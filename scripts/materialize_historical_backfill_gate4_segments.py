from __future__ import annotations

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_identity_segments_policy import (
    AlpacaBackfillIdentitySegmentPolicyBuilder,
)


def main() -> None:
    settings = load_settings()
    report = AlpacaBackfillIdentitySegmentPolicyBuilder(settings).run()

    print("ATLAS Historical Backfill Gate 4 Identity Chain Materialization")
    print("  safety: derived identity metadata only; canonical history untouched")
    print(f"  contract:                     {report.contract_version}")
    print(f"  parent segment contract:      {report.parent_segment_contract_version}")
    print(f"  identity policy parent:       {report.identity_policy_contract_version}")
    print(f"  observed symbols:             {report.observed_symbols:,}")
    print(f"  safe candidate rows:          {report.safe_candidate_rows:,}")
    print(f"  input unique safe edges:      {report.input_unique_safe_edges:,}")
    print(f"  duplicate safe evidence rows: {report.duplicate_safe_candidate_rows:,}")
    print(f"  quarantined safe rows:        {report.quarantined_safe_candidate_rows:,}")
    print(f"  quarantined unique edges:     {report.quarantined_unique_safe_edges:,}")
    print(f"  CUSIP-ambiguous symbols:      {report.cusip_ambiguous_symbols:,}")
    print(f"  identity-eligible safe edges: {report.identity_eligible_safe_edges:,}")
    print(f"  identity chains:              {report.identity_chains:,}")
    print(f"  identity segments:            {report.identity_segments:,}")
    print(f"  singleton chains:             {report.singleton_chains:,}")
    print(f"  multi-symbol chains:          {report.multi_symbol_chains:,}")
    print(f"  max chain length:             {report.max_chain_length:,}")
    print(f"  expected chain count:         {report.expected_chain_count:,}")
    print("  validation:")
    print(f"    edge/component accounting:  {report.edge_component_accounting}")
    print(f"    chain coverage exact:       {report.chain_coverage_exact}")
    print(
        f"    eligible edges consumed:    {report.eligible_safe_edges_consumed_exact}"
    )
    print(f"    quarantine accounting:      {report.quarantine_accounting_exact}")
    print(f"  eligible safe edges:          {report.safe_edge_path}")
    print(f"  quarantined safe edges:       {report.quarantined_safe_edge_path}")
    print(f"  ambiguous symbols:            {report.ambiguous_symbol_path}")
    print(f"  chains:                       {report.chain_path}")
    print(f"  segments:                     {report.segment_path}")
    print(f"  report:                       {report.report_path}")
    print("  canonical data modified:      False")
    print("  Historical Backfill Gate 4 corporate action / identity segmentation: CURRENT")


if __name__ == "__main__":
    main()
