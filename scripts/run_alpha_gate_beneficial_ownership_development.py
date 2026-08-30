from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_beneficial_ownership_development import (
    BENEFICIAL_OWNERSHIP_DEVELOPMENT_CONTRACT,
    BENEFICIAL_OWNERSHIP_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
    BeneficialOwnershipDevelopmentError,
    BeneficialOwnershipDevelopmentStudy,
    development_implementation_fingerprint,
)
from packages.backtesting.alpha_gate_beneficial_ownership_predictor import (
    BENEFICIAL_OWNERSHIP_PREDICTOR_CONTRACT,
    BeneficialOwnershipPredictorBuilder,
    BeneficialOwnershipPredictorError,
)
from packages.backtesting.alpha_gate_beneficial_ownership_scientific_policy import (
    BENEFICIAL_OWNERSHIP_HYPOTHESES,
    BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT,
    beneficial_ownership_scientific_fingerprint,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.massive.xbrl_pit import MassiveCIKPITReferenceProvider
from packages.providers.sec_edgar_archive import SECEDGARArchiveClient


def _progress(message: str) -> None:
    print(message, flush=True)


def main() -> int:
    print("ATLAS Pre-Phase33 SEC Schedule 13D/13G Beneficial Ownership — Development Evaluation")
    print(f"Predictor contract: {BENEFICIAL_OWNERSHIP_PREDICTOR_CONTRACT}")
    print(f"Development contract: {BENEFICIAL_OWNERSHIP_DEVELOPMENT_CONTRACT}")
    print(f"Scientific fingerprint: {beneficial_ownership_scientific_fingerprint()}")
    print(
        "Frozen scientific fingerprint expected: "
        f"{BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT}"
    )
    print(
        "Development implementation fingerprint: "
        f"{development_implementation_fingerprint()}"
    )
    print(
        "Frozen development implementation fingerprint expected: "
        f"{BENEFICIAL_OWNERSHIP_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT}"
    )
    print(f"Finite hypotheses: {len(BENEFICIAL_OWNERSHIP_HYPOTHESES)}")
    print("Protected returns: SEALED / UNREAD")
    print("Provider writes / broker / orders / PAPER / LIVE / automation: DISABLED")
    print()

    if beneficial_ownership_scientific_fingerprint() != BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT:
        print("Beneficial-ownership development: NOT ACCEPTED — scientific fingerprint drifted")
        return 2
    if (
        development_implementation_fingerprint()
        != BENEFICIAL_OWNERSHIP_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT
    ):
        print("Beneficial-ownership development: NOT ACCEPTED — implementation fingerprint drifted")
        return 2

    try:
        settings = load_settings()
        predictor = BeneficialOwnershipPredictorBuilder(
            settings,
            SECEDGARArchiveClient(),
            MassiveCIKPITReferenceProvider(settings),
            progress_callback=_progress,
        ).build()
        print()
        print("Source-only predictor reconstruction: PASS")
        print(f"Predictor rows: {predictor['predictor_rows']}")
        print(f"Stage counts: {predictor['stage_counts']}")
        print(f"Candidate counts: {predictor['candidate_counts']}")
        print(f"Source sample counts: {predictor['source_sample_counts']}")
        print(f"Predictor diagnostics: {predictor['diagnostics']}")
        print(
            "Provider source reads / cache hits: "
            f"{predictor['provider_source_reads']} / {predictor['cache_hits']}"
        )
        print(
            "Target outcome rows read before development opens: "
            f"{predictor['target_outcome_rows_read']}"
        )
        print(f"Protected return rows read: {predictor['protected_return_rows_read']}")
        print()

        report = BeneficialOwnershipDevelopmentStudy(
            settings, progress_callback=_progress
        ).run()
    except (
        BeneficialOwnershipPredictorError,
        BeneficialOwnershipDevelopmentError,
        ProviderError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        print()
        print("Beneficial-ownership development: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print(
            "No protected return, alpha support, Phase33 entry, or trading authority was granted."
        )
        return 2

    print()
    print(f"Beneficial-ownership development status: {report['status']}")
    print(f"Development outcomes read: {report['target_outcome_rows_read']}")
    print(f"Outcome path diagnostics: {report['outcome_diagnostics']}")
    print(f"Development boundaries: {report['boundaries']}")
    print(
        "Selection passers after all hard gates + Holm: "
        f"{report['selection_passers']}"
    )
    print(f"Selection winners: {report['selection_winners']}")
    print(f"Internal finalists: {report['internal_finalists']}")
    print(f"Regulatory-era diagnostics: {report['regulatory_era_diagnostics']}")
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
    print(
        "Provider writes / broker reads / broker writes / orders / PAPER / LIVE / automation: "
        f"{report['provider_writes_performed']} / {report['broker_reads_performed']} / "
        f"{report['broker_writes_performed']} / {report['order_writes_performed']} / "
        f"{report['paper_submits_performed']} / {report['live_writes_performed']} / "
        f"{report['automation_writes_performed']}"
    )
    print(f"Phase33 authority: {report['phase33_signal_to_trade_authority']}")
    print(f"Development report: {report['report_path']}")
    print(f"Next scientific action: {report['next_scientific_action']}")
    print(f"Pass: {report['pass']}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
