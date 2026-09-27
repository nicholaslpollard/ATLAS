from __future__ import annotations

"""Test original-native all-year stock marks with zero provider/2026 access."""

from datetime import UTC, date, timedelta
from types import SimpleNamespace

import pytest

import packages.data.multiyear_native_stock_open_v1 as m
from packages.core.market_calendar import get_market_calendar
from packages.data.multiyear_accepted_stock_census_v1 import freeze_development_census
from packages.data.multiyear_stock_news_source_v1 import join_stock_pit_news


def _selected(session: date, ident: str):
    calendar = get_market_calendar()
    next_session = calendar.sessions_in_range(
        session + timedelta(days=1), session + timedelta(days=9)
    )[0]
    _, decision = calendar.regular_open_close(session)
    entry, _ = calendar.regular_open_close(next_session)
    return SimpleNamespace(
        opportunity_id=ident, ticker="TEST", instrument_id="instrument-TEST",
        policy_id="original-policy", economic_family_id="family",
        fold_id=7, native_timeframe="1d", direction="LONG",
        signal_session=session, decision_utc=decision, entry_utc=entry,
        source_analysis_fingerprint="a" * 64, primary_net_return=9999.0,
        gross_return=-222.0,
    )


class FakeNews:
    lineage = {"accepted_v2_fingerprint": "c" * 64}
    coverage_end = date(2026, 9, 19)
    scanned_articles = 100
    duplicate_article_rows = 0
    def prior_counts(self, ticker, *, decision_utc):
        return {
            "coverage_status": "VERIFIED_SOURCE_COVERAGE_AT_DECISION",
            "unique_articles_available_prior_24h": 0,
            "unique_articles_available_prior_7d": 1,
        }


def _sources():
    items = [
        _selected(date(2021, 10, 1), "early"),
        _selected(date(2022, 3, 1), "middle"),
        _selected(date(2025, 12, 31), "late2025"),
    ]
    source = {
        "selected_opportunity_count": len(items),
        "source_integrity_fingerprint": "b" * 64,
        "conditioning_analysis_fingerprint": "a" * 64,
    }
    census = freeze_development_census(
        items, source, expiry_rule=lambda day: day + timedelta(days=35)
    )
    joined = join_stock_pit_news(census, FakeNews())
    return census, joined


def _raw(project_root, proxies, *, progress):
    assert len(proxies) == 2
    assert {x.opportunity_id for x in proxies} == {"early", "middle"}
    assert all(x.entry_utc.year <= 2025 for x in proxies)
    assert all(not hasattr(x, "primary_net_return") for x in proxies)
    progress("NATIVE_RAW_UNIT_VERIFIED", {"verified_units": 1, "total_units": 1})
    return {"early": 42.5, "middle": 101.1}, {
        "protected_master_return_rows_read": 0,
        "source_fingerprint": "f" * 64,
        "native_raw_source": {
            "verified_native_raw_unit_count": 1,
            "verified_native_raw_unit_bindings": [
                {"unit_id": "original-unit", "year": 2021, "canonical_sha256": "d" * 64}
            ],
        },
    }


def test_all_cases_retained_raw_unadjusted_early_and_late_gap(tmp_path):
    census, joined = _sources()
    stages = []
    result = m.attach_native_raw_open(
        census, joined, project_root=tmp_path, reader=_raw,
        progress=stages.append
    )
    assert result["case_denominator"] == 3
    assert result["verified_native_raw_open_cases"] == 2
    assert result["deferred_2026_entry_cases"] == 1
    assert result["provider_requests"] == result["protected_outcomes_read"] == 0
    assert result["native_units_verified"] == 1
    assert [r["case_id"] for r in result["rows"]] == [
        x["case_id"] for x in census["cases"]
    ]
    assert result["rows"][0]["raw_underlying_price"] == "42.5"
    assert result["rows"][1]["raw_underlying_price"] == "101.1"
    assert result["rows"][2]["raw_underlying_price"] is None
    assert result["rows"][2]["native_source_status"] == (
        "DEFERRED_ENTRY_2026_NATIVE_SOURCE_NOT_READ"
    )
    assert result["rows"][0]["underlying_price_basis"] == "RAW_AS_TRADED_NATIVE_1DAY_OPEN"
    assert result["rows"][0]["option_symbol"] is None
    assert result["rows"][0]["raw_open_is_not_09_35_trade_or_fill"]
    assert result["rows"][0]["prior_7d_news_articles"] == 1
    assert any(x["stage"] == "NATIVE_RAW_UNIT_VERIFIED" for x in stages)
    assert all(x.get("provider_requests") == 0 for x in stages)

    settings = SimpleNamespace(resolved_path=lambda path: tmp_path / path)
    path, action = m.write_native_source(settings, census, joined, result)
    assert path.is_file() and action.startswith("WRITTEN")
    assert m.inspect_existing_native_source(settings, census, joined) == result
    assert m.write_native_source(settings, census, joined, result)[1].startswith("REUSED")
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(m.MultiYearRawStockError, match="unreadable"):
        m.inspect_existing_native_source(settings, census, joined)


def test_incomplete_source_refused_without_fallback(tmp_path):
    census, joined = _sources()
    def missing(*args, **kwargs):
        return {"early": 10.0}, {
            "protected_master_return_rows_read": 0,
            "native_raw_source": {
                "verified_native_raw_unit_count": 1,
                "verified_native_raw_unit_bindings": [{"unit_id": "x"}],
            },
        }
    with pytest.raises(m.MultiYearRawStockError, match="coverage"):
        m.attach_native_raw_open(census, joined, project_root=tmp_path,
                                 reader=missing)
    def bad(*args, **kwargs):
        raw, source = _raw(*args, **kwargs)
        source["protected_master_return_rows_read"] = 1
        return raw, source
    with pytest.raises(m.MultiYearRawStockError, match="coverage"):
        m.attach_native_raw_open(census, joined, project_root=tmp_path, reader=bad)


def test_native_source_builder_reuses_accepted_stock_news_and_derived(tmp_path, monkeypatch):
    census, joined = _sources()
    settings = SimpleNamespace(
        project_root=tmp_path,
        resolved_path=lambda p: tmp_path / p,
        assert_external_storage_binding=lambda name:
            None if name == "research_evidence" else pytest.fail("unexpected binding"),
    )
    monkeypatch.setattr(
        m, "build_stock_news_source",
        lambda *args, **kwargs: (census, joined, tmp_path / "accepted.json",
                                 "REUSED_VERIFIED_FEATURE_SOURCE_NO_NEWS_RESCAN"),
    )
    calls = []
    def project(*args, **kwargs):
        calls.append("native")
        return m.attach_native_raw_open(
            census, joined, project_root=tmp_path, reader=_raw
        )
    monkeypatch.setattr(m, "attach_native_raw_open", project)
    # The wrapper itself is not used recursively: seed the original result
    # with the unpatched helper would be unnecessary for this reuse check.
    def source(*args, **kwargs):
        calls.append("native")
        return {
            "contract": m.CONTRACT, "case_denominator": 3,
            "native_units_verified": 1, "rows": [],
        }
    monkeypatch.setattr(m, "attach_native_raw_open", source)
    monkeypatch.setattr(
        m, "write_native_source",
        lambda settings, census, joined, report:
            (tmp_path / "saved.json", "WRITTEN_NEW_NATIVE_RAW_STOCK_OPEN_SOURCE"),
    )
    first = m.build_multiyear_native_raw_open_source(settings)
    assert first[2] == "WRITTEN_NEW_NATIVE_RAW_STOCK_OPEN_SOURCE"
    assert calls == ["native"]
