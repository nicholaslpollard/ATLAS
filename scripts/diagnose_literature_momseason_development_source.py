from __future__ import annotations

from packages.backtesting.literature_momseason_development_source_diagnostic import (
    MomSeasonDevelopmentSourceIncompleteDiagnostic,
)
from packages.core.settings import load_settings


def main() -> None:
    result = MomSeasonDevelopmentSourceIncompleteDiagnostic(load_settings()).run()
    print("ATLAS Literature-Anchored Alpha Exploration — LIT-01 Development Source Diagnostic")
    print(f"  status:                              {result['status']}")
    print(f"  contract:                            {result['contract_version']}")
    print(f"  freeze fingerprint:                  {result['freeze_fingerprint']}")
    print(f"  holdings fingerprint:                {result['holdings_fingerprint']}")
    print(f"  target plan fingerprint:             {result['target_plan_fingerprint']}")
    print(f"  holdings rows:                       {result['holdings_rows']}")
    print(f"  target plan rows:                    {result['target_plan_rows']}")
    print(f"  cached transport source keys:        {result['cached_transport_source_keys']}")
    print(f"  missing target units:                {result['missing_target_units']}")
    print(f"  unavailable plan rows:               {result['unavailable_plan_rows']}")
    print(f"  unavailable provider source keys:    {result['unavailable_source_keys']}")
    print(f"  unavailable status counts:           {result['unavailable_status_counts']}")
    print(f"  blocked frozen holdings:             {result['blocked_holdings']}")
    print(f"  blocked by hypothesis:               {result['blocked_holdings_by_hypothesis']}")
    print(f"  blocked by target month:             {result['blocked_holdings_by_target_month']}")
    print("  unavailable source details:")
    for item in result["details"]:
        print(
            "    "
            f"{item['endpoint_session']} {item['historical_ticker']} "
            f"status={item['availability_status']} "
            f"instrument_rows={item['instrument_rows']} "
            f"prior_hits={item['prior_holding_hits']} "
            f"target_hits={item['target_holding_hits']} "
            f"blocked_holdings={item['blocked_holdings']} "
            f"hypotheses={item['hypotheses']} "
            f"months={item['target_months']} "
            f"instruments={item['instrument_ids']}"
        )
    print("  scientific interpretation:")
    print(f"    {result['scientific_interpretation']}")
    print("  safety boundary:")
    print(f"    provider reads performed:          {result['provider_reads_performed']}")
    print(f"    protected return rows read:        {result['protected_return_rows_read']}")
    print(f"    protected holdout consumed:        {result['protected_holdout_consumed']}")
    print(f"    broker reads performed:            {result['broker_reads_performed']}")
    print(f"    order writes performed:            {result['order_writes_performed']}")
    print(f"    PAPER submits performed:           {result['paper_submits_performed']}")
    print(f"    LIVE writes performed:             {result['live_writes_performed']}")
    print(f"  report:                              {result['report_path']}")


if __name__ == "__main__":
    main()
