from __future__ import annotations

from pathlib import Path

import pytest

import packages.data.historical_option_reference_v5_aciw_historical_gap_diagnostic as module
from packages.core.settings import load_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _settings(tmp_path: Path):
    base = load_settings(PROJECT_ROOT)
    return base.model_copy(update={"project_root": tmp_path.resolve()})


def _row(
    *,
    underlying: str = "ACIW",
    exchange: str = "BATO",
) -> dict[str, object]:
    return {
        "ticker": module.TARGET_TICKER,
        "underlying_ticker": underlying,
        "contract_type": "call",
        "expiration_date": module.TARGET_EXPIRATION,
        "strike_price": module.TARGET_STRIKE_PRICE,
        "exercise_style": "american",
        "shares_per_contract": 100,
        "primary_exchange": exchange,
        "cfi": "OCASPS",
        "additional_underlyings": [],
    }


def test_v5_aciw_diagnostic_contract_is_frozen() -> None:
    manifest = module.diagnostic_manifest()

    assert (
        module.HISTORICAL_OPTION_REFERENCE_V5_ACIW_HISTORICAL_GAP_DIAGNOSTIC_FINGERPRINT
        == "5be1afdd7cb18cf77f6e0c5b76d2329f4afd1d8c07c37b2c051ec003325688b1"
    )
    assert manifest["parent_v5_contract_fingerprint"] == (
        "4a9775c90414d8a454654d5f0928d79b68dec785b16b493e197ea34471aef1ea"
    )
    assert manifest["target"]["partition"] == "expired-2014-08"
    assert manifest["target"]["ticker"] == "O:ACIW140816C00040000"
    assert manifest["target"]["expiration_date"] == "2014-08-16"
    assert manifest["target"]["failed_v5_historical_as_of"] == "2014-08-15"
    assert manifest["target"]["failed_v5_expired_filter"] is False
    assert len(manifest["requests"]["historical_structural_list_matrix"]) == 8
    assert len(manifest["requests"]["contract_overview_dates"]) == 6
    assert manifest["authority"]["bulk_acquisition"] is False
    assert manifest["authority"]["conflict_resolution_rule"] is False
    assert manifest["authority"]["quarantine_rule"] is False
    assert manifest["authority"]["paper_authority"] is False
    assert manifest["authority"]["live_authority"] is False


def test_list_probe_paginates_and_does_not_filter_underlying(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    calls: list[str] = []
    left = _row(underlying="ACIW", exchange="BATO")
    right = _row(underlying="ACI", exchange="XMIO")

    def fake_request(_settings, *, url: str, api_key: str, **_kwargs):
        assert api_key == "token"
        calls.append(url)
        if len(calls) == 1:
            return 200, {
                "status": "OK",
                "request_id": "page-1",
                "results": [left],
                "next_url": (
                    settings.massive.provider.rest_base_url.rstrip("/")
                    + "/v3/reference/options/contracts?page=2"
                ),
            }
        return 200, {
            "status": "OK",
            "request_id": "page-2",
            "results": [right],
        }

    monkeypatch.setattr(module, "_request_json", fake_request)

    result = module._request_list_once(
        settings,
        api_key="token",
        as_of=module.CURRENT_AS_OF,
        expired=True,
    )

    assert len(calls) == 2
    assert "underlying_ticker=" not in calls[0]
    assert "expiration_date=2014-08-16" in calls[0]
    assert "strike_price=40" in calls[0]
    assert result["page_count"] == 2
    assert result["target_row_count"] == 2
    assert set(result["request_ids"]) == {"page-1", "page-2"}


def test_run_reproduces_zero_preexpiration_gap_and_finds_later_exact_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    left = _row(underlying="ACIW", exchange="BATO")
    historical = _row(underlying="ACI", exchange="BATO")

    monkeypatch.setenv(settings.massive.credentials.api_key_env, "token")

    def fake_list_twice(
        _settings,
        *,
        api_key: str,
        as_of: str,
        expired: bool,
    ):
        assert api_key == "token"
        if as_of == module.CURRENT_AS_OF:
            rows = [left, historical]
        elif as_of == "2014-08-15" and expired is False:
            rows = []
        elif as_of == "2014-08-16" and expired is False:
            rows = [historical]
        else:
            rows = []
        attempt = {
            "as_of": as_of,
            "expired": expired,
            "candidate_row_count": len(rows),
            "candidate_set_fingerprint": module._row_set_fingerprint(rows),
            "target_row_count": len(rows),
            "target_row_hashes": sorted(module._row_hash(row) for row in rows),
            "target_row_set_fingerprint": module._row_set_fingerprint(rows),
            "target_rows": rows,
            "page_count": 1,
            "request_ids": ["rid"],
            "safe_initial_url": "https://example.invalid",
        }
        return {
            "as_of": as_of,
            "expired": expired,
            "stable": True,
            "attempts": [attempt, dict(attempt)],
            "field_differences": module._field_differences(rows),
        }

    def fake_overview_twice(
        _settings,
        *,
        api_key: str,
        as_of: str,
    ):
        assert api_key == "token"
        row = historical if as_of == "2014-08-16" else None
        attempt = {
            "http_status": 200 if row is not None else 404,
            "request_id": "rid",
            "safe_url": "https://example.invalid",
            "provider_status": "OK" if row is not None else "NOT_FOUND",
            "provider_message": "" if row is not None else "Option Ticker not found.",
            "not_found": row is None,
            "row_present": row is not None,
            "row_hash": None if row is None else module._row_hash(row),
            "row": row,
            "response_fingerprint": module.stable_fingerprint(
                {
                    "http_status": 200 if row is not None else 404,
                    "row_hash": None if row is None else module._row_hash(row),
                }
            ),
        }
        return {
            "as_of": as_of,
            "stable": True,
            "attempts": [attempt, dict(attempt)],
        }

    monkeypatch.setattr(module, "_request_list_twice", fake_list_twice)
    monkeypatch.setattr(module, "_request_overview_twice", fake_overview_twice)

    report = module.run_historical_option_reference_v5_aciw_historical_gap_diagnostic(
        settings
    )
    interpretation = report["interpretation"]

    assert interpretation["current_list_conflict_reproduced"] is True
    assert (
        interpretation["v5_preexpiration_zero_target_failure_reproduced"] is True
    )
    assert interpretation["any_historical_exact_match"] is True
    matches = interpretation["historical_exact_list_overview_current_matches"]
    assert matches == [
        {
            "as_of": "2014-08-16",
            "expired": False,
            "list_stable": True,
            "target_row_count": 1,
            "target_row_hashes": [module._row_hash(historical)],
            "overview_stable": True,
            "overview_present": True,
            "list_overview_exact_match": True,
            "historical_payload_current_exact_match_count": 1,
        }
    ]
    assert (
        interpretation[
            "diagnostic_only_no_resolution_or_quarantine_rule_authorized"
        ]
        is True
    )


def test_overview_rejects_noncanonical_404(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)

    monkeypatch.setattr(
        module,
        "_request_json",
        lambda *_args, **_kwargs: (
            404,
            {"status": "NOT_FOUND", "message": "different"},
        ),
    )

    with pytest.raises(
        module.HistoricalOptionReferenceV5AciwHistoricalGapDiagnosticError,
        match="did not match provider NOT_FOUND semantics",
    ):
        module._request_overview_twice(
            settings,
            api_key="token",
            as_of="2014-08-15",
        )
