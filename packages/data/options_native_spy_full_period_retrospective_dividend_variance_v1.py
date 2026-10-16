from __future__ import annotations

"""Full-period SPY raw vs retrospective dividend-conditioned variance sensitivity.

This is a *diagnostic*, not an as-of adjusted close feed, causal forecast,
published dividend history proof, implied-variance input or backtest. All
archival sources remain unchanged. No provider, outcomes, option, or raw-bar IO.
"""

from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from decimal import Context, Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
from typing import Any

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_archival_action_timeline_v1 import (
    COVERAGE, PinnedSource, _load_pinned,
)
from packages.data.options_native_spy_dividend_negative_control_v1 import ARCHIVE
from packages.data.options_native_spy_prior_variance_sensitivity_v1 import (
    LOG_QUANTUM, YEAR_SECONDS,
)
from packages.strategies.options_native_pilot_v1_contract import AUTHORITY, SPECIFICATION_FINGERPRINT

CONTRACT = "atlas-options-native-spy-retrospective-dividend-variance-grid-v1"
NEGATIVE = PinnedSource(
    "data/research/options_native_spy_dividend_negative_control_v1/81102692ce1d1062.json",
    "fd984995c6bd7d5db17dca3c61105d9365d255bd5765cf6535ce8c92eed81e63",
    "81102692ce1d1062ddc0022f09350b1c1d9a6ec5514625081a08f273607e8a96",
)
JANUARY_2020 = PinnedSource(
    "data/research/options_native_spy_prior_variance_sensitivity_v1/0962d8ff207f29ea.json",
    "574d57fb0d19e60486e1b3defbf50ac09f677d19fd37b4ef716e6a73607b0ccc",
    "0962d8ff207f29ea492408e711d714726d8dcaada55c6e50942b6c646007e378",
)
REFERENCE_SOURCE = "https://dividendhistory.org/payout/SPY/"
CORROBORATING_SOURCE = "https://www.aastocks.com/en/usq/analysis/dividend.aspx?symbol=SPY"
REFERENCE_OBSERVED_DATE = "2026-10-16"
REFERENCE_START = "2017-12-15"
REFERENCE_END = "2025-12-19"
KNOWN_ABSENCE = "2018-06-15"
RATE_TOLERANCE = Decimal("0.000005")

# Original, independently published US SPY dividend-history values, transcribed
# on 2026-10-16. NOT historical 2017-2025 announcements or PIT source receipts.
# U.S. sponsor historical-distributions XLSX is a further authority to reconcile
# when a versioned original file is available. Do not substitute a CDI ex-date.
RETROSPECTIVE_US_SPY_DISTRIBUTIONS = (
    ("2017-12-15", "1.351333"),
    ("2018-03-16", "1.09678"),
    ("2018-06-15", "1.245568"),
    ("2018-09-21", "1.322611"),
    ("2018-12-21", "1.435429"),
    ("2019-03-15", "1.233119"),
    ("2019-06-21", "1.43164"),
    ("2019-09-20", "1.383619"),
    ("2019-12-20", "1.569992"),
    ("2020-03-20", "1.405559"),
    ("2020-06-19", "1.366242"),
    ("2020-09-18", "1.339224"),
    ("2020-12-18", "1.58"),
    ("2021-03-19", "1.277788"),
    ("2021-06-18", "1.375875"),
    ("2021-09-17", "1.428117"),
    ("2021-12-17", "1.636431"),
    ("2022-03-18", "1.366009"),
    ("2022-06-17", "1.576871"),
    ("2022-09-16", "1.596398"),
    ("2022-12-16", "1.7814"),
    ("2023-03-17", "1.506204"),
    ("2023-06-16", "1.638367"),
    ("2023-09-15", "1.583169"),
    ("2023-12-15", "1.906073"),
    ("2024-03-15", "1.594937"),
    ("2024-06-21", "1.759024"),
    ("2024-09-20", "1.745531"),
    ("2024-12-20", "1.965548"),
    ("2025-03-21", "1.695528"),
    ("2025-06-20", "1.761117"),
    ("2025-09-19", "1.831114"),
    ("2025-12-19", "1.993368"),
)


class RetrospectiveDividendGridError(ValueError):
    pass


def _require(test: bool, reason: str) -> None:
    if not test:
        raise RetrospectiveDividendGridError(reason)


def _positive_decimal(v: object) -> Decimal:
    _require(isinstance(v, str) and 0 < len(v) < 64, "bounded decimal source required")
    try:
        d = Decimal(v)
    except InvalidOperation as exc:
        raise RetrospectiveDividendGridError("invalid source decimal") from exc
    _require(d.is_finite() and Decimal(0) < d < Decimal("1000000")
             and d.as_tuple().exponent >= -24, "invalid source magnitude or precision")
    return d


def reference_schedule() -> dict[str, Decimal]:
    _require(len(RETROSPECTIVE_US_SPY_DISTRIBUTIONS) == 33
             and RETROSPECTIVE_US_SPY_DISTRIBUTIONS[0][0] == REFERENCE_START
             and RETROSPECTIVE_US_SPY_DISTRIBUTIONS[-1][0] == REFERENCE_END,
             "independent reference schedule population changed")
    out: dict[str, Decimal] = {}
    for when, amount in RETROSPECTIVE_US_SPY_DISTRIBUTIONS:
        _require(when == date.fromisoformat(when).isoformat()
                 and when not in out
                 and REFERENCE_START <= when <= REFERENCE_END,
                 "reference ex-date invalid, repeated or out of scope")
        out[when] = _positive_decimal(amount)
    _require(list(out) == sorted(out) and len(out) == 33 and KNOWN_ABSENCE in out,
             "reference dates not strictly increasing")
    counts = Counter(k[:4] for k in out)
    _require(counts == {"2017": 1, **{str(year): 4 for year in range(2018, 2026)}},
             "quarterly retrospective reference series changed")
    return out


def reconcile_reference_to_archive(archive: dict[str, Any], schedule: dict[str, Decimal]) -> dict:
    candidates = archive.get("action_candidates")
    _require(isinstance(candidates, list) and len(candidates) == 32
             and archive.get("action_candidates_by_type") == {"cash_dividends": 32}
             and archive.get("archival_candidates_with_unknown_effective_date") == 0,
             "original action candidate population changed")
    recorded: dict[str, Decimal] = {}
    for item in candidates:
        payload = item.get("payload")
        _require(item.get("action_type") == "cash_dividends"
                 and item.get("historical_available_at_utc") is None
                 and item.get("point_in_time_qualified") is False
                 and isinstance(payload, dict) and payload.get("symbol") == "SPY"
                 and isinstance(payload.get("ex_date"), str),
                 "original action source gained historical authority or wrong type")
        when = payload["ex_date"]
        _require(when not in recorded and when in schedule, "extra/duplicate archive ex-date")
        recorded[when] = _positive_decimal(str(payload["rate"]))
    _require(set(schedule) - set(recorded) == {KNOWN_ABSENCE},
             "full-period date reconciliation changed; no automatic source repair")
    _require(set(recorded) - set(schedule) == set(), "unexplained archival ex-date")
    residuals = [
        {"ex_date": day, "archived_rate": str(recorded[day]),
         "reference_rate": str(schedule[day]),
         "archived_minus_reference": str(recorded[day] - schedule[day])}
        for day in sorted(recorded) if recorded[day] != schedule[day]
    ]
    _require([x["ex_date"] for x in residuals] == ["2018-03-16", "2020-06-19"]
             and all(abs(Decimal(x["archived_minus_reference"])) <= RATE_TOLERANCE for x in residuals),
             "retrospective cash amount disagreement exceeds expected rounding")
    return {
        "reference_event_count": len(schedule), "archived_event_count": len(recorded),
        "exact_ex_date_matches": len(recorded),
        "known_missing_ex_dates": [KNOWN_ABSENCE],
        "rounded_rate_residuals": residuals, "retrospective_nondividend_events_proved_absent": False,
        "historical_record_completeness_qualified": False,
    }


def case_volatility(prior: list[str], observations: dict[str, Any],
                    schedule: dict[str, Decimal]) -> dict[str, Any]:
    """Twenty bounded intervals; baseline date never consumes a distribution."""
    _require(len(prior) == 21 and len(set(prior)) == 21, "21 distinct prior closing clocks required")
    times: list[datetime] = []
    prices: list[Decimal] = []
    for key in prior:
        try:
            t = datetime.fromisoformat(key)
        except (TypeError, ValueError) as exc:
            raise RetrospectiveDividendGridError("invalid minute clock") from exc
        _require(t.tzinfo is not None and t.utcoffset() is not None, "timezone-naive minute clock")
        t = t.astimezone(UTC)
        row = observations.get(key)
        _require(isinstance(row, dict) and row.get("status") == "RAW_MINUTE_PRESENT"
                 and row.get("historical_available_at_utc") is None,
                 "wrong historical price provenance or publication asserted")
        times.append(t)
        prices.append(_positive_decimal(row.get("raw_close")))
    _require(all(b > a for a, b in zip(times, times[1:])), "out-of-order historical price clocks")
    seconds = 0
    raw_sum = Decimal(0)
    conditional_sum = Decimal(0)
    hits = []
    with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
        for i in range(1, 21):
            seconds += int((times[i] - times[i-1]).total_seconds())
            ex_date = times[i].date().isoformat()
            cash = schedule.get(ex_date, Decimal(0))
            if cash:
                hits.append({"ex_date": ex_date, "retrospective_cash_usd": str(cash)})
            raw_r = (prices[i] / prices[i-1]).ln().quantize(LOG_QUANTUM)
            conditional_r = ((prices[i] + cash) / prices[i-1]).ln().quantize(LOG_QUANTUM)
            raw_sum += raw_r * raw_r
            conditional_sum += conditional_r * conditional_r
        _require(seconds > 0 and len(hits) <= 2, "invalid 20-return interval span")
        raw_rate = raw_sum / Decimal(seconds)
        conditioned_rate = conditional_sum / Decimal(seconds)
        raw_vol = (raw_rate * YEAR_SECONDS).sqrt()
        conditioned_vol = (conditioned_rate * YEAR_SECONDS).sqrt()
    return {
        "annualized_raw_price_volatility": str(raw_vol),
        "annualized_retrospective_dividend_conditioned_volatility": str(conditioned_vol),
        "delta_annualized_volatility": str(conditioned_vol - raw_vol),
        "archived_dividend_adjustment_would_be_lookahead_without_pit_proof": bool(hits),
        "retrospective_dividends_in_return_end_dates": hits,
        "elapsed_calendar_seconds": seconds,
        "historical_feature_accepted": False,
    }


def build_full_period_retrospective_grid(settings: AtlasSettings) -> dict[str, Any]:
    coverage = _load_pinned(settings, COVERAGE)
    archive = _load_pinned(settings, ARCHIVE)
    negative = _load_pinned(settings, NEGATIVE)
    january = _load_pinned(settings, JANUARY_2020)
    _require(coverage.get("report_fingerprint") == COVERAGE.fingerprint
             and archive.get("report_fingerprint") == ARCHIVE.fingerprint
             and negative.get("report_fingerprint") == NEGATIVE.fingerprint
             and january.get("report_fingerprint") == JANUARY_2020.fingerprint,
             "one of four upstream report identities differs")
    _require(coverage.get("contract") == "atlas-options-native-spy-development-minute-clock-coverage-v1"
             and coverage.get("specification_fingerprint") == SPECIFICATION_FINGERPRINT
             and coverage.get("target_weekly_cases") == 411
             and coverage.get("raw_complete_weekly_cases") == 407
             and coverage.get("observed_exact_clocks") == 2406
             and coverage.get("pilot_input_acceptance") is False
             and coverage.get("authority") == dict(AUTHORITY)
             and archive.get("native_ledger_records_reconciled") == 378362
             and archive.get("status") == "ARCHIVAL_SPY_ACTION_INDEX_ONLY_PIT_AND_COVERAGE_UNQUALIFIED"
             and archive.get("authority") == dict(AUTHORITY)
             and negative.get("contract") == "atlas-options-native-spy-external-dividend-negative-control-v1"
             and negative.get("affected_weekly_case_count") == 5
             and negative.get("archive_empty_weekly_windows") == 267
             and negative.get("pilot_input_acceptance") is False
             and negative.get("authority") == dict(AUTHORITY),
             "frozen source scope, gap or authority changed")
    _require(negative.get("frozen_archival_timeline_fingerprint") == ARCHIVE.fingerprint
             and negative.get("frozen_coverage_report_fingerprint") == COVERAGE.fingerprint
             and negative.get("retrospective_cash_amount_is_historical_feature") is False
             and january.get("specification_fingerprint") == SPECIFICATION_FINGERPRINT
             and january.get("return_count") == 20
             and january.get("pilot_input_acceptance") is False
             and january.get("forecast_total_variance") is None,
             "negative control or first 2020 variance comparison changed")
    observations = coverage.get("observations")
    cases = coverage.get("cases")
    _require(isinstance(observations, dict) and len(observations) == 2407
             and isinstance(cases, list) and len(cases) == 411,
             "frozen case/observation population drifted")
    schedule = reference_schedule()
    comparison = reconcile_reference_to_archive(archive, schedule)
    weekly = []
    stats: dict[str, list[Decimal]] = defaultdict(list)
    touched = 0
    full = 0
    four_missing = []
    for case in cases:
        day = case["decision_date"]
        previous = case["prior_close_keys"]
        keys = [*previous, case["spot_key"]]
        _require(len(previous) == 21 and len(set(keys)) == 22
                 and set(keys).issubset(observations)
                 and case.get("historical_input_accepted") is False
                 and case.get("forecast_total_variance") is None,
                 "case prior/spot scope or historical authority changed")
        missing = [k for k in keys if observations[k].get("raw_close") is None]
        _require(missing == case.get("missing_clocks"), "source gaps changed")
        if missing:
            four_missing.append(day)
            weekly.append({"decision_date": day, "status": "RAW_PRICE_GAP_NO_VARIANCE_DIAGNOSTIC",
                           "missing_raw_clocks": missing, "historical_feature_accepted": False})
            continue
        result = case_volatility(previous, observations, schedule)
        full += 1
        touched += bool(result["retrospective_dividends_in_return_end_dates"])
        if day == "2020-01-06":
            previous_numbers = january["conditional_variance"]
            _require(result["annualized_raw_price_volatility"] ==
                     previous_numbers["unadjusted_annualized_volatility"]
                     and result["annualized_retrospective_dividend_conditioned_volatility"] ==
                     previous_numbers["one_dividend_annualized_volatility"],
                     "first pilot's previously proven variance arithmetic did not reproduce")
        stats[day[:4]].append(Decimal(result["delta_annualized_volatility"]))
        weekly.append({"decision_date": day, "status": "RETROSPECTIVE_VARIANCE_SENSITIVITY_ONLY",
                       **result})
    _require(full == 407 and touched >= 130 and len(weekly) == 411,
             "annual retrospective dividend variance population drifted")
    _require(four_missing == ["2019-08-19", "2019-08-26", "2019-09-03", "2019-09-09"],
             "known August 2019 missing-minute dependencies drifted")
    affected = [row["decision_date"] for row in weekly
                if row.get("retrospective_dividends_in_return_end_dates") and
                any(x["ex_date"] == KNOWN_ABSENCE
                    for x in row["retrospective_dividends_in_return_end_dates"])]
    _require(affected == ["2018-06-18", "2018-06-25", "2018-07-02",
                          "2018-07-09", "2018-07-16"],
             "June 2018 negative-control windows did not reproduce")
    by_year = []
    for year, ds in sorted(stats.items()):
        by_year.append({"decision_year": year, "windows": len(ds),
                        "raw_vs_dividend_delta_min": str(min(ds)),
                        "raw_vs_dividend_delta_max": str(max(ds)),
                        "raw_vs_dividend_delta_mean": str(sum(ds) / len(ds))})
    report = {
        "contract": CONTRACT,
        "status": "FULL_PERIOD_RETROSPECTIVE_SENSITIVITY_ONLY_NO_PIT_FEATURES",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "pinned_input_raw_sha256": {
            "minute_coverage": COVERAGE.sha256, "archival_action_index": ARCHIVE.sha256,
            "external_negative_control": NEGATIVE.sha256,
            "january_2020_sensitivity": JANUARY_2020.sha256,
        },
        "retrospective_reference": {
            "source": REFERENCE_SOURCE, "independent_corrob": CORROBORATING_SOURCE,
            "source_observed_on": REFERENCE_OBSERVED_DATE,
            "date_range": [REFERENCE_START, REFERENCE_END],
            "rows": [{"us_ex_date": k, "us_cash_per_share": str(v)}
                     for k, v in schedule.items()],
            "us_issuer_historical_distribution_file_retrieved_and_hashed": False,
            "2018_2025_historical_publication_revisions_proved": False,
            "full_split_and_noncash_corporate_action_coverage_proved": False,
        },
        "archive_reconciliation": comparison,
        "fixed_weekly_decision_count": 411,
        "physically_price_complete_decisions": full,
        "retrospective_dividend_touched_decisions": touched,
        "price_incomplete_decisions": four_missing,
        "known_archivally_omitted_dividend_affected_decisions": affected,
        "annual_delta_summary": by_year,
        "weekly_retrospective_sensitivity": weekly,
        "retrospective_dividend_adjusted_return_inputs_qualified": False,
        "historical_publication_and_revision_clocks_qualified": False,
        "complete_splits_and_dividends_source_coverage_qualified": False,
        "historical_economic_feature_accepted": False,
        "historical_backtest_authorized": False,
        "economic_log_returns": None,
        "forecast_total_variance": None,
        "option_quotes": None,
        "pilot_input_acceptance": False,
        "historical_performance_evidence": False,
        "reads": {"pinned_json_reports": 4, "minute_source_units": 0,
                  "action_ledgers": 0, "option_histories": 0, "outcomes": 0,
                  "provider_requests": 0, "broker_requests": 0},
        "authority": dict(AUTHORITY),
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report
