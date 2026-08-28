from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.backtesting.phase31_diagnostics import (
    PHASE31_EXPECTED_FAILED_CHECK,
    Phase31Form4LagDiagnostic,
    Phase31Form4LagDiagnosticError,
)
from packages.backtesting.phase31_feasibility import Phase31FeasibilityError, Phase31Form4Feasibility
from packages.providers.massive.phase31 import Phase31Form4WindowResult


class FakeSettings:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.data = SimpleNamespace(
            paths=SimpleNamespace(provider="data/provider", derived="data/derived")
        )

    def resolved_path(self, value: str) -> Path:
        return self.root / value


class ChronologyViolationClient:
    def form4_window(self, *, start_date, end_date) -> Phase31Form4WindowResult:
        common = {
            "form_type": "4",
            "issuer_cik": "0000000001",
            "owner_cik": "0000000002",
            "record_type": "transaction",
            "security_type": "non-derivative",
            "direct_or_indirect": "D",
            "is_officer": True,
            "is_director": False,
            "is_ten_percent_owner": False,
            "aff_10b5_one": False,
            "transaction_timeliness": "O",
        }
        future_purchase = {
            **common,
            "accession_number": f"{start_date.isoformat()}-future-P",
            "filing_date": start_date.isoformat(),
            "transaction_date": (start_date + timedelta(days=1)).isoformat(),
            "transaction_code": "P",
            "transaction_acquired_disposed": "A",
            "transaction_shares": 100,
            "transaction_price_per_share": 10.0,
            "transaction_value": 1000.0,
            "shares_owned_following_transaction": 1000,
            "tickers": ["BrK.B"],
            "filing_url": "https://www.sec.gov/example",
        }
        same_day_sale = {
            **common,
            "accession_number": f"{start_date.isoformat()}-same-S",
            "owner_cik": "0000000003",
            "filing_date": start_date.isoformat(),
            "transaction_date": start_date.isoformat(),
            "transaction_code": "S",
            "transaction_acquired_disposed": "D",
            "transaction_shares": 50,
            "transaction_price_per_share": 11.0,
            "transaction_value": 550.0,
            "shares_owned_following_transaction": 950,
            "tickers": ["brk.b"],
        }
        return Phase31Form4WindowResult(
            rows=(future_purchase, same_day_sale),
            page_count=1,
            request_ids=(f"req-{start_date.isoformat()}",),
        )


def _prepare_failed_target(tmp_path: Path) -> FakeSettings:
    settings = FakeSettings(tmp_path)
    with pytest.raises(Phase31FeasibilityError, match=PHASE31_EXPECTED_FAILED_CHECK):
        Phase31Form4Feasibility(settings, ChronologyViolationClient()).run()  # type: ignore[arg-type]
    return settings


def test_phase31_lag_diagnostic_reconstructs_failed_frozen_evidence(tmp_path: Path) -> None:
    settings = _prepare_failed_target(tmp_path)
    report = Phase31Form4LagDiagnostic(settings).run()  # type: ignore[arg-type]

    assert report["pass"] is True
    assert report["source_failed_checks"] == [PHASE31_EXPECTED_FAILED_CHECK]
    assert report["lag_relation_counts"] == {
        "transaction_after_filing": 4,
        "transaction_same_day_as_filing": 4,
    }
    assert report["violating_rows"] == 4
    assert report["violating_unique_accessions"] == 4
    assert report["violation_transaction_code_counts"] == {"P": 4}
    assert report["violation_security_type_counts"] == {"non-derivative": 4}
    assert report["violation_acquired_disposed_counts"] == {"A": 4}
    assert report["violation_10b5_1_counts"] == {"false": 4}
    assert report["violation_role_counts"] == {"officer": 4}
    assert report["violation_transaction_after_filing_gap_days"] == {"1": 4}
    assert report["target_outcome_rows_read"] == 0
    assert report["protected_candidate_rows_read"] == 0
    assert report["protected_return_rows_read"] == 0
    assert report["provider_reads"] == 0
    assert report["broker_reads"] == 0
    assert report["order_writes"] == 0
    assert report["paper_submits"] == 0
    assert report["live_writes"] == 0
    assert Path(report["violation_artifact_path"]).is_file()
    assert Path(report["report_path"]).is_file()
    assert report["violation_samples"][0]["tickers"] == ["BrK.B"]


def test_phase31_lag_diagnostic_fails_if_frozen_evidence_hash_drifts(tmp_path: Path) -> None:
    settings = _prepare_failed_target(tmp_path)
    diagnostic = Phase31Form4LagDiagnostic(settings)  # type: ignore[arg-type]
    evidence = diagnostic.evidence_path("research_boundary")
    evidence.write_text(evidence.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")

    with pytest.raises(Phase31Form4LagDiagnosticError, match="SHA mismatch"):
        diagnostic.run()
