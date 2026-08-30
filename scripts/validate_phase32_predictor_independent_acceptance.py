from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase32_policy import phase32_policy_fingerprint
from packages.backtesting.phase32_predictor_acceptance import (
    PHASE32_PREDICTOR_INDEPENDENT_ACCEPTANCE_CONTRACT,
    PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256,
    PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256,
    Phase32PredictorIndependentAcceptance,
    Phase32PredictorIndependentAcceptanceError,
    _rebuild_predictors,
    reconcile_massive_text_rows,
)
from packages.backtesting.phase32_predictor_acquisition import PHASE32_FROZEN_POLICY_FINGERPRINT


def _filing_row(candidate_id: str, direction: str, *, instrument_id: str = "figi:ABC") -> dict[str, object]:
    return {
        "eligibility": "eligible",
        "instrument": {
            "instrument_id": instrument_id,
            "identity_key": ["composite_figi", "ABC"],
            "identity_quality": "strong",
        },
        "candidate_ids": [candidate_id],
        "accession_number": f"0000000001-23-00000{1 if direction == 'LONG' else 2}",
        "issuer_cik": "0000000001",
        "decision_session": "2023-10-06",
        "exit_session": "2023-10-13",
        "stage": "development",
        "provider_tickers": ["ABC"],
        "taxonomy_triples": [["x", "y", "z"]],
        "acceptance_datetime": "2023-10-05T16:00:00-04:00",
        "sec_source_record_sha256": "a" * 64,
        "massive_text_sha256": "b" * 64,
        "supporting_text_sha256": ["c" * 64],
    }


def main() -> int:
    assert PHASE32_PREDICTOR_INDEPENDENT_ACCEPTANCE_CONTRACT == (
        "phase32-predictor-independent-acceptance-v1-local-immutable-source-only"
    )
    assert phase32_policy_fingerprint() == PHASE32_FROZEN_POLICY_FINGERPRINT
    assert re.fullmatch(r"[0-9a-f]{64}", PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256)
    assert re.fullmatch(r"[0-9a-f]{64}", PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256)
    assert PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256 == (
        "18fd036f8718bba9920395627f0e233cd9cead41d03decb31f29d5bdf0a3ff31"
    )
    assert PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256 == (
        "c5b171557d173bdf0095aecfaf660b8660f2480d233fa9c5a55f138b86c1f3f9"
    )

    module_source = (PROJECT_ROOT / "packages" / "backtesting" / "phase32_predictor_acceptance.py").read_text(
        encoding="utf-8"
    )
    forbidden_imports = (
        "packages.providers",
        "urllib.request",
        "requests",
        "httpx",
        "socket",
    )
    for forbidden in forbidden_imports:
        assert forbidden not in module_source, forbidden
    constructor = inspect.signature(Phase32PredictorIndependentAcceptance.__init__)
    assert "index_client" not in constructor.parameters
    assert "semantic_client" not in constructor.parameters
    assert "sec_client" not in constructor.parameters
    assert "reference_provider" not in constructor.parameters

    base = {
        "accession_number": "0000000001-23-000001",
        "cik": "0000000001",
        "filing_date": "2023-10-05",
        "form_type": "8-K",
        "filing_url": "https://www.sec.gov/example.txt",
        "items_text": "same filing text",
    }
    valid = reconcile_massive_text_rows(
        [{**base, "ticker": "AAA"}, {**base, "ticker": "BBB"}],
        accession="0000000001-23-000001",
        issuer_cik="0000000001",
    )
    assert valid["row_count"] == 2
    assert valid["tickers"] == ["AAA", "BBB"]
    try:
        reconcile_massive_text_rows(
            [{**base, "ticker": "AAA"}, {**base, "ticker": "BBB", "items_text": "changed"}],
            accession="0000000001-23-000001",
            issuer_cik="0000000001",
        )
    except Phase32PredictorIndependentAcceptanceError:
        pass
    else:  # pragma: no cover
        raise AssertionError("non-ticker Text conflict did not fail closed")

    one, contradictions, contradiction_rows = _rebuild_predictors(
        [_filing_row("share_repurchase_long", "LONG")]
    )
    assert len(one) == 1
    assert one[0]["candidate_id"] == "share_repurchase_long"
    assert one[0]["outcome_rows_read"] == 0
    assert contradictions == 0
    assert contradiction_rows == 0

    none, contradictions, contradiction_rows = _rebuild_predictors(
        [
            _filing_row("share_repurchase_long", "LONG"),
            _filing_row("equity_issuance_short", "SHORT"),
        ]
    )
    assert none == []
    assert contradictions == 1
    assert contradiction_rows == 2

    print("ATLAS Phase 32 independent predictor/source acceptance contract: PASS")
    print(f"- frozen policy fingerprint pinned: {PHASE32_FROZEN_POLICY_FINGERPRINT}")
    print(f"- target filing-entity SHA-256 pinned: {PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256}")
    print(f"- target predictor SHA-256 pinned: {PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256}")
    print("- independent acceptance implementation has no provider/network client dependency")
    print("- local Text multiplicity is independently rechecked and conflicts fail closed")
    print("- deterministic predictor aggregation and contradictory LONG/SHORT exclusion are rechecked")
    print("- market outcomes, broker reads, orders, PAPER, and LIVE authority remain absent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
