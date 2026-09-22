from __future__ import annotations

from pathlib import Path

import pytest

import packages.data.historical_option_reference_v4_correction_conflict_diagnostic as module
from packages.core.settings import load_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _settings(tmp_path: Path):
    base = load_settings(PROJECT_ROOT)
    return base.model_copy(update={"project_root": tmp_path.resolve()})


def _row(*, correction: int, exchange: str = "BATO") -> dict[str, object]:
    return {
        "ticker": module.TARGET_TICKER,
        "underlying_ticker": "ACT",
        "contract_type": "call",
        "expiration_date": module.TARGET_EXPIRATION,
        "strike_price": 45,
        "exercise_style": "american",
        "shares_per_contract": 100,
        "primary_exchange": exchange,
        "cfi": "OCASPS",
        "correction": correction,
        "additional_underlyings": [],
    }


def test_v4_correction_conflict_diagnostic_contract_is_frozen() -> None:
    manifest = module.diagnostic_manifest()

    assert (
        module.HISTORICAL_OPTION_REFERENCE_V4_CORRECTION_CONFLICT_DIAGNOSTIC_FINGERPRINT
        == "54a4436ba1cfee33c6dc3eaabfedd4334c50985d2ee696fab2cc97cfc22620c7"
    )
    assert manifest["parent_v4_contract_fingerprint"] == (
        "2ddeb58d5f552ff0edb87a2244f130b813cf49600f5f82b1f50d8e1ee047a57d"
    )
    assert manifest["target"]["partition"] == "expired-2014-07"
    assert manifest["target"]["ticker"] == "O:ACT2140719C00045000"
    assert manifest["target"]["expiration_date"] == "2014-07-19"
    assert manifest["target"]["strike_price"] == 45
    current = manifest["requests"]["current_structural_list"]
    historical = manifest["requests"]["historical_structural_list"]
    assert current["underlying_filter_intentionally_omitted"] is True
    assert historical["underlying_filter_intentionally_omitted"] is True
    assert manifest["authority"]["bulk_acquisition"] is False
    assert manifest["authority"]["conflict_resolution_rule"] is False
    assert manifest["authority"]["paper_authority"] is False
    assert manifest["authority"]["live_authority"] is False


def test_list_probe_does_not_filter_underlying(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    url = module._list_url(
        settings,
        as_of=module.CURRENT_AS_OF,
        expired=True,
    )

    assert "underlying_ticker=" not in url
    assert "expiration_date=2014-07-19" in url
    assert "strike_price=45" in url
    assert "contract_type=call" in url
    assert "as_of=2026-09-19" in url


def test_current_probe_preserves_same_explicit_correction_conflict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    left = _row(correction=2, exchange="BATO")
    right = _row(correction=2, exchange="XMIO")

    def fake_request(_settings, *, url: str, api_key: str, **_kwargs):
        assert api_key == "token"
        return 200, {
            "status": "OK",
            "request_id": "rid",
            "results": [left, right],
        }

    monkeypatch.setattr(module, "_request_json", fake_request)

    section = module._request_list_twice(
        settings,
        api_key="token",
        as_of=module.CURRENT_AS_OF,
        expired=True,
    )

    assert section["stable"] is True
    first = section["attempts"][0]
    assert first["target_row_count"] == 2
    assert first["target_correction_values"] == [2]
    assert first["target_correction_present_count"] == 2
    assert section["field_differences"] == {
        "primary_exchange": ["BATO", "XMIO"]
    }


def test_run_reports_historical_exact_match_without_authorizing_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    left = _row(correction=2, exchange="BATO")
    historical = _row(correction=2, exchange="XMIO")

    monkeypatch.setenv(settings.massive.credentials.api_key_env, "token")

    def fake_request(
        _settings,
        *,
        url: str,
        api_key: str,
        accepted_http_statuses=frozenset(),
    ):
        assert api_key == "token"
        if "/O%3AACT2140719C00045000?" in url:
            return 200, {
                "status": "OK",
                "request_id": "overview",
                "results": historical,
            }
        if "as_of=2014-07-18" in url:
            return 200, {
                "status": "OK",
                "request_id": "historical-list",
                "results": [historical],
            }
        return 200, {
            "status": "OK",
            "request_id": "current-list",
            "results": [left, historical],
        }

    monkeypatch.setattr(module, "_request_json", fake_request)

    report = module.run_historical_option_reference_v4_correction_conflict_diagnostic(
        settings
    )
    interpretation = report["interpretation"]

    assert interpretation["current_list_conflict_reproduced"] is True
    assert interpretation["all_current_target_rows_have_explicit_correction"] is True
    assert interpretation["current_target_rows_share_one_correction_value"] is True
    assert interpretation["historical_list_target_row_count"] == 1
    assert (
        interpretation["historical_overview_matches_historical_list_row"] is True
    )
    assert (
        interpretation["historical_overview_matches_exactly_one_current_row"] is True
    )
    assert (
        interpretation["diagnostic_only_no_resolution_rule_authorized"] is True
    )
    assert report["authority"]["conflict_resolution_rule"] is False
