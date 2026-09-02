from __future__ import annotations

from packages.backtesting.literature_momseason_lit01_closeout import MomSeasonLIT01Closeout
from packages.core.settings import load_settings


def main() -> int:
    report = MomSeasonLIT01Closeout(load_settings()).run()
    print("ATLAS Literature-Anchored Alpha Exploration — LIT-01 Closeout")
    print(f"  status:                              {report['status']}")
    print(f"  scientific classification:           {report['scientific_classification']}")
    print(f"  economic signal classification:      {report['economic_signal_classification']}")
    print(f"  alpha rejection:                      {report['alpha_rejection']}")
    print(f"  alpha support:                        {report['alpha_support']}")
    print(f"  family finalist:                      {report['family_finalist']}")
    print(f"  development outcomes opened:          {report['development_outcomes_opened']}")
    print(f"  complete holding returns:             {report['development_complete_holding_returns']}")
    print(f"  unavailable holding returns:          {report['development_unavailable_holding_returns']}")
    print(f"  unavailable provider source keys:     {report['unavailable_provider_source_keys']}")
    print(f"  unavailable frozen plan rows:         {report['unavailable_plan_rows']}")
    print(f"  provider reads during closeout:       {report['provider_reads_performed']}")
    print(f"  protected return rows read:           {report['protected_return_rows_read']}")
    print(f"  protected holdout consumed:           {report['protected_holdout_consumed']}")
    print(f"  Phase33 signal-to-trade authority:     {report['phase33_signal_to_trade_authority']}")
    print(f"  next scientific action:               {report['next_scientific_action']}")
    print(f"  closeout fingerprint:                 {report['closeout_fingerprint']}")
    print(f"  report:                               {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
