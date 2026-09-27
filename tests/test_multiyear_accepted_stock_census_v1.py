from __future__ import annotations

"""No-network source-only six-year selected-signal census tests."""

from datetime import UTC, date, timedelta
from types import SimpleNamespace

import pytest

import packages.data.multiyear_accepted_stock_census_v1 as m
from packages.core.market_calendar import get_market_calendar
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint


ANALYSIS = "a" * 64
SOURCE = "b" * 64


def _item(year, *, signal=None, ident=None, timeframe="1d", direction="LONG"):
    cal = get_market_calendar()
    signal = signal or date(year, 3, 1)
    assert cal.is_session(signal)
    next_session = cal.sessions_in_range(signal + timedelta(days=1),
                                         signal + timedelta(days=8))[0]
    _, signal_close = cal.regular_open_close(signal)
    entry_open, _ = cal.regular_open_close(next_session)
    return SimpleNamespace(
        opportunity_id=ident or f"case-{year}", ticker="TEST",
        instrument_id=f"instrument-{year}", policy_id="accepted-policy",
        economic_family_id="accepted-family", fold_id=year,
        native_timeframe=timeframe, direction=direction, signal_session=signal,
        decision_utc=signal_close, entry_utc=entry_open,
        source_analysis_fingerprint=ANALYSIS,
        primary_net_return=-123.0, gross_return=9999.0,
    )


def _source(items):
    return {
        "selected_opportunity_count": len(items),
        "source_integrity_fingerprint": SOURCE,
        "conditioning_analysis_fingerprint": ANALYSIS,
    }


def _expiry(day):
    return day + timedelta(days=35)


def test_2021_to_2025_actual_selection_and_2026_gap_visible_without_returns(tmp_path):
    items = [
        _item(2021, signal=date(2021, 10, 1)),
        _item(2022), _item(2023), _item(2024), _item(2025),
        _item(2025, signal=date(2025, 12, 31), ident="last-session"),
        _item(2023, ident="intraday-rejected", timeframe="1m"),
        _item(2024, ident="short-rejected", direction="SHORT"),
    ]
    progress = []
    result = m.freeze_development_census(
        items, _source(items), expiry_rule=_expiry, progress=progress.append
    )
    assert result["original_selected_source_count"] == 8
    assert result["daily_long_case_denominator"] == 6
    assert all(result["by_year"][str(year)]["accepted_development_daily_long_signals"] >= 1
               for year in range(2021, 2026))
    assert result["by_year"]["2026"]["accepted_development_daily_long_signals"] == 0
    assert result["by_year"]["2026"]["source_authority"].startswith(
        "NEEDS_SEPARATE_PROSPECTIVE"
    )
    assert result["source_statuses"]["NEEDS_SEPARATE_2026_NATIVE_SOURCE"] == 1
    assert result["provider_requests"] == result["protected_outcomes_read"] == 0
    assert result["authority"]["option_contract_selected"] is False
    assert result["original_timeframe_counts"] == {"1d": 7, "1m": 1}
    for row in result["cases"]:
        assert row["native_raw_entry_open"] is None
        assert row["selected_option_symbol"] is None
        assert "gross_return" not in row and "primary_net_return" not in row
        assert "selector_score" not in row
        assert row["no_outcome_or_return_fields_projected"] is True
    settings = SimpleNamespace(resolved_path=lambda path: tmp_path / path)
    path, action = m.write_development_census(settings, result)
    assert path.is_file() and action == "WRITTEN_NEW_ACCEPTED_SIGNAL_CENSUS"
    assert m.write_development_census(settings, result)[1].startswith("REUSED")
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(m.MultiYearStockSignalError, match="immutable"):
        m.write_development_census(settings, result)


def test_invalid_selected_fingerprint_and_nonclose_decision_fail_closed():
    item = _item(2023)
    with pytest.raises(m.MultiYearStockSignalError, match="identity"):
        m.freeze_development_census(
            [SimpleNamespace(**{**vars(item), "source_analysis_fingerprint": "z" * 64})],
            _source([item]), expiry_rule=_expiry
        )
    with pytest.raises(m.MultiYearStockSignalError, match="decision/entry clock"):
        m.freeze_development_census(
            [SimpleNamespace(**{**vars(item),
                                "decision_utc": item.decision_utc + timedelta(minutes=1)})],
            _source([item]), expiry_rule=_expiry
        )


def test_expiry_exclusion_preserves_case_and_duplicate_source_denied():
    item = _item(2022)
    def unavailable(day):
        raise m.CandidateStockExportError("no bounded exchange monthly expiry is available")
    result = m.freeze_development_census([item], _source([item]),
                                         expiry_rule=unavailable)
    assert result["daily_long_case_denominator"] == 1
    assert result["cases"][0]["source_status"] == (
        "NO_MONTHLY_EXPIRATION_IN_FROZEN_28_TO_60_DAY_WINDOW"
    )
    assert result["cases"][0]["structural_expiration"] is None
    with pytest.raises(m.MultiYearStockSignalError, match="duplicate"):
        m.freeze_development_census([item, item], _source([item, item]),
                                    expiry_rule=_expiry)


def test_builder_queries_development_once_and_never_2026(tmp_path):
    source = [_item(2021, signal=date(2021, 10, 1)), _item(2024)]
    calls = []
    settings = SimpleNamespace(
        project_root=tmp_path,
        assert_external_storage_binding=lambda name:
            None if name == "research_evidence" else pytest.fail("wrong binding")
    )
    def load(root, **kwargs):
        calls.append((root, kwargs))
        return source, _source(source)
    result = m.build_development_census(settings, loader=load, duckdb_threads=2)
    assert result["by_year"]["2026"]["accepted_development_daily_long_signals"] == 0
    assert len(calls) == 1
    assert calls[0][1] == {
        "start_session": date(2021, 1, 1),
        "end_session": date(2025, 12, 31),
        "duckdb_threads": 2,
    }
