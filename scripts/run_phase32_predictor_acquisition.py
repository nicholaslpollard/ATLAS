from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase32_predictor_acquisition import (
    PHASE32_ACQUISITION_END,
    PHASE32_ACQUISITION_START,
    PHASE32_FILING_ENTITY_KEY_RULE,
    PHASE32_FROZEN_POLICY_FINGERPRINT,
    PHASE32_PREDICTOR_ACQUISITION_CONTRACT,
    Phase32PredictorAcquisitionError,
    Phase32PredictorSourceAcquisition,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.massive.phase32 import MassivePhase32SECIndexClient
from packages.providers.massive.phase32_semantic import MassivePhase32SemanticClient
from packages.providers.massive.reference_data import MassiveReferenceProvider
from packages.providers.massive.rest import MassiveRESTClient
from packages.providers.sec_edgar import SECEDGARClient


class _Phase32SemanticAcquisitionAdapter:
    """Bind the accepted Massive semantic API to the Phase32 acquisition port."""

    def __init__(self, client: MassivePhase32SemanticClient) -> None:
        self.client = client

    def taxonomy(self) -> Any:
        return self.client.taxonomy()

    def eight_k_disclosures(self, *, start_date: date, end_date: date) -> Any:
        return self.client.disclosures_window(start_date=start_date, end_date=end_date)

    def eight_k_text(self, *, cik: object, filing_date: date) -> tuple[dict[str, Any], ...]:
        return self.client.eight_k_text(cik=cik, filing_date=filing_date)


def _print_progress(completed: int, total: int) -> None:
    if total <= 0:
        return
    interval = max(1, total // 20)
    if completed == 1 or completed == total or completed % interval == 0:
        print(f"Phase32 progress: {completed} / {total} filing entities completed")


def main() -> int:
    print("ATLAS Phase 32 — Full-History 8-K Predictor/Source Acquisition")
    print(f"Contract: {PHASE32_PREDICTOR_ACQUISITION_CONTRACT}")
    print(f"Frozen policy fingerprint: {PHASE32_FROZEN_POLICY_FINGERPRINT}")
    print(f"Filing-entity source key: {PHASE32_FILING_ENTITY_KEY_RULE}")
    print(f"Source range: {PHASE32_ACQUISITION_START}..{PHASE32_ACQUISITION_END}")
    print("Scope: source metadata + semantic predictors + PIT identity only")
    print("Stock/SPY/options outcomes: FORBIDDEN / UNREAD")
    print("Protected returns: FORBIDDEN / UNREAD")
    print("Remote mutations / broker reads / orders / PAPER / LIVE: DISABLED")
    print("Acquisition is resumable from atomically cached local source evidence.")
    print()

    try:
        settings = load_settings()
        rest = MassiveRESTClient(settings)
        semantic_client = MassivePhase32SemanticClient(rest)
        report = Phase32PredictorSourceAcquisition(
            settings,
            MassivePhase32SECIndexClient(rest),
            _Phase32SemanticAcquisitionAdapter(semantic_client),
            SECEDGARClient(),
            MassiveReferenceProvider(settings, client=rest),
            progress_callback=_print_progress,
        ).run()
    except (Phase32PredictorAcquisitionError, ProviderError, OSError, ValueError) as exc:
        print("Phase 32 full-history predictor/source acquisition: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print(
            "Stop here. Diagnose and repair the source/identity/acquisition defect. "
            "Do not open development returns. A rerun will reuse completed atomic source caches."
        )
        return 2

    print("Phase 32 full-history predictor/source acquisition: PASS")
    print(
        f"Source rows: index={report['total_index_rows']} "
        f"disclosures={report['total_disclosure_rows']} "
        f"candidate_accessions={report['frozen_candidate_source_accessions']} "
        f"filing_entities={report['candidate_filing_entity_records']} "
        f"multi_filer_accessions={report['multi_filer_candidate_accessions']}"
    )
    print(f"Eligible predictor rows: {report['eligible_predictor_rows']}")
    print(f"Candidate predictor counts: {report['candidate_predictor_counts']}")
    print(f"Stage predictor counts: {report['stage_predictor_counts']}")
    print(f"Source-stage filing-entity counts: {report['source_stage_filing_entity_counts']}")
    print(f"Identity/source exclusions: {report['exclusion_counts']}")
    print(f"Contradictory instrument sessions: {report['contradictory_instrument_sessions']}")
    print(f"Network reads this run: {report['network_reads']}")
    print(f"Cache hits this run: {report['cache_hits']}")
    print(
        "Stock / SPY / options / protected return rows read: "
        f"{report['stock_price_rows_read']} / {report['spy_price_rows_read']} / "
        f"{report['options_rows_read']} / {report['protected_return_rows_read']}"
    )
    print("Provider writes / broker reads / broker writes / orders / PAPER / LIVE: 0 / 0 / 0 / 0 / 0 / 0")
    print(f"Filing-entity evidence SHA-256: {report['candidate_filing_entity_evidence_sha256']}")
    print(f"Predictor SHA-256: {report['predictor_rows_sha256']}")
    print(f"Report: {report['report_path']}")
    print(f"Predictors: {report['predictor_path']}")
    print(
        "Next action only after independent acceptance of this PASS: development-return "
        "evaluation under the unchanged frozen policy. Protected returns remain closed."
    )
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
