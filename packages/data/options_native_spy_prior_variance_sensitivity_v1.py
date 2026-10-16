from __future__ import annotations

"""Read-only sensitivity of the first SPY pilot's prior returns to ONE cached dividend.

The archived corporate-action snapshot is not a 2019 publication-time source.
A verified original action record is not proof of complete split/dividend
coverage, a historically known amount, or an admissible strategy feature.
The output is a conditional arithmetic comparison, never a historical return
adapter, tradable forecast, experiment result, or source qualification.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Context, Decimal, ROUND_HALF_EVEN, InvalidOperation, localcontext
import hashlib
import json
from pathlib import Path
from typing import Any

from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_pilot_input_packet_v1 import FEATURE_CUTOFF, requested_prior_sessions
from packages.data.options_native_spy_action_source_proof_v1 import CONTRACT as PROOF_CONTRACT
from packages.data.options_native_stock_input_review_v1 import CONTRACT as STOCK_CONTRACT
from packages.strategies.options_native_pilot_v1_contract import AUTHORITY, SPECIFICATION_FINGERPRINT

CONTRACT = "atlas-options-native-spy-prior-variance-sensitivity-v1"
MAX_FILE_BYTES = 512 * 1024
YEAR_SECONDS = Decimal(365 * 86400)
LOG_QUANTUM = Decimal("1e-24")
EX_DATE = "2019-12-20"


class SpyPriorVarianceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PinnedReview:
    path: str = "data/research/options_native_stock_input_review_v1/9caee69b5d0fc180.json"
    sha256: str = "3dd302e9416ebb373fbb94d14045823e1e2c081b72f8c403ddd1cd5ffdc0f3bb"
    fingerprint: str = "9caee69b5d0fc18075451f7b4b8c46ec3c8db817d4b0b0d3ed311bf9712748e7"


@dataclass(frozen=True, slots=True)
class PinnedProof:
    path: str = "data/research/options_native_spy_action_source_proof_v1/b0cbad9dca14d6ce.json"
    sha256: str = "3880427d8300d814cebd7ede1c6a2b6dc72c51d8a50fc686a75932081566b237"
    fingerprint: str = "b0cbad9dca14d6ce0221cd684473fbc3190e17248c42b0b0909c0854a9f8d929"


def _require(test: bool, reason: str) -> None:
    if not test:
        raise SpyPriorVarianceError(reason)


def _json_reject_nonfinite(value: str) -> None:
    raise SpyPriorVarianceError("nonfinite number inside pinned JSON report")


def _read_report(settings: AtlasSettings, binding: PinnedReview | PinnedProof) -> dict[str, Any]:
    path = settings.resolved_path(binding.path)
    _require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= MAX_FILE_BYTES,
             "named retained source report missing, linked or oversized")
    raw = path.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == binding.sha256, "retained report raw-byte hash drifted")
    try:
        report = json.loads(raw, parse_constant=_json_reject_nonfinite)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise SpyPriorVarianceError("retained report is malformed") from exc
    _require(isinstance(report, dict) and report.get("report_fingerprint") == binding.fingerprint
             and _fingerprint({k: v for k, v in report.items() if k != "report_fingerprint"})
             == binding.fingerprint, "retained report signature or identity changed")
    return report


def _price(value: object, *, can_zero: bool = False) -> Decimal:
    _require(isinstance(value, str) and 0 < len(value) <= 64, "bounded price string required")
    try:
        out = Decimal(value)
    except InvalidOperation as exc:
        raise SpyPriorVarianceError("invalid price or cash amount") from exc
    _require(out.is_finite() and 0 <= out <= 1000000 and (can_zero or out > 0)
             and out.as_tuple().exponent >= -24, "nonpositive or unbounded price or cash amount")
    return out


def _clock(value: object) -> datetime:
    _require(isinstance(value, str), "exact historical UTC clock required")
    try:
        at = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SpyPriorVarianceError("invalid historical clock") from exc
    _require(at.tzinfo is not None and at.utcoffset() is not None, "timezone-free clock forbidden")
    return at.astimezone(UTC)


def build_spy_prior_variance_sensitivity(
    settings: AtlasSettings, *, stock_binding: PinnedReview = PinnedReview(),
    proof_binding: PinnedProof = PinnedProof(),
) -> dict[str, Any]:
    stock = _read_report(settings, stock_binding)
    proof = _read_report(settings, proof_binding)
    expected = {
        "contract": STOCK_CONTRACT, "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "feature_cutoff_utc": FEATURE_CUTOFF.isoformat(),
        "requested_minute_observations": 22, "present_minute_observations": 22,
        "missing_minute_clocks": [], "economic_log_returns": None,
        "forecast_total_variance": None, "pilot_input_acceptance": False,
    }
    _require(all(stock.get(k) == v for k, v in expected.items())
             and stock.get("authority") == dict(AUTHORITY) | {"raw_source_scans": 3},
             "stock-input report scope or historical authority changed")
    required_proof = {
        "contract": PROOF_CONTRACT, "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "date_window": ["2019-10-01", "2020-03-31"],
        "prior_stock_review_fingerprint": stock_binding.fingerprint,
        "prior_stock_review_sha256": stock_binding.sha256,
        "source_page_hashes_verified": True,
        "native_ledger_exactly_matches_original_pages": True,
        "original_prior_window_candidates_reconciled": 1,
        "historical_pit_publication_qualified": False,
        "action_effective_date_coverage_qualified": False,
        "economic_log_returns": None, "forecast_total_variance": None,
        "pilot_input_acceptance": False,
    }
    _require(all(proof.get(k) == v for k, v in required_proof.items())
             and proof.get("authority") == dict(AUTHORITY) | {"raw_source_scans": 2},
             "original action proof scope or historical authority changed")
    _require(proof.get("source_scans", {}).get("raw_option_histories") == 0,
             "source proof unexpectedly opened option history")

    # This is deliberately a ONE-record sensitivity, not a claim that another
    # corporate action was absent from the historical information set.
    actions = proof.get("spy_action_candidates")
    _require(isinstance(actions, list) and len(actions) == 2, "SPY action population changed")
    actions_by_date: dict[str, dict[str, Any]] = {}
    for action in actions:
        _require(isinstance(action, dict) and action.get("action_type") == "cash_dividends"
                 and action.get("historical_available_at_utc") is None
                 and action.get("point_in_time_qualified") is False, "action type or PIT flag changed")
        payload = action.get("payload")
        _require(isinstance(payload, dict) and payload.get("symbol") == "SPY"
                 and payload.get("special") is False, "SPY distribution identity changed")
        key = payload.get("ex_date")
        _require(key in (EX_DATE, "2020-03-20") and key not in actions_by_date,
                 "SPY action dates, uniqueness or chronology changed")
        actions_by_date[key] = action
    _require(set(actions_by_date) == {EX_DATE, "2020-03-20"}, "unexpected source dividend event")
    amount = _price(str(actions_by_date[EX_DATE]["payload"]["rate"]))
    _price(str(actions_by_date["2020-03-20"]["payload"]["rate"]))
    _require(actions_by_date["2020-03-20"]["payload"]["process_date"] > FEATURE_CUTOFF.date().isoformat(),
             "future dividend process-date relationship changed")
    retained = stock.get("corporate_actions", {}).get("selected_spy_records")
    _require(isinstance(retained, list) and len(retained) == 1
             and retained[0] == actions_by_date[EX_DATE],
             "first prior SPY dividend does not exactly match original stock review")

    calendar = get_market_calendar("XNYS")
    observations = stock.get("observations")
    days = requested_prior_sessions()
    _require(isinstance(observations, list) and len(observations) == 22 and len(days) == 21,
             "prior 21-close population changed")
    closes: list[tuple[datetime, Decimal, str]] = []
    for row, day in zip(observations[:21], days):
        end = _clock(row.get("interval_end_utc"))
        start = _clock(row.get("interval_start_utc"))
        _require(row.get("role") == "PRIOR_REGULAR_CLOSE" and row.get("session_date") == day.isoformat()
                 and row.get("state") == "EXACT_CACHED_MINUTE_PRESENT"
                 and end == calendar.regular_open_close(day)[1] and start == end - timedelta(minutes=1)
                 and row.get("historical_available_at_utc") is None and row.get("pilot_eligible") is False
                 and row.get("economic_return_qualified") is False
                 and row.get("interval_end_is_publication_proof") is False,
                 "prior minute price clock or qualification changed")
        price = _price(row.get("raw_close"))
        daily_price = _price(row.get("retained_daily_close"))
        _require(_price(str(abs(Decimal(row["minute_minus_daily"]))), can_zero=True)
                 == abs(price - daily_price), "minute/daily comparison changed")
        closes.append((end, price, day.isoformat()))
    spot = observations[-1]
    _require(spot.get("role") == "DECISION_SPOT" and spot.get("session_date") == "2020-01-06"
             and _clock(spot.get("interval_end_utc")) == FEATURE_CUTOFF
             and _clock(spot.get("interval_start_utc")) == FEATURE_CUTOFF - timedelta(minutes=1)
             and spot.get("state") == "EXACT_CACHED_MINUTE_PRESENT"
             and spot.get("historical_available_at_utc") is None
             and spot.get("pilot_eligible") is False, "frozen 10:00 decision observation changed")
    _price(spot.get("raw_close"))

    raw_sum = Decimal(0)
    conditional_sum = Decimal(0)
    seconds = 0
    rows = []
    with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
        for (previous_at, previous, _), (at, current, day) in zip(closes, closes[1:]):
            dividend = amount if day == EX_DATE else Decimal(0)
            seconds += int((at - previous_at).total_seconds())
            unadjusted = (current / previous).ln().quantize(LOG_QUANTUM)
            conditional = ((current + dividend) / previous).ln().quantize(LOG_QUANTUM)
            raw_sum += unadjusted ** 2
            conditional_sum += conditional ** 2
            rows.append({"interval_start_utc": previous_at.isoformat(),
                         "interval_end_utc": at.isoformat(), "end_session": day,
                         "raw_close_log_return": str(unadjusted),
                         "one_dividend_conditional_log_return": str(conditional),
                         "scenario_ex_date_cash_per_original_share": str(dividend),
                         "historical_return_qualified": False})
        _require(len(rows) == 20 and seconds > 0, "prior variance window incomplete")
        raw_rate = raw_sum / Decimal(seconds)
        conditioned_rate = conditional_sum / Decimal(seconds)
        raw_vol = (raw_rate * YEAR_SECONDS).sqrt()
        conditioned_vol = (conditioned_rate * YEAR_SECONDS).sqrt()
    result = {
        "contract": CONTRACT, "status": "CONDITIONAL_SENSITIVITY_ONLY_NO_HISTORICAL_PIT_ACCEPTANCE",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "feature_cutoff_utc": FEATURE_CUTOFF.isoformat(),
        "input_source_identities": {"stock_review_sha256": stock_binding.sha256,
                                    "stock_review_fingerprint": stock_binding.fingerprint,
                                    "raw_action_proof_sha256": proof_binding.sha256,
                                    "raw_action_proof_fingerprint": proof_binding.fingerprint},
        "return_rows": rows,
        "prior_close_count": len(closes), "return_count": len(rows),
        "decision_spot_raw": spot["raw_close"], "elapsed_calendar_seconds": seconds,
        "conditional_dividend_record": actions_by_date[EX_DATE],
        "later_dividend_excluded": {"ex_date": "2020-03-20", "role": "FUTURE_NOT_PILOT_INPUT"},
        "assumptions_not_qualified": [
            "ARCHIVAL_DIVIDEND_AMOUNT_ASSUMED_KNOWN_AT_2020_01_06_DESPITE_UNKNOWN_PUBLICATION_AND_REVISIONS",
            "NO_OTHER_CORPORATE_ACTIONS_ASSUMED_FOR_DIAGNOSTIC_NOT_ESTABLISHED_BY_CACHED_RECORD_SELECTION",
            "EX_DATE_CASH_PER_ORIGINAL_SHARE_USED_FOR_ANALYTICAL_RETURN_NOT_BROKER_PAYMENT",
            "ORIGINAL_MINUTE_CLOSE_END_IS_NOT_HISTORICAL_PROVIDER_PUBLICATION_CLOCK",
            "CALENDAR_TIME_SQUARED_LOG_RETURN_VARIANCE_CONVENTION_IS_FROZEN_BUT_NOT_ALPHA_EVIDENCE",
        ],
        "conditional_variance": {
            "unadjusted_variance_per_calendar_second": str(raw_rate),
            "one_dividend_variance_per_calendar_second": str(conditioned_rate),
            "unadjusted_annualized_volatility": str(raw_vol),
            "one_dividend_annualized_volatility": str(conditioned_vol),
            "variance_method": "sum(squared_20_log_returns)/sum(calendar_seconds_between_closes)",
            "annualization_seconds": str(YEAR_SECONDS),
            "historical_feature_authority": False,
        },
        "economic_log_returns": None, "forecast_total_variance": None,
        "historical_pit_publication_qualified": False, "action_effective_date_coverage_qualified": False,
        "pilot_input_acceptance": False, "historical_performance_evidence": False,
        "source_scans": {"daily": 0, "minute": 0, "original_action_pages": 0,
                         "native_action_ledger": 0, "options": 0, "outcomes": 0},
        "authority": dict(AUTHORITY),
    }
    result["report_fingerprint"] = _fingerprint(result)
    return result
