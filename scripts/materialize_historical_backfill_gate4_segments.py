from __future__ import annotations

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_identity_segments import AlpacaBackfillIdentitySegmentBuilder


def main() -> None:
    settings = load_settings()
    report = AlpacaBackfillIdentitySegmentBuilder(settings).run()

    print("ATLAS Historical Backfill Gate 4 Identity Chain Materialization")
    print("  safety: derived identity metadata only; canonical history untouched")
    print(f"  contract:                     {report.contract_version}")
    print(f"  identity policy parent:       {report.identity_policy_contract_version}")
    print(f"  observed symbols:             {report.observed_symbols:,}")
    print(f"  safe candidate rows:          {report.safe_candidate_rows:,}")
    print(f"  unique safe edges:            {report.unique_safe_edges:,}")
    print(f"  duplicate safe evidence rows: {report.duplicate_safe_candidate_rows:,}")
    print(f"  identity chains:              {report.identity_chains:,}")
    print(f"  identity segments:            {report.identity_segments:,}")
    print(f"  singleton chains:             {report.singleton_chains:,}")
    print(f"  multi-symbol chains:          {report.multi_symbol_chains:,}")
    print(f"  max chain length:             {report.max_chain_length:,}")
    print(f"  expected chain count:         {report.expected_chain_count:,}")
    print("  validation:")
    print(f"    edge/component accounting:  {report.edge_component_accounting}")
    print(f"    chain coverage exact:       {report.chain_coverage_exact}")
    print(f"    safe edges consumed exact:  {report.safe_edges_consumed_exact}")
    print(f"  safe edges:                   {report.safe_edge_path}")
    print(f"  chains:                       {report.chain_path}")
    print(f"  segments:                     {report.segment_path}")
    print(f"  report:                       {report.report_path}")
    print("  canonical data modified:      False")
    print("  Historical Backfill Gate 4 corporate action / identity segmentation: CURRENT")


if __name__ == "__main__":
    main()
