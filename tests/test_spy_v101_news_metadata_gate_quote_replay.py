from __future__ import annotations
"""V101 source/no-lookahead news filter tests; no provider or broker requests."""
from datetime import UTC, datetime
import gzip
import hashlib
import json

import pytest
from scripts import run_spy_v101_news_metadata_gate_quote_replay as v101

class News:
    def __init__(self, count24, count7, status="VERIFIED_SOURCE_COVERAGE_AT_DECISION"):
        self.n24 = count24
        self.n7 = count7
        self.status = status
        self.seen = []
    def prior_counts(self, ticker, *, decision_utc):
        self.seen.append((ticker, decision_utc))
        return {
            "coverage_status": self.status,
            "unique_articles_available_prior_24h": self.n24,
            "unique_articles_available_prior_7d": self.n7,
            "decision_cutoff_utc": decision_utc.isoformat(),
            "authority": {"provider_requests": 0, "news_text_or_sentiment_alpha": False},
        }


def test_original_et_clock_uses_only_historical_utc_cutoff():
    news = News(1,3)
    record = v101.gate_decision("2022_full", "2022-06-01T09:40:01-04:00", "q", news)
    assert news.seen == [("SPY", datetime(2022,6,1,13,40,1,tzinfo=UTC))]
    assert record["status"] == "QUALIFIED_NEWS_METADATA"
    assert v101.passes("NEWS_24H_AT_LEAST_1", record) is True
    assert v101.passes("NEWS_7D_AT_LEAST_3", record) is True
    assert v101.passes("NEWS_24H_ZERO", record) is False


def test_verified_zero_articles_is_not_missing_news():
    record = v101.gate_decision("2021_full", "2021-01-04T09:35:01-05:00", "q", News(0,0))
    assert v101.passes("NEWS_24H_ZERO", record) is True
    assert v101.passes("NEWS_24H_AT_LEAST_1", record) is False
    assert v101.passes("NEWS_7D_AT_LEAST_3", record) is False


def test_unknown_source_must_not_become_a_quiet_news_signal():
    record = v101.gate_decision("2024_full", "2024-01-02T09:35:01-05:00", "q",
                                News(None,None,"NEWS_SOURCE_NOT_ACQUIRED_THROUGH_DECISION"))
    assert record["status"] == "NEWS_SOURCE_NOT_ASOF_QUALIFIED"
    assert all(v101.passes(g,record) is None for g in v101.GATES)


def test_2020_original_has_no_qualified_news_and_no_spurious_reader_call():
    reader = News(0,0)
    record = v101.gate_decision("2020_SOURCE_PARTIAL","2020-04-09T09:35:01-04:00","q",reader)
    assert reader.seen == []
    assert record["status"] == "NEWS_SOURCE_OUTSIDE_VERIFIED_YEAR_SCOPE"
    assert v101.passes("NEWS_24H_ZERO",record) is None


@pytest.mark.parametrize("period,stamp", [
    ("2022_full","2023-06-01T09:35:01-04:00"),
    ("2025_h2","2025-06-30T09:35:01-04:00"),
    ("2026_janapr","2026-05-12T09:35:01-04:00"),
    ("2021_full","2021-01-01T09:35:01"),
])
def test_other_year_precohort_protected_and_naive_clocks_rejected(period,stamp):
    with pytest.raises(v101.V101Error,match="CLOCK"):
        v101.gate_decision(period,stamp,"q",News(1,3))


def test_news_count_quality_rejects_negative_boolean_null_and_inconsistent():
    for x,y in ((-1,2),(3,2),(True,2),(None,4)):
        with pytest.raises(v101.V101Error,match="COUNT"):
            v101.gate_decision("2022_full","2022-06-01T09:35:01-04:00","q",News(x,y))


def test_original_trial_exit_sha_parent_and_full_24_variant_grid():
    class V100:
        @staticmethod
        def check(item):
            assert item["fingerprint"].startswith("sig")
            return item
    groups=[]
    for policy in ("control_50_100","balanced_35_100","runner_35_150"):
        for lag in (1,3):
            trial={"fingerprint":f"sig-{policy}-{lag}","session":"2022-02-02",
                   "strategy":"impulse_0935","policy":policy,"lag_seconds":lag,
                   "actual_broker_fills":0}
            checks=[{"fingerprint":f"sig-{policy}-{lag}-{dwell}",
                     "original_trial_sha":trial["fingerprint"],
                     "session":trial["session"],"strategy":trial["strategy"],
                     "policy":policy,"lag_seconds":lag,
                     "limit_rest_seconds":dwell,"actual_broker_fills":0}
                    for dwell in (0,3,10,30)]
            groups.append({"original_v84_trial":trial,"original_v86_exit_rechecks":checks})
    assert len(v101.original_pairs({"original_24_variant_economic_trials":groups},v100=V100))==24
    groups[0]["original_v86_exit_rechecks"][0]["original_trial_sha"]="sig-wrong"
    with pytest.raises(v101.V101Error,match="PARENT"):
        v101.original_pairs({"original_24_variant_economic_trials":groups},v100=V100)


def test_new_original_evidence_is_signed_gzipped_and_immutable(tmp_path):
    class V100:
        @staticmethod
        def _fingerprint(item):
            return hashlib.sha256(json.dumps(item,sort_keys=True).encode()).hexdigest()
    path=tmp_path/"report.json.gz"
    receipt=v101.signed_write(path,{"contract":"test","value":2},V100)
    raw=path.read_bytes()
    obj=json.loads(gzip.decompress(raw))
    assert obj["fingerprint"]==receipt["signed_fingerprint"]
    assert hashlib.sha256(raw).hexdigest()==receipt["sha256"]
    with pytest.raises(FileExistsError):
        v101.signed_write(path,{"contract":"test"},V100)


def test_hypothetical_comparison_is_news_covered_years_only():
    assert v101.NEWS_PERIODS == (
        "2021_full","2022_full","2023_full","2024_full","2025_h2","2026_janapr")
    assert len(v101.GATES)==3


def test_protected_master_holdout_partitions_not_opened_by_v101_source_reader(monkeypatch):
    from packages.data import offline_multiyear_news_context_v1 as news
    scanned = []
    def read_months(settings, *, last_month, progress=None):
        scanned.append(last_month.isoformat())
        raise v101.V101Error("TEST_STOP_BEFORE_PARQUET_SCAN")
    monkeypatch.setattr(news,"verified_news_partition_paths",read_months)
    with pytest.raises(v101.V101Error,match="TEST_STOP"):
        v101.accepted_news_to_april_2026(object())
    assert scanned==["2026-04-01"]


def _cash_book(*, unresolved=False):
    events = [
        {"event": "ENTRY_ASK_REFERENCE_ONLY", "debit_usd": "200.00"},
        {"event": "MODELED_EXIT_QUOTE_CREDIT", "two_pct_haircut_credit_usd": "220.00"},
    ]
    end = "25020.00"
    if unresolved:
        events.extend([
            {"event": "ENTRY_ASK_REFERENCE_ONLY", "debit_usd": "175.00"},
            {"event": "UNKNOWN_EXPIRY_OR_EXERCISE_CASH"},
        ])
        end = "24845.00"
    return {
        "starting_cash_usd": "25000.00", "ending_stressed_quote_cash_usd": end,
        "closed_trade_stressed_quote_pnl_usd": "20.00",
        "stressed_month_pnl_usd": {"2024-06": "20.00"},
        "stressed_week_pnl_usd": {"2024-W23": "20.00"},
        "all_considered_and_blocked_events": events,
        "unresolved_exercise_or_expiry_cash": unresolved,
        "terminal_equity_known_if_flat_usd": None if unresolved else "25020.00",
    }


def test_cash_with_unknown_expiry_is_censored_not_false_arithmetic_error():
    book = _cash_book(unresolved=True)
    audit = v101.audit_v90_cash(book)
    assert audit["unresolved"] is True
    assert audit["remaining_entry_premium_usd"] == "175.00"
    assert book["closed_trade_stressed_quote_pnl_usd"] == "20.00"
    assert book["ending_stressed_quote_cash_usd"] == "24845.00"


def test_closed_account_requires_exact_original_cash_arithmetic():
    assert v101.audit_v90_cash(_cash_book()) == {
        "unresolved": False, "remaining_entry_premium_usd": None}


def test_unknown_cash_does_not_exempt_event_or_closed_pnl_tampering():
    import copy
    broken = copy.deepcopy(_cash_book(unresolved=True))
    broken["stressed_week_pnl_usd"]["2024-W23"] = "21.00"
    with pytest.raises(v101.V101Error, match="GATED_CASH_ARITHMETIC"):
        v101.audit_v90_cash(broken)
    broken = copy.deepcopy(_cash_book(unresolved=True))
    broken["all_considered_and_blocked_events"][2]["debit_usd"] = "174.00"
    with pytest.raises(v101.V101Error, match="GATED_CASH_ARITHMETIC"):
        v101.audit_v90_cash(broken)
    broken = copy.deepcopy(_cash_book(unresolved=True))
    broken["terminal_equity_known_if_flat_usd"] = "24845.00"
    with pytest.raises(v101.V101Error, match="GATED_CASH_ARITHMETIC"):
        v101.audit_v90_cash(broken)


def test_unresolved_signed_account_never_promoted_to_complete_quote_pnl(monkeypatch):
    from types import SimpleNamespace
    import sys
    monkeypatch.setitem(sys.modules,
        "packages.simulation.spy_v90_six_family_capital_ledger",
        SimpleNamespace(verified=lambda book: True))
    book = {**_cash_book(unresolved=True), "fingerprint": "a"*64,
            "actual_broker_orders": 0}
    out = v101.filtered_cash([], missing=[], coverage_known=True,
        simulate=lambda *args, **kw: book,
        scope="impulse_0935", policy="balanced_35_100", lag=1, dwell=0)
    assert out["status"] == "SOURCE_OR_SETTLEMENT_CENSORED"
    assert out["cash_equity_known"] is False
    assert out["quote_pnl_usd"] is None
    assert out["original_account_sha"] == "a"*64
    assert out["unresolved_open_entry_premium_usd"] == "175.00"


def _real_v90_pair(*, pnl="35.20", unresolved=False, rejected=False):
    """Actual V84/V86 signed original-shape fixture through unmodified V90."""
    from packages.simulation.spy_v84_offline_three_family_economics import signed as s84
    from packages.simulation.spy_v86_original_option_exit_recheck import signed as s86
    day = "2024-01-02"
    status = ("NO_ENTRY" if rejected else
              "UNRESOLVED_POSITION" if unresolved else "CLOSED_QUOTE_REFERENCE")
    a = s84({
        "contract": "atlas-v84-offline-three-family-option-quote-shadow-v1",
        "session": day, "strategy": "acceleration_0940",
        "policy": "balanced_35_100", "lag_seconds": 3,
        "decision_at_et": day + "T09:40:01-05:00",
        "entry_action_at_et": None if rejected else day + "T09:40:10-05:00",
        "entry_debit_usd": None if rejected else "200.00",
        "entry_qty": 0 if rejected else 2,
        "status": status, "reason": "ENTRY_REJECTED" if rejected else "ORIGINAL_EXIT",
        "source_query_id": "v101-synthetic-fixture",
        "provider_requests": 0, "actual_broker_fills": 0,
    })
    b = s86({
        "contract": "atlas-v86-original-option-exit-limit-recheck-v1",
        "original_trial_sha": a["fingerprint"],
        "session": day, "strategy": "acceleration_0940",
        "policy": "balanced_35_100", "lag_seconds": 3,
        "limit_rest_seconds": 10,
        "status": status, "reason": "ENTRY_REJECTED" if rejected else "ORIGINAL_EXIT",
        "exit_action_at_et": None if (unresolved or rejected)
                             else day + "T09:41:10-05:00",
        "quote_reference_pnl_usd": None if (unresolved or rejected) else pnl,
        "quote_reference_pnl_2pct_bid_haircut_usd":
            None if (unresolved or rejected) else pnl,
        "provider_requests": 0, "actual_broker_fills": 0,
    })
    return a, b


@pytest.mark.parametrize("pnl", ["35.20", "-35.20", "0.00"])
def test_real_v90_signed_entry_to_v101_cash_result(pnl):
    from packages.simulation.spy_v90_six_family_capital_ledger import simulate
    result = v101.filtered_cash(
        [_real_v90_pair(pnl=pnl)], missing=[], coverage_known=True,
        simulate=simulate, scope="acceleration_0940",
        policy="balanced_35_100", lag=3, dwell=10)
    assert result["cash_equity_known"] is True
    assert result["status"] == "COMPLETE_QUOTE_CASH"
    assert result["quote_pnl_usd"] == pnl
    assert result["unresolved_open_entry_premium_usd"] is None
    assert result["account"]["actual_broker_orders"] == 0


def test_real_v90_rejected_entry_to_v101_no_trade_result():
    from packages.simulation.spy_v90_six_family_capital_ledger import simulate
    result = v101.filtered_cash(
        [_real_v90_pair(rejected=True)], missing=[], coverage_known=True,
        simulate=simulate, scope="acceleration_0940",
        policy="balanced_35_100", lag=3, dwell=10)
    assert result["status"] == "COMPLETE_QUOTE_CASH"
    assert result["quote_pnl_usd"] == "0"
    assert result["account"]["dispositions"]["NO_ENTRY_REJECTED"] == 1


def test_real_v90_unresolved_expiry_to_v101_censored_result():
    from packages.simulation.spy_v90_six_family_capital_ledger import simulate
    result = v101.filtered_cash(
        [_real_v90_pair(unresolved=True)], missing=[], coverage_known=True,
        simulate=simulate, scope="acceleration_0940",
        policy="balanced_35_100", lag=3, dwell=10)
    assert result["status"] == "SOURCE_OR_SETTLEMENT_CENSORED"
    assert result["cash_equity_known"] is False
    assert result["quote_pnl_usd"] is None
    assert result["unresolved_open_entry_premium_usd"] == "200.00"
    assert result["account"]["terminal_equity_known_if_flat_usd"] is None


def test_source_missing_stays_censored_even_with_closed_quote():
    from packages.simulation.spy_v90_six_family_capital_ledger import simulate
    result = v101.filtered_cash(
        [_real_v90_pair()], missing=[{"session":"2024-01-03"}],
        coverage_known=True, simulate=simulate, scope="acceleration_0940",
        policy="balanced_35_100", lag=3, dwell=10)
    assert result["status"] == "SOURCE_OR_SETTLEMENT_CENSORED"
    assert result["quote_pnl_usd"] is None
    assert result["original_missing_source_candidates"] == 1
    assert result["account"]["closed_trade_stressed_quote_pnl_usd"] == "35.20"


def test_unknown_news_coverage_does_not_call_capital_simulation():
    def forbidden(*args, **kwargs):
        raise AssertionError("unknown news must not become a simulated flat account")
    result = v101.filtered_cash(
        [], missing=[], coverage_known=False, simulate=forbidden,
        scope="acceleration_0940", policy="balanced_35_100",
        lag=3, dwell=10)
    assert result["status"] == "NEWS_COVERAGE_UNQUALIFIED"
    assert result["cash_equity_known"] is False
    assert result["quote_pnl_usd"] is None
