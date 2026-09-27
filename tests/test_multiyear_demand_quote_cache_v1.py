from __future__ import annotations

"""Synthetic no-network cache/dedup and hard provider-credit safety tests."""

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import packages.data.multiyear_demand_quote_cache_v1 as m


ASOF = datetime(2026, 9, 27, 20, 25, tzinfo=UTC)
LAST = date(2026, 9, 25)


def _case(year, number=0, decision_day=2):
    return {
        "case_id": f"{year}-{number}", "ticker": "TEST",
        "option_symbol": f"TEST{str(year)[2:]}0318C00100000",
        "right": "call", "expiration": f"{year}-03-18",
        "decision_at_utc": f"{year}-03-{decision_day:02d}T14:35:00+00:00",
        "selected_at_utc": f"{year}-03-{decision_day:02d}T14:34:00+00:00",
        "accepted_stock_source_sha256": "a" * 64,
    }


def _settings(tmp_path):
    return SimpleNamespace(
        resolved_path=lambda path: tmp_path / path,
        assert_external_storage_binding=lambda name:
            None if name == "options" else pytest.fail("wrong binding"),
    )


def _response(ticket, consumed=1, remaining=1700):
    timestamp = int(datetime(2023, 3, 3, 21, tzinfo=UTC).timestamp())
    raw = json.dumps({
        "s": "ok", "optionSymbol": [ticket["option_symbol"]],
        "updated": [timestamp], "bid": [1.0], "ask": [1.2],
        "last": [1.1], "volume": [5], "openInterest": [10],
        "underlyingPrice": [100.0],
    }).encode()
    headers = {
        "X-Api-Ratelimit-Consumed": str(consumed),
        "X-Api-Ratelimit-Remaining": str(remaining),
    }
    return 200, raw, headers


def test_six_year_demand_preserves_gap_and_deduplicates_physical_quote_queries():
    selected = [
        _case(2021, 1, 2), _case(2022, 1), _case(2022, 2),
        _case(2023), _case(2024), _case(2025),
        {**_case(2026), "option_symbol": "TEST261016C00100000",
         "expiration": "2026-10-16", "decision_at_utc": "2026-09-24T13:35:00+00:00",
         "selected_at_utc": "2026-09-24T13:34:00+00:00"},
    ]
    # 2021-03 original decision is outside Starter entitlement; 2026
    # October expiry is not yet complete, so quote to last closed day only.
    plan = m.freeze_quote_demand(selected, asof_utc=ASOF, last_completed_session=LAST)
    assert plan["requested_case_denominator"] == 7
    assert plan["unique_physical_quote_queries"] == 5
    assert [r["disposition"] for r in plan["memberships"]].count(
        "ORIGINAL_DECISION_OUTSIDE_STARTER_FIVE_YEAR_WINDOW") == 1
    assert len([r for r in plan["requests"] if r["from_inclusive"] == "2022-01-01"]) == 1
    current = next(r for r in plan["requests"] if r["option_symbol"].startswith("TEST261016"))
    assert current["to_exclusive"] == "2026-09-26"
    assert plan["provider_requests"] == 0 and plan["strategy_authority"] is False


def test_future_selected_option_cannot_be_backfilled():
    altered = _case(2023)
    altered["selected_at_utc"] = "2023-03-02T14:36:00+00:00"
    with pytest.raises(m.MultiYearQuoteCacheError, match="predecision"):
        m.freeze_quote_demand([altered], asof_utc=ASOF, last_completed_session=LAST)
    altered = _case(2023)
    altered["option_symbol"] = "TEST230318P00100000"
    with pytest.raises(m.MultiYearQuoteCacheError, match="predecision"):
        m.freeze_quote_demand([altered], asof_utc=ASOF, last_completed_session=LAST)


def test_preview_does_not_contact_provider_and_paid_requires_credit_reserve(tmp_path, monkeypatch):
    plan = m.freeze_quote_demand([_case(2023)], asof_utc=ASOF, last_completed_session=LAST)
    s = _settings(tmp_path)
    called = []
    report = m.run_demand_cache(
        s, plan, transport=lambda *a: called.append(1) or pytest.fail("network"),
    )
    assert report["pending"] == 1 and report["new_provider_attempts"] == 0
    assert called == [] and report["status"] == "PREVIEW_ONLY_NO_PROVIDER_GETS"
    with pytest.raises(m.MultiYearQuoteCacheError, match="500-credit"):
        m.run_demand_cache(
            s, plan, max_new_requests=2, max_observed_credits=200,
            authorize_provider=True, confirm_paid_starter=True,
            confirm_private_internal_use=True, token="test", user_asserted_remaining=600,
            transport=lambda *a: pytest.fail("must refuse before network"),
        )


def test_paid_single_get_creates_reusable_exact_receipt_and_no_replay(tmp_path, monkeypatch):
    plan = m.freeze_quote_demand([_case(2023)], asof_utc=ASOF, last_completed_session=LAST)
    s = _settings(tmp_path)
    monkeypatch.setattr(m, "_require_external", lambda settings: None)
    monkeypatch.setattr(m, "assert_category_acquisition_allowed", lambda *a, **kw: None)
    called = []
    def transport(ticket, token):
        called.append(ticket["request_identity"])
        assert token == "test"
        return _response(ticket)
    result = m.run_demand_cache(
        s, plan, max_new_requests=1, max_observed_credits=2,
        authorize_provider=True, confirm_paid_starter=True,
        confirm_private_internal_use=True, token="test",
        user_asserted_remaining=1700, transport=transport,
    )
    assert result["new_provider_attempts"] == 1
    assert result["observed_credits"] == 1
    assert result["new_cache_complete"] == 1 and result["pending"] == 0
    assert called == [plan["requests"][0]["request_identity"]]
    cached = m.run_demand_cache(s, plan, transport=lambda *a: pytest.fail("replay forbidden"))
    assert cached["new_cache_complete"] == 1 and cached["pending"] == 0
    assert cached["new_provider_attempts"] == 0
    path = m._path(s, plan["requests"][0])[0]
    path.write_bytes(b"changed")
    with pytest.raises(m.MultiYearQuoteCacheError, match="lineage"):
        m.run_demand_cache(s, plan, transport=lambda *a: pytest.fail("tampered"))


def test_provider_uncertainty_preserves_intent_and_paid_lock(tmp_path, monkeypatch):
    plan = m.freeze_quote_demand([_case(2023)], asof_utc=ASOF, last_completed_session=LAST)
    s = _settings(tmp_path)
    monkeypatch.setattr(m, "_require_external", lambda settings: None)
    monkeypatch.setattr(m, "assert_category_acquisition_allowed", lambda *a, **kw: None)
    def uncertain(*a):
        raise TimeoutError("simulated prior attempt uncertain")
    with pytest.raises(m.MultiYearQuoteCacheError, match="preserved original"):
        m.run_demand_cache(
            s, plan, max_new_requests=1, max_observed_credits=1,
            authorize_provider=True, confirm_paid_starter=True,
            confirm_private_internal_use=True, token="test",
            user_asserted_remaining=1700, transport=uncertain,
        )
    assert m._path(s, plan["requests"][0])[2].is_file()
    assert (tmp_path / "data/options/manifests/.multiyear_paid_get.lock").is_file()
    with pytest.raises(m.MultiYearQuoteCacheError, match="unresolved"):
        m.run_demand_cache(s, plan)


def test_reuse_accepted_2022_stores_no_second_raw_copy(tmp_path, monkeypatch):
    plan = m.freeze_quote_demand([_case(2022)], asof_utc=ASOF, last_completed_session=LAST)
    s = _settings(tmp_path)
    old = {
        "option_symbol": plan["requests"][0]["option_symbol"],
        "from_inclusive": "2022-01-01", "to_exclusive": "2022-03-19",
        "request_identity": "a" * 64,
    }
    monkeypatch.setattr(m, "OfflineOptionHistoryStore", lambda settings: SimpleNamespace(
        settings=settings, _tickets={old["option_symbol"]: old},
        plan_fingerprint="b" * 64,
    ))
    monkeypatch.setattr(m, "old_2022_receipt", lambda settings, ticket: {
        "status": "COMPLETE_SOURCE_ONLY",
        "body_sha256": hashlib.sha256(b"old-original").hexdigest(),
        "safe_summary": {"observed_rows": 2},
    })
    result = m.run_demand_cache(
        s, plan, transport=lambda *a: pytest.fail("must reuse old 2022"),
    )
    assert result["reused_original_2022"] == 1
    assert result["new_provider_attempts"] == 0
    assert result["pending"] == 0
