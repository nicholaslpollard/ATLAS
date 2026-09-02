from __future__ import annotations

from packages.backtesting.literature_momseason_lit02_source_feasibility import (
    MomSeasonLIT02SourceFeasibilityPlan,
)
from packages.core.settings import load_settings


def main() -> int:
    report = MomSeasonLIT02SourceFeasibilityPlan(load_settings()).run()
    print("ATLAS Literature-Anchored Alpha Exploration — LIT-02 Source Feasibility")
    print(f"  status:                              {report['status']}")
    print(f"  source contract status:              {report['source_contract_status']}")
    print(f"  source policy fingerprint:           {report['source_policy_fingerprint']}")
    print(f"  feasibility cases:                   {report['feasibility_cases']}")
    print(f"  required source coverage:            {report['required_source_coverage']:.0%}")
    print(f"  feasibility plan fingerprint:        {report['feasibility_plan_fingerprint']}")
    print(f"  economic outcome values read:        {report['economic_outcome_values_read']}")
    print(f"  new price/return provider reads:      {report['new_price_or_return_provider_reads']}")
    print(f"  source metadata provider reads:       {report['source_metadata_provider_reads']}")
    print(f"  protected return rows read:           {report['protected_return_rows_read']}")
    print(f"  protected holdout consumed:           {report['protected_holdout_consumed']}")
    print(f"  fresh reuse of LIT-01 dev interval:   {report['fresh_confirmatory_reuse_of_lit01_2021_09_to_2026_04']}")
    print(f"  Phase33 signal-to-trade authority:    {report['phase33_signal_to_trade_authority']}")
    print(f"  next action:                          {report['next_action']}")
    print(f"  report fingerprint:                   {report['report_fingerprint']}")
    print(f"  plan:                                 {report['plan_path']}")
    print(f"  report:                               {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
