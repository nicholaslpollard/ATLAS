from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase32_predictor_acceptance import (
    PHASE32_PREDICTOR_INDEPENDENT_ACCEPTANCE_CONTRACT,
    PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256,
    PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256,
    Phase32PredictorIndependentAcceptance,
    Phase32PredictorIndependentAcceptanceError,
)
from packages.backtesting.phase32_predictor_acquisition import PHASE32_FROZEN_POLICY_FINGERPRINT
from packages.core.settings import load_settings


def _print_progress(completed: int, total: int) -> None:
    if total <= 0:
        return
    interval = max(1, total // 20)
    if completed == 1 or completed == total or completed % interval == 0:
        print(f"Phase32 independent audit progress: {completed} / {total} filing entities completed")


def main() -> int:
    print("ATLAS Phase 32 — Independent Local Predictor/Source Acceptance")
    print(f"Contract: {PHASE32_PREDICTOR_INDEPENDENT_ACCEPTANCE_CONTRACT}")
    print(f"Frozen policy fingerprint: {PHASE32_FROZEN_POLICY_FINGERPRINT}")
    print(f"Target filing-entity SHA-256: {PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256}")
    print(f"Target predictor SHA-256: {PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256}")
    print("Scope: completed local source caches + immutable predictor/source artifacts only")
    print("Network reads: FORBIDDEN / ZERO")
    print("Stock/SPY/options outcomes: FORBIDDEN / UNREAD")
    print("Protected returns: FORBIDDEN / UNREAD")
    print("Provider/broker/order/PAPER/LIVE mutations: DISABLED")
    print()

    try:
        report = Phase32PredictorIndependentAcceptance(
            load_settings(), progress_callback=_print_progress
        ).run()
    except (Phase32PredictorIndependentAcceptanceError, OSError, ValueError) as exc:
        print("Phase 32 independent predictor/source acceptance: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print(
            "Stop here. Diagnose and repair the local source/lineage/identity defect. "
            "Do not open development returns. Protected returns remain closed."
        )
        return 2

    print("Phase 32 independent predictor/source acceptance: PASS")
    print(
        f"Source rows: index={report['total_index_rows']} disclosures={report['total_disclosure_rows']} "
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
    print(f"Independent network reads: {report['independent_network_reads']}")
    print(
        "Stock / SPY / options / protected return rows read: "
        f"{report['stock_price_rows_read']} / {report['spy_price_rows_read']} / "
        f"{report['options_rows_read']} / {report['protected_return_rows_read']}"
    )
    print("Provider writes / broker reads / broker writes / orders / PAPER / LIVE: 0 / 0 / 0 / 0 / 0 / 0")
    print(f"Filing-entity evidence SHA-256: {report['candidate_filing_entity_evidence_sha256']}")
    print(f"Predictor SHA-256: {report['predictor_rows_sha256']}")
    print(f"Independent acceptance fingerprint: {report['acceptance_fingerprint']}")
    print(f"Acceptance artifact: {report['acceptance_path']}")
    print(
        "Next permitted gate after this PASS: development-return evaluation under the unchanged "
        "frozen Phase32 scientific policy. Protected returns remain closed."
    )
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
