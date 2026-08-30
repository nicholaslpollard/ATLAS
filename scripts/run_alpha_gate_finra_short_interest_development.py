from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_finra_short_interest_development import (
    FINRA_SHORT_INTEREST_DEVELOPMENT_CONTRACT,
    FINRA_SHORT_INTEREST_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
    FINRAShortInterestDevelopmentError,
    FINRAShortInterestDevelopmentStudy,
)
from packages.backtesting.alpha_gate_finra_short_interest_predictor import (
    FINRA_SHORT_INTEREST_PREDICTOR_CONTRACT,
    FINRAShortInterestPredictorBuilder,
    FINRAShortInterestPredictorError,
)
from packages.backtesting.alpha_gate_finra_short_interest_scientific_policy import (
    FINRA_SHORT_INTEREST_HYPOTHESES,
    FINRA_SHORT_INTEREST_SCIENTIFIC_CONTRACT,
    FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.finra_short_interest import FINRAShortInterestClient
from packages.providers.massive.reference_data import MassiveReferenceProvider


def progress(message: str) -> None:
    print(message, flush=True)


def main() -> int:
    print("ATLAS Pre-Phase33 Alpha Gate — FINRA Short Interest Development")
    print(f"Scientific contract: {FINRA_SHORT_INTEREST_SCIENTIFIC_CONTRACT}")
    print(f"Scientific fingerprint: {FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT}")
    print(f"Predictor contract: {FINRA_SHORT_INTEREST_PREDICTOR_CONTRACT}")
    print(f"Development contract: {FINRA_SHORT_INTEREST_DEVELOPMENT_CONTRACT}")
    print(
        "Development implementation fingerprint: "
        f"{FINRA_SHORT_INTEREST_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT}"
    )
    print(
        "Frozen hypotheses: "
        + ", ".join(
            f"{spec.candidate_id}:{spec.direction}"
            for spec in FINRA_SHORT_INTEREST_HYPOTHESES
        )
    )
    print("Stage 1: reconstruct complete source-only predictor population")
    print("Stage 2: open development-only exact 63-session paths only if Stage 1 passes")
    print("Protected returns: SEALED / UNREAD")
    print("Provider writes / broker / order / PAPER / LIVE / automation: DISABLED")
    print()

    try:
        settings = load_settings()
        predictor = FINRAShortInterestPredictorBuilder(
            settings,
            FINRAShortInterestClient(),
            MassiveReferenceProvider(settings),
            progress_callback=progress,
        ).run()
    except (FINRAShortInterestPredictorError, ProviderError, OSError, ValueError) as exc:
        print("FINRA source-only predictor reconstruction: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("Development market outcomes were not opened.")
        print("Protected returns remain unread; Phase33 and trading authority remain blocked.")
        return 2

    print()
    print(f"FINRA source-only predictor reconstruction: {predictor['status']}")
    print(f"Predictor rows: {predictor['predictor_rows']}")
    print(f"Stage counts: {predictor['stage_counts']}")
    print(f"Candidate counts: {predictor['candidate_counts']}")
    print(f"Source-only gates: {predictor['source_only_gates']}")
    print(f"Diagnostics: {predictor['diagnostics']}")
    print(
        "FINRA source files / Massive PIT snapshots: "
        f"{predictor['finra_source_files_read']} / "
        f"{predictor['massive_reference_snapshots_read']}"
    )
    print(f"Target outcome rows before development: {predictor['target_outcome_rows_read']}")
    print(f"Protected return rows: {predictor['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {predictor['protected_holdout_consumed']}")
    print(f"Predictor report: {predictor['report_path']}")
    if predictor.get("pass") is not True:
        print("Source-only predictor gate did not pass; market outcomes remain sealed.")
        print("Pass: False")
        return 1

    print()
    try:
        report = FINRAShortInterestDevelopmentStudy(
            settings, progress_callback=progress
        ).run()
    except (FINRAShortInterestDevelopmentError, OSError, ValueError) as exc:
        print("FINRA short-interest development: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("Protected returns remain unread; Phase33 and trading authority remain blocked.")
        return 3

    print()
    print(f"FINRA short-interest development status: {report['status']}")
    print(f"Development outcomes read: {report['target_outcome_rows_read']}")
    print(f"Outcome diagnostics: {report['outcome_diagnostics']}")
    print(f"Boundaries: {report['boundaries']}")
    print(f"Selection passers: {report['selection_passers']}")
    print(f"Selection winners: {report['selection_winners']}")
    print(f"Internal finalists: {report['internal_finalists']}")
    print(f"Protected source-only prechecks: {report['protected_source_prechecks']}")
    print(
        "Protected-return eligible finalists: "
        f"{report['protected_return_eligible_finalists']}"
    )
    print(
        "Protected predictor rows read for source-only precheck: "
        f"{report['protected_predictor_rows_read_for_source_precheck']}"
    )
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {report['protected_holdout_consumed']}")
    print(f"Phase33 authority: {report['phase33_signal_to_trade_authority']}")
    print("Provider writes / broker reads / broker writes / orders / PAPER / LIVE / automation: 0 / 0 / 0 / 0 / 0 / 0 / 0")
    print(f"Development report: {report['report_path']}")
    print(f"Next scientific action: {report['next_scientific_action']}")
    print(f"Pass: {report['pass']}")
    return 0 if report['pass'] else 1


if __name__ == "__main__":
    raise SystemExit(main())
