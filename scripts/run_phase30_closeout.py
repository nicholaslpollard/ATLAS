from __future__ import annotations

from packages.backtesting.phase30_closeout import Phase30Closeout
from packages.backtesting.phase30_validation import Phase30IndependentNegativeValidator
from packages.core.settings import load_settings


def main() -> None:
    settings = load_settings()
    validation = Phase30IndependentNegativeValidator(settings).run()
    closeout = Phase30Closeout(settings).run()

    print("ATLAS Phase 30 — Independent Negative Reconstruction + Full Closeout")
    print(f"Frozen Phase30 policy fingerprint: {closeout['phase30_policy_fingerprint']}")
    print(f"Independent validation: {validation['status']}")
    print(
        "Reconstructed population rows/tickers/sessions: "
        f"{validation['reconstructed_population_rows']} / "
        f"{validation['reconstructed_population_tickers']} / "
        f"{validation['reconstructed_population_sessions']}"
    )
    print("Independent selection reconstruction:")
    for candidate_id, metrics in validation["reconstructed_selection"].items():
        print(
            f"  {candidate_id}: rows={metrics['raw_rows']} "
            f"sessions={metrics['signal_sessions']} "
            f"mean10={metrics['primary_mean_return']}"
        )
    print(f"Selection survivors: {closeout['selection_survivor_ids']}")
    print(f"Selection winners: {closeout['selection_winner_ids']}")
    print(f"Frozen finalists: {closeout['finalist_ids']}")
    print(f"Supported candidates: {closeout['supported_candidate_ids']}")
    print(f"Phase 30 disposition: {closeout['phase30_disposition']}")
    print(f"Phase 31 entry satisfied: {closeout['phase31_entry_satisfied']}")
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
    print("Next project action: Phase30 documentation/merge, then rebaseline the next alpha architecture; Phase31 remains blocked because supported alpha is still zero.")
    print(f"Pass: {closeout['pass']}")


if __name__ == "__main__":
    main()
