from __future__ import annotations

from packages.backtesting.phase31_closeout import Phase31Closeout
from packages.backtesting.phase31_validation import Phase31IndependentNegativeValidator
from packages.core.settings import load_settings


def main() -> None:
    settings = load_settings()
    validation = Phase31IndependentNegativeValidator(settings).run()
    closeout = Phase31Closeout(settings).run()

    print("ATLAS Phase 31 — Independent Negative Reconstruction + Full Closeout")
    print(f"Frozen Phase31 policy fingerprint: {closeout['phase31_policy_fingerprint']}")
    print(f"Independent validation: {validation['status']}")
    print(
        "Reconstructed development predictor / usable rows: "
        f"{validation['reconstructed_development_predictor_rows']} / "
        f"{validation['reconstructed_usable_outcome_rows']}"
    )
    path = validation["reconstructed_path_diagnostics"]
    print(
        "Independent path exclusions: "
        f"missing_exact_stock_path={path['exact_stock_path_missing_rows']} "
        f"split_crossing={path['split_crossing_censored_rows']}"
    )
    print("Independent selection reconstruction:")
    for candidate_id, metrics in validation["reconstructed_selection"].items():
        print(
            f"  {candidate_id}: rows={metrics['raw_rows']} "
            f"sessions={metrics['signal_sessions']} "
            f"tickers={metrics['unique_tickers']} "
            f"mandatory_sample_gate_fail="
            f"{validation['mandatory_sample_gate_failures'][candidate_id]}"
        )
    print(f"Selection survivors: {closeout['selection_survivor_ids']}")
    print(f"Selection winners: {closeout['selection_winner_ids']}")
    print(f"Frozen finalists: {closeout['finalist_ids']}")
    print(f"Supported candidates: {closeout['supported_candidate_ids']}")
    print(f"Phase 31 disposition: {closeout['phase31_disposition']}")
    print(f"Phase 32 signal-to-trade entry satisfied: {closeout['phase32_entry_satisfied']}")
    print(f"Protected candidate rows read: {closeout['protected_candidate_rows_read']}")
    print(f"Protected return rows read: {closeout['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {closeout['protected_holdout_consumed']}")
    print(
        "Provider reads/writes / broker reads/writes / orders / PAPER / LIVE: "
        f"{closeout['provider_reads']} / {closeout['provider_writes']} / "
        f"{closeout['broker_reads']} / {closeout['broker_writes']} / "
        f"{closeout['order_writes']} / {closeout['paper_submits']} / "
        f"{closeout['live_writes']}"
    )
    print(f"Closeout report: {closeout['report_path']}")
    print(
        "Next project action: document/merge Phase31 ACCEPTED_NEGATIVE, then rebaseline "
        "another materially distinct alpha source. Phase32 signal-to-trade remains blocked."
    )
    print(f"Pass: {closeout['pass']}")


if __name__ == "__main__":
    main()
