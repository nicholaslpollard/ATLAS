from __future__ import annotations

import json

from packages.backtesting.literature_momseason_lit02_source_metadata_repair_v2_diagnostic import (
    MomSeasonLIT02RepairV2ResidualDiagnostic,
)
from packages.core.settings import load_settings


def _top(mapping: object, limit: int = 14) -> dict[str, object]:
    if not isinstance(mapping, dict):
        return {}
    return dict(list(mapping.items())[:limit])


def main() -> int:
    report = MomSeasonLIT02RepairV2ResidualDiagnostic(load_settings()).run()
    print("ATLAS Literature-Anchored Alpha Exploration — LIT-02 Repair-v2 Residual Diagnostic")
    print(f"  status:                              {report['status']}")
    print(f"  repair-v2 classification fingerprint:{report['repair_v2_classification_fingerprint']}")
    print(f"  repair-v2 report fingerprint:        {report['repair_v2_report_fingerprint']}")
    print(f"  feasibility cases validated:         {report['feasibility_cases']}")
    print(f"  resolved cases:                      {report['resolved_cases']}")
    print(f"  newly resolved by repair-v2:         {report['newly_resolved_cases']}")
    print(f"  unresolved cases:                    {report['unresolved_cases']}")
    print(f"  source coverage:                     {float(report['source_coverage']) * 100:.2f}%")
    print(
        "  mechanism counts:                    "
        f"{json.dumps(_top(report['mechanism_counts']), sort_keys=False)}"
    )
    print(
        "  top reason combinations:             "
        f"{json.dumps(_top(report['reason_combination_counts']), sort_keys=False)}"
    )
    print(
        "  SEC residual case modes:             "
        f"{json.dumps(report['sec_residual_case_modes'], sort_keys=True)}"
    )
    print(
        "  SEC candidate reasons:               "
        f"{json.dumps(_top(report['candidate_reason_counts']), sort_keys=False)}"
    )
    print(
        "  date-unresolved value profiles:      "
        f"{json.dumps(report['date_unresolved_value_profiles'], sort_keys=True)}"
    )
    print(
        "  context-unresolved value profiles:   "
        f"{json.dumps(report['context_unresolved_value_profiles'], sort_keys=True)}"
    )
    print(
        "  identity gap cases:                  "
        f"{json.dumps(report['identity_gap_cases'], sort_keys=True)}"
    )
    print(
        "  repeated unresolved tickers:         "
        f"{json.dumps(report['repeated_unresolved_tickers'][:20], sort_keys=True)}"
    )
    print(f"  provider reads during diagnostic:    {report['provider_reads_performed']}")
    print(f"  economic outcome values read:        {report['economic_outcome_values_read']}")
    print(f"  new price/return provider reads:      {report['new_price_or_return_provider_reads']}")
    print(f"  protected return rows read:           {report['protected_return_rows_read']}")
    print(f"  protected holdout consumed:           {report['protected_holdout_consumed']}")
    print(f"  LIT-02 economic design unblocked:     {report['lit02_economic_design_unblocked']}")
    print(f"  Phase33 signal-to-trade authority:    {report['phase33_signal_to_trade_authority']}")
    print(f"  diagnostic fingerprint:              {report['diagnostic_fingerprint']}")
    print(f"  next action:                          {report['next_action']}")
    print(f"  report:                               {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
