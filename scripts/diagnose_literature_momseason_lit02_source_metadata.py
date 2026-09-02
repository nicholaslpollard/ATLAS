from __future__ import annotations

import json

from packages.backtesting.literature_momseason_lit02_source_metadata_diagnostic import (
    MomSeasonLIT02SourceMetadataDiagnostic,
)
from packages.core.settings import load_settings


def _top(mapping: object, limit: int = 12) -> dict[str, object]:
    if not isinstance(mapping, dict):
        return {}
    return dict(list(mapping.items())[:limit])


def main() -> int:
    report = MomSeasonLIT02SourceMetadataDiagnostic(load_settings()).run()
    print("ATLAS Literature-Anchored Alpha Exploration — LIT-02 Source Metadata Diagnostic")
    print(f"  status:                              {report['status']}")
    print(f"  source classification fingerprint:   {report['source_classification_fingerprint']}")
    print(f"  source report fingerprint:           {report['source_report_fingerprint']}")
    print(f"  feasibility cases validated:         {report['feasibility_cases']}")
    print(f"  resolved cases:                      {report['resolved_cases']}")
    print(f"  unresolved cases:                    {report['unresolved_cases']}")
    print(
        "  mechanism counts:                    "
        f"{json.dumps(_top(report['mechanism_counts']), sort_keys=False)}"
    )
    print(
        "  top reason combinations:             "
        f"{json.dumps(_top(report['reason_combination_counts']), sort_keys=False)}"
    )
    print(
        "  SEC evidence modes:                  "
        f"{json.dumps(report['sec_evidence_mode_counts'], sort_keys=True)}"
    )
    print(
        "  terminal effective-date cases:       "
        f"{json.dumps(report['terminal_effective_date_cases'], sort_keys=True)}"
    )
    print(
        "  multiple cash-value conflict cases:  "
        f"{report['multiple_cash_value_conflict_cases']}"
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
