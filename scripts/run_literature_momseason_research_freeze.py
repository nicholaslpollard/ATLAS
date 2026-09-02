from __future__ import annotations

from packages.backtesting.literature_momseason_research_freeze import MomSeasonResearchFreeze
from packages.core.settings import load_settings


def _ratio(value: object) -> str:
    try:
        return f"{float(value):.6f}"
    except (TypeError, ValueError):
        return str(value)


def main() -> int:
    report = MomSeasonResearchFreeze(load_settings()).run()
    contract = report["scientific_contract"]
    development = contract["development_gate"]
    protected = contract["protected_policy"]
    costs = contract["transaction_costs"]
    calibration = report["positive_path_calibration"]
    gate = report["gate_assessment"]

    print("ATLAS Literature-Anchored Alpha Exploration — LIT-01 Research Gate + Scientific Freeze")
    print(f"  status:                              {report['status']}")
    print(f"  contract:                            {report['contract_version']}")
    print(f"  freeze fingerprint:                  {report['freeze_fingerprint']}")
    print("  scientific family:")
    print(f"    fixed hypotheses:                  {development['family_size']}")
    print(f"    family alpha:                      {development['family_alpha']}")
    print(f"    multiple testing:                  {development['multiple_testing']}")
    print("  independent sample:")
    print(f"    unit:                              {development['independent_unit']}")
    print(f"    development months:                {development['development_month_count']}")
    months = development['development_months']
    print(f"    range:                             {months[0]} through {months[-1]}")
    bootstrap = development['bootstrap']
    print("  primary inference:")
    print(f"    bootstrap:                         {bootstrap['type']}")
    print(f"    block months:                      {bootstrap['block_months']}")
    print(f"    replicates:                        {bootstrap['replicates']}")
    print(f"    one-sided direction:               {bootstrap['one_sided_direction']}")
    print(f"    confidence:                        {bootstrap['confidence']}")
    print("  transaction costs:")
    print(
        "    primary/stress per leg:           "
        f"{costs['primary_bps_per_one_way_leg_turnover']:.1f}/"
        f"{costs['stress_bps_per_one_way_leg_turnover']:.1f} bps"
    )
    print(f"    realized-turnover costing:         True")
    print("  positive-path calibration:")
    print(f"    trials:                            {calibration['trials']}")
    print(f"    family promotions:                 {calibration['family_promotions']}")
    print(f"    family detection rate:             {_ratio(calibration['family_detection_rate'])}")
    print(f"    target detection rate:             {_ratio(calibration['target_family_detection_rate'])}")
    print(f"    target met:                        {calibration['target_met']}")
    for key, value in calibration['hypothesis_detection_rates'].items():
        print(f"    {key:<34} {_ratio(value)}")
    print("  generic prospective-freeze gate:")
    print(f"    disposition:                       {gate['disposition']}")
    print(f"    ready to freeze:                   {gate['ready_to_freeze']}")
    reach = gate['gate_reachability']
    print(f"    reachability:                      {reach['disposition']}")
    print(f"    strictest Holm threshold:          {_ratio(reach['strictest_holm_threshold'])}")
    print(f"    empirical p-value floor:           {_ratio(reach['empirical_p_value_floor'])}")
    print("  protected policy:")
    print(
        "    current complete / required:       "
        f"{protected['current_complete_target_months']}/"
        f"{protected['minimum_complete_target_months']}"
    )
    print(f"    current window sufficient:         {protected['current_window_sufficient']}")
    print("  safety boundary:")
    print(f"    development outcome rows read:     {report['development_outcome_rows_read']}")
    print(f"    target outcome rows read:          {report['target_outcome_rows_read']}")
    print(f"    protected return rows read:        {report['protected_return_rows_read']}")
    print(f"    protected holdout consumed:        {report['protected_holdout_consumed']}")
    print(f"    provider reads performed:          {report['provider_reads_performed']}")
    print(f"    broker reads performed:            {report['broker_reads_performed']}")
    print(f"    order writes performed:            {report['order_writes_performed']}")
    print(f"    PAPER submits performed:           {report['paper_submits_performed']}")
    print(f"    LIVE writes performed:             {report['live_writes_performed']}")
    print(f"  report:                              {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
