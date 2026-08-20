from __future__ import annotations

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_identity_asset_risk import (
    AlpacaBackfillIdentityAssetRiskBuilder,
)


def main() -> None:
    settings = load_settings()
    report = AlpacaBackfillIdentityAssetRiskBuilder(settings).run()

    print("ATLAS Historical Backfill Gate 4 Asset-ID Reference Risk Materialization")
    print("  safety: retained current asset discovery evidence only; no provider fetch")
    print(f"  contract:                         {report.contract_version}")
    print(f"  parent segment policy:            {report.parent_segment_policy_contract_version}")
    print(f"  asset state role:                 {report.asset_state_role}")
    print(f"  historical identity effect:       {report.historical_identity_effect}")
    print(f"  retained asset payloads:          {report.raw_asset_payloads:,}")
    print(f"  raw asset rows:                   {report.raw_asset_rows:,}")
    print(f"  raw exact symbols:                {report.raw_exact_symbols:,}")
    print(f"  distinct symbol/asset-id pairs:   {report.distinct_symbol_asset_id_pairs:,}")
    print(f"  symbols with >1 asset ID:         {report.symbols_with_multiple_asset_ids:,}")
    print(f"  observed symbols with >1 asset ID:{report.observed_symbols_with_multiple_asset_ids:>10,}")
    print(f"  touching eligible continuity:     {report.reuse_touching_eligible_edge:,}")
    print(f"  touching existing quarantine:     {report.reuse_touching_quarantined_edge:,}")
    print(f"  inside multi-symbol chain:        {report.reuse_in_multi_symbol_chain:,}")
    print(f"  reference rows:                   {report.reference_rows:,}")
    print(f"  segment reference annotations:    {report.segment_reference_annotations:,}")
    print(f"  chain reference annotations:      {report.chain_reference_annotations:,}")
    print(f"  parent identity chains:           {report.parent_identity_chains:,}")
    print(f"  resulting identity chains:        {report.resulting_identity_chains:,}")
    print(f"  parent identity segments:         {report.parent_identity_segments:,}")
    print(f"  resulting identity segments:      {report.resulting_identity_segments:,}")
    print("  validation:")
    print(f"    historical chain unchanged:     {report.historical_chain_structure_unchanged}")
    print(f"    reference-only/non-segmenting:  {report.reference_policy_is_non_segmenting}")
    print(f"  reference artifact:               {report.reference_artifact_path}")
    print(f"  chains:                           {report.chain_path}")
    print(f"  segments:                         {report.segment_path}")
    print(f"  report:                           {report.report_path}")
    print("  canonical data modified:          False")
    print("  Historical Backfill Gate 4 corporate action / identity segmentation: CURRENT")


if __name__ == "__main__":
    main()
