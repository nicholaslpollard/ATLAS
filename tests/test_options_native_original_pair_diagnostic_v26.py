from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from packages.data.options_native_original_pair_diagnostic_v26 import (
    CONTRACT, FEE_GRID, PairDiagnosticError, _evaluate_cohort, _pair_observations,
    _stats, _read_verified_exit_source, register_outcome_inspection_trial,
    TRIAL_ID, TRIAL_LEDGER_REL,
)
from packages.data.options_native_pilot_accelerated_readiness_v1 import (
    _exit_at_time_query, _exit_review_sessions,
)

ET = ZoneInfo("America/New_York")
ENTRY = date(2025, 1, 6)
EXP = date(2025, 2, 14)


def quote(day: date, right: str, *,
          bid: str = "2.00", ask: str = "2.05",
          seconds_ago: int = 10, strike: str = "590.00",
          bid_size: int = 1, ask_size: int = 1,
          expiration: date = EXP):
    cutoff = datetime.combine(day, datetime.strptime("10:00", "%H:%M").time(), ET)
    return {
        "expiration": expiration.isoformat(), "strike": strike,
        "right": right, "timestamp": (cutoff - timedelta(seconds=seconds_ago)).isoformat(),
        "bid": bid, "ask": ask, "bid_size": bid_size, "ask_size": ask_size,
    }


def pairs(day: date, *, call_bid="2.50", put_bid="2.20"):
    return [
        quote(day, "call", bid=call_bid, ask="2.60"),
        quote(day, "put", bid=put_bid, ask="2.30"),
    ]


def test_entry_and_exit_pair_screen_preserve_original_contract_identity():
    opening = _pair_observations(pairs(ENTRY), ENTRY, entry=True)
    closing = _pair_observations(pairs(date(2025, 1, 7)), date(2025, 1, 7), entry=False)
    assert list(opening) == list(closing)
    assert len(opening) == 1
    key = next(iter(opening))
    assert opening[key]["entry_ask"] == Decimal("4.90")
    assert closing[key]["exit_bid"] == Decimal("4.70")


def test_expiry_entry_band_differs_from_post_entry_review_band():
    d = date(2025, 2, 3)
    # 11 DTE cannot be newly entered under frozen 30..45 DTE.
    assert _pair_observations(pairs(d), d, entry=True) == {}
    assert len(_pair_observations(pairs(d), d, entry=False)) == 1


def test_age_skew_spread_size_and_future_quote_censor_without_fabricated_fill():
    assert not _pair_observations([
        quote(ENTRY, "call", seconds_ago=10),
        quote(ENTRY, "put", seconds_ago=12),
    ], ENTRY, entry=True)
    assert not _pair_observations([
        quote(ENTRY, "call", seconds_ago=31),
        quote(ENTRY, "put", seconds_ago=31),
    ], ENTRY, entry=True)
    assert not _pair_observations([
        quote(ENTRY, "call", bid="1.00", ask="2.00"),
        quote(ENTRY, "put"),
    ], ENTRY, entry=True)
    assert not _pair_observations([
        quote(ENTRY, "call", ask_size=0),
        quote(ENTRY, "put"),
    ], ENTRY, entry=True)
    with pytest.raises(PairDiagnosticError, match="QUOTE_CLOCK_AFTER_REVIEW"):
        _pair_observations([
            quote(ENTRY, "call", seconds_ago=-1),
            quote(ENTRY, "put"),
        ], ENTRY, entry=True)


def test_missing_exit_quotes_are_not_retroactive_entry_veto():
    first_review = _exit_review_sessions(ENTRY)[0]
    first_request = _exit_at_time_query(first_review)
    entries = [{"query_id": "entryA", "date_et": ENTRY.isoformat()}]
    queried = []

    def source_reader(query_id, _row):
        queried.append(query_id)
        if query_id == "entryA":
            return "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC", pairs(ENTRY)
        if query_id == first_request["query_id"]:
            return "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC", pairs(first_review)
        return "EXPLICIT_NO_DATA_SOURCE_ONLY", None

    report = _evaluate_cohort(entries, source_reader)
    assert report["entries_evaluated"] == 1
    assert report["entry_pairs_screened"] == 1
    assert report["five_session_review_uses_reached"] == 5
    assert report["matched_pair_review_observations"] == 1
    assert report["review_source_states"]["EXPLICIT_NO_DATA_SOURCE_ONLY"] == 4
    assert len(queried) == 6
    fees = report["fee_sensitivity_per_contract_per_side"]
    assert set(fees) == set(FEE_GRID)
    assert fees["0.00"]["observations"] == 1
    assert fees["1.30"]["mean_pct"] < fees["0.00"]["mean_pct"]
    assert report["by_entry_year"]["2025"]["matched"] == 1


def test_no_tradable_pair_produces_explicitly_null_economic_summary():
    def source_reader(qid, _row):
        if qid == "entryA":
            return "LEGACY_2025_EXTERNALLY_SAVED_UNADMITTED", None
        return "EXPLICIT_NO_DATA_SOURCE_ONLY", None

    report = _evaluate_cohort(
        [{"query_id": "entryA", "date_et": ENTRY.isoformat()}], source_reader,
    )
    assert report["entry_pairs_screened"] == 0
    assert report["matched_pair_review_observations"] == 0
    assert report["missing_entry_source_states"] == {
        "LEGACY_2025_EXTERNALLY_SAVED_UNADMITTED": 1,
    }
    assert _stats([])["mean_pct"] is None


def test_original_positive_crossed_quote_fails_not_silently_selects_winner():
    with pytest.raises(PairDiagnosticError, match="QUOTE_CROSSED"):
        _pair_observations([
            quote(ENTRY, "call", bid="3.0", ask="2.0"),
            quote(ENTRY, "put"),
        ], ENTRY, entry=True)


def test_source_reader_is_separate_from_provider_and_account_replay():
    # The V26 read-only source module may import evidence readers but may not
    # launch paid collection, promote sources, or generate execution receipts.
    import inspect
    import packages.data.options_native_original_pair_diagnostic_v26 as v26
    text = inspect.getsource(v26)
    assert "option_at_time_quote_surface(" not in text
    assert "run_exit_campaign(" not in text
    assert "replay_synthetic_account(" not in text
    assert CONTRACT.startswith("atlas-spy-quote-pair")


def test_outcome_inspection_is_preregistered_once_before_option_price_review(tmp_path):
    from packages.performance.ledger import StrategyTrialLedger

    class Settings:
        def assert_external_storage_binding(self, name):
            assert name == "options"

        def resolved_path(self, relative):
            assert relative == TRIAL_LEDGER_REL
            return tmp_path / "trials.jsonl"

    settings = Settings()
    first = register_outcome_inspection_trial(settings)
    assert len(first["newly_registered"]) == 2
    assert TRIAL_ID in first["trial_ids"]
    second = register_outcome_inspection_trial(settings)
    assert second["newly_registered"] == []
    records = StrategyTrialLedger(settings.resolved_path(TRIAL_LEDGER_REL)).read()
    assert len(records) == 2
    assert all(not r.performance_outcomes_opened for r in records)
    assert all(r.master_protected_return_rows_read == 0 for r in records)
    assert not first["qualifying_historical_authority"]
