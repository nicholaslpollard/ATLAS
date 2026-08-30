from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_xbrl_development import (
    XBRL_DEVELOPMENT_CONTRACT,
    XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
    XBRLDevelopmentError,
    XBRLDevelopmentStudy,
    development_implementation_fingerprint,
)
from packages.backtesting.alpha_gate_xbrl_predictor import (
    XBRL_PREDICTOR_CONTRACT,
    XBRLPredictorBuilder,
    XBRLPredictorError,
)
from packages.backtesting.alpha_gate_xbrl_scientific_policy import (
    XBRL_HYPOTHESES,
    XBRL_SCIENTIFIC_FINGERPRINT,
    xbrl_scientific_fingerprint,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.massive.xbrl_pit import MassiveCIKPITReferenceProvider
from packages.providers.sec_xbrl import SECXBRLCompanyFactsClient
from packages.providers.sec_xbrl_pit import SECXBRLPITMetadataClient


def _progress(message: str) -> None:
    print(message, flush=True)


def main() -> int:
    print("ATLAS Pre-Phase33 SEC XBRL Fundamental Alpha — Development Evaluation")
    print(f"Predictor contract: {XBRL_PREDICTOR_CONTRACT}")
    print(f"Development contract: {XBRL_DEVELOPMENT_CONTRACT}")
    print(f"Scientific fingerprint: {xbrl_scientific_fingerprint()}")
    print(f"Frozen scientific fingerprint expected: {XBRL_SCIENTIFIC_FINGERPRINT}")
    print(f"Development implementation fingerprint: {development_implementation_fingerprint()}")
    print(
        f"Frozen development implementation fingerprint expected: "
        f"{XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT}"
    )
    print(f"Finite hypotheses: {len(XBRL_HYPOTHESES)}")
    print("Protected returns: SEALED / UNREAD")
    print("Provider writes / broker / orders / PAPER / LIVE / automation: DISABLED")
    print()

    if xbrl_scientific_fingerprint() != XBRL_SCIENTIFIC_FINGERPRINT:
        print("XBRL development: NOT ACCEPTED — scientific fingerprint drifted")
        return 2
    if development_implementation_fingerprint() != XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT:
        print("XBRL development: NOT ACCEPTED — implementation fingerprint drifted")
        return 2

    try:
        settings = load_settings()
        companyfacts = SECXBRLCompanyFactsClient()
        submissions = SECXBRLPITMetadataClient()
        reference = MassiveCIKPITReferenceProvider(settings)
        predictor = XBRLPredictorBuilder(
            settings,
            companyfacts,
            submissions,
            reference,
        ).run(progress_callback=_progress)
        print()
        print("Source-only predictor reconstruction: PASS")
        print(f"Predictor rows: {predictor['predictor_rows']}")
        print(f"Stage counts: {predictor['stage_counts']}")
        print(f"Candidate counts: {predictor['candidate_counts']}")
        print(
            f"Provider source reads / cache hits: "
            f"{predictor['source_reads_performed']} / {predictor['cache_hits']}"
        )
        print(f"Target outcome rows read before development opens: {predictor['target_outcome_rows_read']}")
        print(f"Protected return rows read: {predictor['protected_return_rows_read']}")
        print()

        report = XBRLDevelopmentStudy(settings, progress_callback=_progress).run()
    except (XBRLPredictorError, XBRLDevelopmentError, ProviderError, OSError, ValueError) as exc:
        print()
        print("XBRL development: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No protected return, alpha support, Phase33 entry, or trading authority was granted.")
        return 2

    print()
    print(f"XBRL development status: {report['status']}")
    print(f"Development outcomes read: {report['target_outcome_rows_read']}")
    print(f"Outcome path diagnostics: {report['outcome_diagnostics']}")
    print(f"Development boundaries: {report['boundaries']}")
    print(f"Selection passers after all hard gates + Holm: {report['selection_passers']}")
    print(f"Selection winners: {report['selection_winners']}")
    print(f"Internal finalists: {report['internal_finalists']}")
    print(f"Protected source-only prechecks: {report['protected_source_prechecks']}")
    print(f"Protected-return eligible finalists: {report['protected_return_eligible_finalists']}")
    print(f"Protected predictor rows read for source-only precheck: {report['protected_predictor_rows_read_for_source_precheck']}")
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
