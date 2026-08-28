from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.backtesting.phase31_feasibility import (
    PHASE31_PROBE_WINDOWS,
    Phase31FeasibilityError,
    Phase31Form4Feasibility,
    phase31_feasibility_fingerprint,
)
from packages.providers.massive.phase31 import Phase31Form4WindowResult


class FakeSettings:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.data = SimpleNamespace(
            paths=SimpleNamespace(
                provider="data/provider",
                derived="data/derived",
            )
        )

    def resolved_path(self, value: str) -> Path:
        return self.root / value


class FakeClient:
    def __init__(self, *, drift: bool = False) -> None:
        self.drift = drift

    def form4_window(self, *, start_date, end_date) -> Phase31Form4WindowResult:
        base = start_date
        suffix = "drift" if self.drift else "stable"
        common = {
            "form_type": "4",
            "issuer_cik": "0000000001",
            "owner_cik": "0000000002",
            "record_type": "transaction",
            "is_officer": True,
            "is_director": False,
            "is_ten_percent_owner": False,
            "aff_10b5_one": False,
            "transaction_timeliness": "O",
            "security_type": "non-derivative",
            "direct_or_indirect": "D",
            "shares_owned_following_transaction": 1000,
        }
        purchase = {
            **common,
            "accession_number": f"{base.isoformat()}-P-{suffix}",
            "filing_date": base.isoformat(),
            "tickers": ["BrK.B"],
            "transaction_code": "P",
            "transaction_date": (base - timedelta(days=1)).isoformat(),
            "transaction_shares": 100,
            "transaction_price_per_share": 10.0,
            "transaction_value": 1000.0,
        }
        sale = {
            **common,
            "accession_number": f"{base.isoformat()}-S-{suffix}",
            "filing_date": base.isoformat(),
            "owner_cik": "0000000003",
            "tickers": ["brk.b"],
            "transaction_code": "S",
            "transaction_date": base.isoformat(),
            "transaction_shares": 50,
            "transaction_price_per_share": 11.0,
            "transaction_value": 550.0,
        }
        return Phase31Form4WindowResult(
            rows=(purchase, sale),
            page_count=1,
            request_ids=(f"req-{base.isoformat()}",),
        )


def test_phase31_feasibility_is_nonperformance_and_case_preserving(tmp_path: Path) -> None:
    settings = FakeSettings(tmp_path)
    report = Phase31Form4Feasibility(settings, FakeClient()).run()  # type: ignore[arg-type]

    assert report["pass"] is True
    assert report["target_outcome_rows_read"] == 0
    assert report["protected_candidate_rows_read"] == 0
    assert report["protected_return_rows_read"] == 0
    assert report["total_rows"] == len(PHASE31_PROBE_WINDOWS) * 2
    assert report["aggregate_transaction_code_counts"] == {"P": 4, "S": 4}
    assert report["public_availability_rule"] == "NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE"

    first = report["windows"][0]
    assert first["unique_tickers"] == 2
    assert first["purchase_rows_P"] == 1
    assert first["sale_rows_S"] == 1
    evidence = Path(first["evidence_path"]).read_text(encoding="utf-8")
    assert "BrK.B" in evidence
    assert "brk.b" in evidence


def test_phase31_feasibility_rerun_reuses_identical_immutable_evidence(tmp_path: Path) -> None:
    settings = FakeSettings(tmp_path)
    first = Phase31Form4Feasibility(settings, FakeClient()).run()  # type: ignore[arg-type]
    second = Phase31Form4Feasibility(settings, FakeClient()).run()  # type: ignore[arg-type]
    assert first["windows"][0]["evidence_sha256"] == second["windows"][0]["evidence_sha256"]


def test_phase31_feasibility_fails_on_immutable_evidence_drift(tmp_path: Path) -> None:
    settings = FakeSettings(tmp_path)
    Phase31Form4Feasibility(settings, FakeClient()).run()  # type: ignore[arg-type]
    with pytest.raises(Phase31FeasibilityError, match="evidence drifted"):
        Phase31Form4Feasibility(settings, FakeClient(drift=True)).run()  # type: ignore[arg-type]


def test_phase31_feasibility_fingerprint_is_stable_shape() -> None:
    fingerprint = phase31_feasibility_fingerprint()
    assert len(fingerprint) == 64
    int(fingerprint, 16)
