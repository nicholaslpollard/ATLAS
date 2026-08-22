from __future__ import annotations

from packages.core.settings import load_settings
from packages.ml.historical_backfill_structural_authority import (
    HistoricalBackfillStructuralAuthorityAudit,
)


def _pct(value: float) -> str:
    return f"{100.0 * float(value):.6f}%"


def main() -> None:
    report = HistoricalBackfillStructuralAuthorityAudit(load_settings()).run()
    reference = report["reference"]
    authority = report["authority"]
    population = report["population"]
    policy = report["policy"]

    print("ATLAS Historical Backfill Gate 11-B Pre-2021 Structural Authority Audit")
    print("  safety: derived authority evidence only; accepted Phase 10 ML/model remains untouched")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  fingerprint scope:                {report['fingerprint_scope']}")
    print(f"  Gate 11-A fingerprint:            {report['gate11a_source_fingerprint']}")
    print(f"  as-of date:                       {report['as_of_date']}")
    print("  structural policy:")
    print("    current active filter used:     False")
    print("    current delisted filter used:   False")
    print("    pre-2021 point-in-time membership claimed: False")
    print(f"    universe policy:                {policy['universe_eligibility_policy']}")
    print("    stable exact reference:         one instrument id + strong/medium identity + complete unchanged structural metadata")
    print("    rename propagation:             accepted Gate-4 chain only; all stable metadata sources must agree")
    print("    unresolved/conflicting metadata: QUARANTINE")
    print("  retained Massive reference corpus:")
    print(f"    rows / snapshots:               {int(reference['reference_rows']):,} / {int(reference['reference_snapshots']):,}")
    print(f"    range:                          {reference['reference_first_snapshot']} -> {reference['reference_last_snapshot']}")
    print(f"    pre-seam rows / snapshots:      {int(reference['preseam_reference_rows']):,} / {int(reference['preseam_reference_snapshots']):,}")
    print(f"    exact symbols:                  {int(reference['reference_symbols']):,}")
    print(f"    stable structural symbols:      {int(reference['stable_reference_symbols']):,}")
    print(f"    ticker-reuse symbols:           {int(reference['reference_reused_symbols']):,}")
    print(f"    incomplete metadata symbols:    {int(reference['reference_incomplete_symbols']):,}")
    print(f"    conflicting metadata symbols:   {int(reference['reference_conflicting_metadata_symbols']):,}")
    print("  Gate-4 chain authority artifact:")
    print(f"    chains:                         {int(authority['chains']):,}")
    print(f"    eligible chains:                {int(authority['eligible_chains']):,}")
    print(f"    status counts:                  {authority['status_counts']}")
    print(f"    semantic fingerprint:           {authority['semantic_fingerprint']}")
    print(f"    parquet sha256:                 {authority['artifact_sha256']}")
    print(f"    artifact:                       {authority['artifact_path']}")
    print("  pre-seam usable population after structural reconciliation:")
    print(f"    Gate 11-A usable rows:          {int(population['usable_rows']):,}")
    print(f"    structurally eligible rows:     {int(population['eligible_rows']):,} ({_pct(population['eligible_fraction'])})")
    print(f"    excluded/quarantined rows:      {int(population['excluded_rows']):,}")
    print(f"    exact structural authority:     {int(population['exact_authority_rows']):,}")
    print(f"    Gate-4 chain propagated:        {int(population['chain_propagated_rows']):,}")
    print(f"    usable / eligible chains:       {int(population['usable_chains']):,} / {int(population['eligible_chains']):,}")
    print(f"    usable / eligible symbols:      {int(population['usable_symbols']):,} / {int(population['eligible_symbols']):,}")
    print(f"    eligible range:                 {population['first_eligible_session']} -> {population['last_eligible_session']}")
    print(f"    eligible class rows:            {population['class_rows']}")
    print(
        "    market context coverage:        "
        f"{int(population['market_context_rows']):,} / {int(population['eligible_rows']):,} "
        f"({_pct(population['market_context_fraction'])})"
    )
    print(f"    row status accounting:          {population['authority_status_rows']}")
    print("  annual eligible evidence:")
    for item in population["annual_evidence"]:
        print(
            f"    {int(item['year'])}: usable={int(item['usable_rows']):,} "
            f"eligible={int(item['eligible_rows']):,} classes={item['class_rows']}"
        )
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  report:                            {report['report_path']}")
    print(f"  production ML writes:              {report['production_ml_writes']}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 11-B structural authority audit: FAIL")
    print("  Historical Backfill Gate 11-B structural identity/eligibility reconciliation: PASS")
    print("  Historical Backfill Gate 11-C lineage-controlled long-history dataset materialization: CURRENT")


if __name__ == "__main__":
    main()
