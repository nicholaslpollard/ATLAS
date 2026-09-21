from __future__ import annotations

import json
from pathlib import Path

import pytest

import packages.data.historical_option_reference_v2_conflict_diagnostic as module
from packages.core.settings import load_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _settings(tmp_path: Path):
    base = load_settings(PROJECT_ROOT)
    return base.model_copy(update={"project_root": tmp_path.resolve()})


def _row(*, shares=100, exchange="XBOX") -> dict[str, object]:
    return {
        "ticker": module.TARGET_TICKER,
        "underlying_ticker": "AAL",
        "contract_type": "call",
        "expiration_date": "2014-06-21",
        "strike_price": 20,
        "exercise_style": "american",
        "shares_per_contract": shares,
        "primary_exchange": exchange,
        "cfi": "OCASPS",
    }


def test_conflict_diagnostic_contract_is_frozen_and_non_authoritative() -> None:
    manifest = module.diagnostic_manifest()

    assert (
        module.HISTORICAL_OPTION_REFERENCE_V2_CONFLICT_DIAGNOSTIC_FINGERPRINT
        == "f544bb78cb6d61cbd69aa5fd266ee20349b3a977b39cb85e79a0a6a5ec0f9678"
    )
    assert manifest["parent_v2_contract_fingerprint"] == (
        "6d0af0b58a66b77c445d7e561d759dfd947e348e994045a1f7cfc16aeb9ccb41"
    )
    assert manifest["target"]["partition"] == "expired-2014-06"
    assert manifest["target"]["ticker"] == "O:AAL140621C00020000"
    assert manifest["authority"] == {
        "diagnostic_only": True,
        "bulk_acquisition": False,
        "source_mutation": False,
        "predictor_generation": False,
        "strategy_outcome_access": False,
        "paper_authority": False,
        "live_authority": False,
    }


def test_field_differences_reports_only_conflicting_fields() -> None:
    rows = [
        _row(shares=100, exchange="XBOX"),
        _row(shares=50, exchange="XBOX"),
    ]

    differences = module._field_differences(rows)

    assert differences == {"shares_per_contract": [100, 50]}


def test_structural_list_can_retain_related_candidate_series() -> None:
    payload = {
        "results": [
            _row(),
            {
                **_row(),
                "ticker": "O:AAL1140621C00020000",
            },
        ]
    }

    rows = module._extract_list_results(payload)

    assert len(rows) == 2
    assert {row["ticker"] for row in rows} == {
        module.TARGET_TICKER,
        "O:AAL1140621C00020000",
    }


def test_run_diagnostic_compares_current_historical_and_overview(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    current_rows = [
        _row(shares=100),
        _row(shares=50),
    ]
    historical_rows = [_row(shares=100)]
    current_overview_row = _row(shares=50)
    historical_overview_row = _row(shares=100)
    calls: list[str] = []

    def fake_request(_settings, *, url: str, api_key: str):
        assert api_key == "token"
        calls.append(url)
        parsed = __import__("urllib.parse").parse.urlsplit(url)
        query = dict(__import__("urllib.parse").parse.parse_qsl(parsed.query))

        if "/v3/reference/options/contracts/" in parsed.path:
            if query["as_of"] == module.CURRENT_AS_OF:
                row = current_overview_row
            else:
                row = historical_overview_row
            return 200, {
                "status": "OK",
                "request_id": f"overview-{len(calls)}",
                "results": row,
            }

        if query["as_of"] == module.CURRENT_AS_OF:
            rows = current_rows
        else:
            rows = historical_rows
        return 200, {
            "status": "OK",
            "request_id": f"list-{len(calls)}",
            "results": rows,
        }

    monkeypatch.setenv(
        settings.massive.credentials.api_key_env,
        "token",
    )
    monkeypatch.setattr(module, "_request_json", fake_request)

    report = module.run_historical_option_reference_v2_conflict_diagnostic(
        settings
    )

    assert len(calls) == 8
    assert report["status"] == "DIAGNOSTIC_COMPLETE"
    assert report["evidence_fingerprint"]

    interpretation = report["interpretation"]
    assert interpretation["current_list_conflict_reproduced"] is True
    assert interpretation["historical_list_conflict_reproduced"] is False
    assert interpretation["all_requests_repeat_stable"] is True
    assert interpretation["current_overview_matches_current_list_row"] is True
    assert interpretation["historical_overview_matches_historical_list_row"] is True
    assert interpretation["current_vs_historical_list_fingerprint_equal"] is False
    assert interpretation["current_vs_historical_overview_hash_equal"] is False
    assert interpretation["diagnostic_only_no_resolution_rule_authorized"] is True

    differences = report["current_structural_list"]["field_differences"]
    assert differences == {"shares_per_contract": [100, 50]}

    manifest_path = (
        tmp_path
        / "data/options/manifests/massive/"
        "historical_option_reference_v2_conflict_diagnostic.json"
    )
    assert manifest_path.is_file()
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert persisted["evidence_fingerprint"] == report["evidence_fingerprint"]
