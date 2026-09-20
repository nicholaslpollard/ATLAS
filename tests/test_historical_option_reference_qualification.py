from __future__ import annotations

from pathlib import Path

import pytest

import packages.data.historical_option_reference_qualification as module
from packages.core.settings import load_settings
from packages.data.provider_source_qualification import (
    SOURCE_QUALIFICATION_DIMENSIONS,
    QualificationDimension,
    qualification_dimensions,
    qualification_status,
)


def _settings(tmp_path: Path):
    base = load_settings(Path(__file__).resolve().parents[1])
    return base.model_copy(update={"project_root": tmp_path.resolve()})


def _record(ticker: str) -> dict[str, object]:
    return {
        "ticker": ticker,
        "underlying_ticker": "SPY",
        "contract_type": "call",
        "expiration_date": "2025-01-17",
        "strike_price": 500.0,
        "exercise_style": "american",
        "shares_per_contract": 100,
        "cfi": "OCASPS",
        "primary_exchange": "BATO",
    }


def test_provider_source_qualification_requires_every_dimension() -> None:
    with pytest.raises(ValueError, match="dimensions incomplete"):
        qualification_dimensions(
            [
                QualificationDimension(
                    SOURCE_QUALIFICATION_DIMENSIONS[0],
                    "PASS",
                    "evidence",
                )
            ]
        )

    complete = qualification_dimensions(
        [
            QualificationDimension(name, "PASS", "evidence")
            for name in SOURCE_QUALIFICATION_DIMENSIONS
        ]
    )
    assert qualification_status(complete) == "PASS"

    complete[1] = dict(complete[1], status="LIMITATION")
    assert qualification_status(complete) == "PASS_WITH_LIMITATIONS"

    complete[2] = dict(complete[2], status="FAIL")
    assert qualification_status(complete) == "FAIL"


def test_option_reference_qualification_contract_is_frozen_and_source_only() -> None:
    manifest = module.qualification_manifest()

    assert (
        manifest["fingerprint"]
        == module.HISTORICAL_OPTION_REFERENCE_QUALIFICATION_FINGERPRINT
        == "17a3736f9317f7e403ea08c123aac35fabad0a8b2682bca7450373b797e9d260"
    )
    assert manifest["documented_history_start"] == "2014-06-02"
    assert manifest["documented_semantics"]["expired_default"] is False
    assert manifest["documented_semantics"]["page_limit_max"] == 1000
    assert manifest["source_role_limits"] == {
        "reference_identity_and_structure": True,
        "historical_candidate_availability_authority": False,
        "historical_dynamic_deliverable_authority": False,
        "historical_market_price_authority": False,
        "reason": (
            "REFERENCE_ROWS_DO_NOT_EXPOSE_A_FIRST_LISTED_TIMESTAMP_AND_CURRENT_"
            "REFERENCE_STATE_MAY_REFLECT_LATER_CORRECTIONS"
        ),
    }
    assert manifest["authority"]["bulk_acquisition"] is False
    assert manifest["authority"]["strategy_outcome_access"] is False
    assert manifest["authority"]["paper_authority"] is False
    assert manifest["authority"]["live_authority"] is False


def test_safe_url_removes_credential_query_parameters() -> None:
    safe = module._safe_url(
        "https://api.massive.com/v3/reference/options/contracts"
        "?cursor=abc&apiKey=secret&limit=25"
    )

    assert "secret" not in safe
    assert "apiKey" not in safe
    assert "cursor=abc" in safe
    assert "limit=25" in safe


def test_result_summary_profiles_identity_schema_and_additive_fields() -> None:
    left = _record("O:SPY250117C00500000")
    right = _record("O:SPY250117P00500000")
    right["unexpected_additive_field"] = "seen"

    summary = module._summarize_results([left, right])

    assert summary["result_count"] == 2
    assert summary["distinct_nonempty_tickers"] == 2
    assert summary["duplicate_ticker_rows"] == 0
    assert summary["missing_required_fields"] == {}
    assert summary["unknown_fields"] == ["unexpected_additive_field"]
    assert summary["contract_types"] == ["call"]
    assert summary["results_fingerprint"]


def test_probe_case_follows_provider_next_url_without_ticker_overlap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    calls: list[str] = []
    first_url = (
        "https://api.massive.com/v3/reference/options/contracts"
        "?expiration_date=2025-01-17&limit=25"
    )
    next_url = (
        "https://api.massive.com/v3/reference/options/contracts"
        "?cursor=opaque"
    )

    def _fake_request(_settings, *, url: str, api_key: str):
        assert api_key == "token"
        calls.append(url)
        if len(calls) == 1:
            return 200, {
                "status": "OK",
                "request_id": "one",
                "results": [_record("O:SPY250117C00500000")],
                "next_url": next_url,
            }
        return 200, {
            "status": "OK",
            "request_id": "two",
            "results": [_record("O:SPY250117P00500000")],
        }

    monkeypatch.setattr(module, "_request_json", _fake_request)
    monkeypatch.setattr(
        settings.data.research.options,
        "reference_endpoint_path",
        "/v3/reference/options/contracts",
    )

    report = module._probe_case(
        settings,
        api_key="token",
        case={
            "name": "test",
            "params": {
                "expiration_date": "2025-01-17",
                "limit": 25,
            },
        },
        follow_next_page=True,
        repeat_first_page=False,
    )

    assert calls[0].startswith(first_url)
    assert calls[1] == next_url
    assert report["pages_fetched"] == 2
    assert report["second_page"]["ticker_overlap_with_first_page"] == 0


def test_dimensions_keep_reference_role_pit_limited() -> None:
    def page(count: int = 1) -> dict[str, object]:
        return {
            "result_count": count,
            "distinct_nonempty_tickers": count,
            "duplicate_ticker_rows": 0,
            "missing_required_fields": {},
        }

    probes = [
        {
            "name": "earliest_documented_history_spy",
            "first_page": page(1),
            "next_url_present": False,
        },
        {
            "name": "historical_2016_spy_point_in_time",
            "first_page": page(1),
            "next_url_present": False,
            "repeat_first_page": {"stable": True},
        },
        {
            "name": "historical_2016_spy_expired_current_view",
            "first_page": page(1),
            "next_url_present": False,
        },
        {
            "name": "recent_2026_spy_point_in_time",
            "first_page": page(1),
            "next_url_present": False,
        },
        {
            "name": "broad_pagination_2025_standard_expiry",
            "first_page": page(1),
            "next_url_present": True,
            "second_page": {
                **page(1),
                "ticker_overlap_with_first_page": 0,
            },
        },
    ]

    dimensions = module._dimensions(probes)

    assert qualification_status(dimensions) == "PASS_WITH_LIMITATIONS"
    by_name = {item["name"]: item for item in dimensions}
    assert by_name["POINT_IN_TIME_AVAILABILITY"]["status"] == "LIMITATION"
    assert by_name["ENTITLEMENT_AND_COVERAGE_BOUNDARIES"]["status"] == "PASS"
    assert by_name["PAGINATION_COMPLETENESS"]["status"] == "PASS"
