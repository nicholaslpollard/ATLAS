from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from packages.backtesting.alpha_gate_xbrl_pit_audit import (
    XBRL_PIT_AUDIT_CONTRACT,
    XBRL_PIT_AUDIT_FINGERPRINT,
    XBRL_PIT_EVIDENCE_RELATIVE,
    XBRL_PIT_REPORT_RELATIVE,
)
from packages.backtesting.alpha_gate_xbrl_pit_identity_repair import (
    XBRL_PIT_IDENTITY_REPAIR_FINGERPRINT,
    XBRLPITIdentitySemanticsRepair,
    xbrl_pit_identity_repair_fingerprint,
)
from packages.providers.massive.xbrl_pit import MassiveCIKPITReferenceProvider


class FakeSettings:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.data = SimpleNamespace(paths=SimpleNamespace(derived="data/derived", provider="data/provider"))
        self.massive = SimpleNamespace(reference=SimpleNamespace(page_limit=1000))

    def resolved_path(self, value: str) -> Path:
        return self.root / value


def test_identity_repair_fingerprint_is_frozen() -> None:
    assert xbrl_pit_identity_repair_fingerprint() == XBRL_PIT_IDENTITY_REPAIR_FINGERPRINT


def test_massive_tradable_common_stock_snapshot_uses_active_true_and_cs(tmp_path: Path) -> None:
    captured: list[dict[str, object]] = []

    class FakeMassiveClient:
        def iter_pages(self, path, params):
            captured.append({"path": path, "params": dict(params)})
            yield {
                "results": [
                    {
                        "ticker": "ABC",
                        "cik": "0000000001",
                        "composite_figi": "BBG000000001",
                        "primary_exchange": "XNYS",
                        "type": "CS",
                        "active": True,
                    }
                ]
            }

    provider = MassiveCIKPITReferenceProvider(
        FakeSettings(tmp_path), client=FakeMassiveClient()  # type: ignore[arg-type]
    )
    rows = provider.tradable_common_stock_snapshot(cik="1", as_of_date=date(2025, 5, 2))
    assert len(rows) == 1
    assert len(captured) == 1
    params = captured[0]["params"]
    assert captured[0]["path"] == "/v3/reference/tickers"
    assert params["cik"] == "0000000001"
    assert params["date"] == "2025-05-02"
    assert params["active"] is True
    assert params["type"] == "CS"


def _write_v1_target_failure(root: Path) -> None:
    issuer_reports = []
    decision_count = 0
    for issuer_index in range(40):
        cik = str(issuer_index + 1).zfill(10)
        filings = []
        for filing_index in range(5):
            accession = f"{issuer_index + 1:010d}-25-{filing_index + 1:06d}"
            filing = {
                "accession_number": accession,
                "filing_date": "2025-05-01",
                "form": "10-Q",
                "status": "AMBIGUOUS_MULTIPLE_PIT_INSTRUMENTS",
            }
            # Preserve exactly 198 decision sessions: omit two only from issuer 40.
            if not (issuer_index == 39 and filing_index >= 3):
                decision = date(2025, 5, 2 + (filing_index % 2))
                filing["decision_session"] = decision.isoformat()
                decision_count += 1
                cache_path = (
                    root
                    / "data/provider"
                    / XBRL_PIT_EVIDENCE_RELATIVE
                    / "massive_reference"
                    / decision.isoformat()
                    / f"{cik}.json"
                )
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_payload = {
                    "issuer_cik": cik,
                    "as_of_date": decision.isoformat(),
                    "rows": [
                        {
                            "ticker": f"C{issuer_index}",
                            "cik": cik,
                            "composite_figi": f"BBG{issuer_index:09d}",
                            "primary_exchange": "XNYS",
                            "type": "CS",
                            "active": True,
                        },
                        {
                            "ticker": f"OLD{issuer_index}",
                            "cik": cik,
                            "composite_figi": f"OLD{issuer_index:09d}",
                            "primary_exchange": "XNYS",
                            "type": "CS",
                            "active": False,
                        },
                        {
                            "ticker": f"W{issuer_index}",
                            "cik": cik,
                            "composite_figi": f"WAR{issuer_index:09d}",
                            "primary_exchange": "XNYS",
                            "type": "WARRANT",
                            "active": True,
                        },
                    ],
                }
                cache_path.write_text(json.dumps(cache_payload), encoding="utf-8")
            filings.append(filing)
        issuer_reports.append(
            {
                "issuer_cik": cik,
                "entity_name": f"Issuer {issuer_index + 1}",
                "filings": filings,
            }
        )
    assert decision_count == 198
    report = {
        "contract_version": XBRL_PIT_AUDIT_CONTRACT,
        "audit_fingerprint": XBRL_PIT_AUDIT_FINGERPRINT,
        "status": "AUDIT_FAIL",
        "pass": False,
        "audit_issuer_sample_size": 40,
        "companyfacts_success": 40,
        "selected_original_filings": 200,
        "sec_metadata_reconciled": 198,
        "acceptance_decisions": 198,
        "unambiguous_identity_mappings": 139,
        "issuers_with_3_unambiguous_mappings": 28,
        "same_accession_context_conflicts": 0,
        "target_outcome_rows_read": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "provider_writes_performed": 0,
        "broker_reads_performed": 0,
        "broker_writes_performed": 0,
        "order_writes_performed": 0,
        "paper_submits_performed": 0,
        "live_writes_performed": 0,
        "automation_writes_performed": 0,
        "issuer_reports": issuer_reports,
    }
    path = root / "data/derived" / XBRL_PIT_REPORT_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_repair_replays_existing_cache_and_excludes_inactive_and_non_common(tmp_path: Path) -> None:
    _write_v1_target_failure(tmp_path)
    report = XBRLPITIdentitySemanticsRepair(FakeSettings(tmp_path)).run()  # type: ignore[arg-type]
    assert report["pass"] is True
    assert report["status"] == "AUDIT_PASS"
    assert report["replayed_identity_decisions"] == 198
    assert report["cache_files_read"] == 198
    assert report["provider_reads_performed"] == 0
    assert report["unambiguous_identity_mappings"] == 198
    assert report["issuers_with_3_unambiguous_mappings"] == 40
    assert report["identity_status_counts"] == {"UNAMBIGUOUS_PIT_INSTRUMENT": 198}
    assert report["target_outcome_rows_read"] == 0
    assert report["protected_return_rows_read"] == 0
    assert report["protected_holdout_consumed"] is False
