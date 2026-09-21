from __future__ import annotations

from pathlib import Path

import pytest

import packages.data.historical_option_reference_v3_underlying_conflict_diagnostic as module
from packages.core.settings import load_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _settings(tmp_path: Path):
    base = load_settings(PROJECT_ROOT)
    return base.model_copy(update={"project_root": tmp_path.resolve()})


def _row(*, underlying: str) -> dict[str, object]:
    return {
        "ticker": module.TARGET_TICKER,
        "underlying_ticker": underlying,
        "contract_type": "call",
        "expiration_date": module.TARGET_EXPIRATION,
        "strike_price": 1,
        "exercise_style": "american",
        "shares_per_contract": 100,
        "primary_exchange": "XBOX",
        "cfi": "OCASPS",
        "additional_underlyings": [],
    }


def test_underlying_conflict_diagnostic_contract_is_frozen() -> None:
    manifest = module.diagnostic_manifest()

    assert (
        module.HISTORICAL_OPTION_REFERENCE_V3_UNDERLYING_CONFLICT_DIAGNOSTIC_FINGERPRINT
        == "aaf0a8e52fdd56521fe000dc1ead04059115d2639b18eb29fad03b8fe76eaec1"
    )
    assert manifest["parent_v3_contract_fingerprint"] == (
        "7a9dab85c57bbc6cd93dee2472a9244d86e8c1776f986cd97036b9963bc4c48e"
    )
    assert manifest["target"]["ticker"] == "O:ACHI140621C00001000"
    assert manifest["target"]["observed_failure"] == (
        "UNVERSIONED_SAME_TICKER_ROWS_DIFFER_IN_UNDERLYING_TICKER"
    )
    current = manifest["requests"]["current_structural_list"]
    historical = manifest["requests"]["historical_structural_list"]
    assert current["underlying_filter_intentionally_omitted"] is True
    assert historical["underlying_filter_intentionally_omitted"] is True
    assert manifest["authority"]["bulk_acquisition"] is False
    assert manifest["authority"]["conflict_resolution_rule"] is False
    assert manifest["authority"]["paper_authority"] is False
    assert manifest["authority"]["live_authority"] is False


def test_option_list_probe_does_not_filter_underlying(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    url = module._list_url(
        settings,
        as_of=module.CURRENT_AS_OF,
        expired=True,
    )

    assert "underlying_ticker=" not in url
    assert "expiration_date=2014-06-21" in url
    assert "strike_price=1" in url
    assert "contract_type=call" in url
    assert "as_of=2026-09-19" in url


def test_current_structural_probe_preserves_both_underlying_identities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    left = _row(underlying="AH")
    right = _row(underlying="ACHI")

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
    assert first["target_underlying_tickers"] == ["ACHI", "AH"]
    assert section["field_differences"] == {
        "underlying_ticker": ["AH", "ACHI"]
    }


def test_stock_identity_context_can_record_plan_limited_403(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)

    def fake_request(
        _settings,
        *,
        url: str,
        api_key: str,
        accepted_http_statuses=frozenset(),
    ):
        assert accepted_http_statuses == frozenset({403, 404})
        return 403, {
            "status": "NOT_AUTHORIZED",
            "request_id": "stock-plan-limited",
            "message": "not entitled",
        }

    monkeypatch.setattr(module, "_request_json", fake_request)

    section = module._request_stock_identity_twice(
        settings,
        api_key="token",
        ticker="AH",
        as_of=module.HISTORICAL_AS_OF,
        active=True,
    )

    assert section["stable"] is True
    first = section["attempts"][0]
    assert first["http_status"] == 403
    assert first["row_count"] == 0


def test_underlying_candidates_include_list_and_overview_rows() -> None:
    values = module._underlying_candidates(
        [_row(underlying="AH")],
        [_row(underlying="ACHI")],
        [{"ticker": module.TARGET_TICKER, "underlying_ticker": "RCM"}],
    )
    assert values == ["ACHI", "AH", "RCM"]
