from __future__ import annotations

"""Same-date/time stock-vs-option *reference* comparison on six-year cohorts.

The source-facing adapter must build inputs from accepted, time-stamped stock
and option data. This component never contacts a provider, selects a different
contract after seeing future liquidity, or grants fill/portfolio authority.
"""

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from math import floor, isfinite
import re
from typing import Any, Literal
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT = "atlas-common-clock-stock-option-eod-reference-scenario-v1"
MARKET_TZ = ZoneInfo("America/New_York")
MAX_MARK_SKEW = timedelta(minutes=30)
DEFAULT_BUDGET = 10000.0
DEFAULT_STOCK_SLIPPAGE_BPS = 5.0
DEFAULT_OPTION_ROUND_TRIP_FEE = 1.30
Mode = Literal["EOD_LATER_SAME_SESSIONS"]


class CommonClockScenarioError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TimedMark:
    session: date
    observed_at_utc: datetime
    per_share: float
    source_sha256: str
    source_kind: str


@dataclass(frozen=True, slots=True)
class SameClockCase:
    case_id: str
    year: int
    ticker: str
    original_signal_utc: datetime
    selected_option_at_utc: datetime
    news_cutoff_utc: datetime
    prior_24h_article_count: int
    prior_7d_article_count: int
    option_symbol: str | None
    option_expiration: date | None
    option_right: Literal["call", "put"] | None
    option_multiplier: int | None
    standard_deliverable_verified: bool
    stock_raw_price_basis_verified: bool
    stock_entry: TimedMark | None
    stock_exit: TimedMark | None
    option_entry_ask: TimedMark | None
    option_exit_bid: TimedMark | None
    option_reference_status: str
    source_lineage_fingerprint: str


def _stamp(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise CommonClockScenarioError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)


def _mark(value: TimedMark, label: str) -> datetime:
    stamp = _stamp(value.observed_at_utc, label)
    if (
        stamp.astimezone(MARKET_TZ).date() != value.session
        or not isinstance(value.per_share, (int, float))
        or isinstance(value.per_share, bool)
        or not isfinite(value.per_share) or value.per_share <= 0
        or len(value.source_sha256) != 64
        or any(c not in "0123456789abcdef" for c in value.source_sha256)
        or not value.source_kind
    ):
        raise CommonClockScenarioError(f"{label} source mark invalid")
    return stamp


def compare_case(
    case: SameClockCase, *, mode: Mode = "EOD_LATER_SAME_SESSIONS",
    allocation: float = DEFAULT_BUDGET,
    stock_slippage_bps: float = DEFAULT_STOCK_SLIPPAGE_BPS,
    stock_round_trip_commission: float = 0.0,
    option_round_trip_fee_per_contract: float = DEFAULT_OPTION_ROUND_TRIP_FEE,
) -> dict[str, Any]:
    """A scenario diagnostic: no observed fill or overlapping-account replay."""
    if mode != "EOD_LATER_SAME_SESSIONS":
        raise CommonClockScenarioError("original 09:35 mode needs independent intraday evidence")
    signal = _stamp(case.original_signal_utc, "original signal")
    selection = _stamp(case.selected_option_at_utc, "option selection")
    news = _stamp(case.news_cutoff_utc, "news cutoff")
    if (
        not case.case_id or not case.ticker
        or case.year not in range(2021, 2027)
        or signal.astimezone(MARKET_TZ).year != case.year
        or selection > signal or news > signal
        or type(case.prior_24h_article_count) is not int
        or type(case.prior_7d_article_count) is not int
        or not 0 <= case.prior_24h_article_count <= case.prior_7d_article_count
        or len(case.source_lineage_fingerprint) != 64
    ):
        raise CommonClockScenarioError("original source/selection/news decision drifted")
    for name, value in (
        ("allocation", allocation),
        ("stock slippage", stock_slippage_bps),
        ("stock commission", stock_round_trip_commission),
        ("option fee", option_round_trip_fee_per_contract),
    ):
        if (
            not isinstance(value, (float, int)) or isinstance(value, bool)
            or not isfinite(value) or value < 0
        ):
            raise CommonClockScenarioError(f"{name} must be finite and nonnegative")
    if allocation <= 0 or not 0 <= stock_slippage_bps <= 200:
        raise CommonClockScenarioError("allocation or stock slippage outside permitted bounds")

    result: dict[str, Any] = {
        "contract": CONTRACT, "case_id": case.case_id, "year": case.year,
        "ticker": case.ticker, "mode": mode,
        "decision_at_utc": signal.isoformat(),
        "selected_option_symbol": case.option_symbol,
        "prior_24h_articles": case.prior_24h_article_count,
        "prior_7d_articles": case.prior_7d_article_count,
        "fixed_scenario_allocation": allocation,
        "stock_status": "MISSING_MATCHED_STOCK_MARKS",
        "stock_reference_pnl": None, "stock_reference_return_fraction": None,
        "stock_shares": 0,
        "option_status": case.option_reference_status,
        "option_reference_pnl": None, "option_reference_return_fraction": None,
        "option_contracts": 0,
        "source_lineage_fingerprint": case.source_lineage_fingerprint,
        "provider_requests": 0, "actual_fills": 0,
        "common_clock_eod_prices_are_not_executable_fill_proof": True,
        "model_reference_pnl_not_backtest_or_paper_pnl": True,
        "account_level_portfolio_return": None,
        "strategy_promoted": False,
    }
    stock = case.stock_entry is not None and case.stock_exit is not None
    option = case.option_entry_ask is not None and case.option_exit_bid is not None
    if case.stock_entry is not None:
        entry_stamp = _mark(case.stock_entry, "stock entry")
    else:
        entry_stamp = None
    if case.stock_exit is not None:
        exit_stamp = _mark(case.stock_exit, "stock exit")
    else:
        exit_stamp = None
    if case.option_entry_ask is not None:
        opt_entry_stamp = _mark(case.option_entry_ask, "option entry")
    else:
        opt_entry_stamp = None
    if case.option_exit_bid is not None:
        opt_exit_stamp = _mark(case.option_exit_bid, "option exit")
    else:
        opt_exit_stamp = None
    if case.stock_raw_price_basis_verified is not True:
        raise CommonClockScenarioError("stock raw-as-traded basis unverified")
    if case.stock_entry is not None and case.stock_entry.source_kind != "NATIVE_RAW_EOD_STOCK_MARK":
        raise CommonClockScenarioError("stock entry is not a native raw EOD mark")
    if case.stock_exit is not None and case.stock_exit.source_kind != "NATIVE_RAW_EOD_STOCK_MARK":
        raise CommonClockScenarioError("stock exit is not a native raw EOD mark")
    if case.option_entry_ask is not None and case.option_entry_ask.source_kind != "HISTORICAL_OPTION_EOD_ASK":
        raise CommonClockScenarioError("option entry is not a historical EOD ask")
    if case.option_exit_bid is not None and case.option_exit_bid.source_kind != "HISTORICAL_OPTION_EOD_BID":
        raise CommonClockScenarioError("option exit is not a historical EOD bid")
    if stock:
        assert entry_stamp is not None and exit_stamp is not None
        if (
            case.stock_entry.session <= signal.astimezone(MARKET_TZ).date()
            or case.stock_exit.session <= case.stock_entry.session
            or exit_stamp <= entry_stamp
        ):
            raise CommonClockScenarioError("stock entry/exit must be strictly later than 09:35")
        basis = stock_slippage_bps / 10000.0
        buy = case.stock_entry.per_share * (1 + basis)
        sell = case.stock_exit.per_share * (1 - basis)
        shares = floor(max(0.0, allocation - stock_round_trip_commission) / buy)
        if shares < 1:
            result["stock_status"] = "INSUFFICIENT_STOCK_ALLOCATION"
        else:
            pnl = shares * (sell - buy) - stock_round_trip_commission
            result.update({
                "stock_status": "ILLUSTRATIVE_STOCK_EOD_REFERENCE",
                "stock_reference_pnl": pnl,
                "stock_reference_return_fraction": pnl / allocation,
                "stock_shares": shares,
            })
    # Preserve each structurally selected option, including missing snapshots.
    if not case.option_symbol:
        if option or case.option_expiration or case.option_multiplier:
            raise CommonClockScenarioError("unselected option cannot carry quote evidence")
        result["option_status"] = "NO_STRUCTURALLY_SELECTED_CONTRACT"
    elif option:
        assert opt_entry_stamp is not None and opt_exit_stamp is not None
        match = re.fullmatch(r"([A-Z0-9.]+)(\\d{6})([CP])(\\d{8})", case.option_symbol)
        if (
            match is None or case.option_expiration is None
            or match.group(2) != case.option_expiration.strftime("%y%m%d")
            or match.group(3) != {"call": "C", "put": "P"}.get(case.option_right)
        ):
            raise CommonClockScenarioError("original OCC option right/expiry changed")
        if (
            case.option_right not in ("call", "put")
            or case.option_expiration is None
            or case.option_multiplier != 100
            or case.standard_deliverable_verified is not True
        ):
            result["option_status"] = "UNVERIFIED_CONTRACT_DELIVERABLE"
        elif not stock:
            result["option_status"] = "NO_MATCHED_STOCK_ENTRY_EXIT_FOR_COMPARISON"
        elif (
            case.option_entry_ask.session != case.stock_entry.session
            or case.option_exit_bid.session != case.stock_exit.session
            or opt_entry_stamp <= signal
            or opt_exit_stamp <= opt_entry_stamp
            or case.option_expiration < case.option_exit_bid.session
            or abs(opt_entry_stamp - entry_stamp) > MAX_MARK_SKEW
            or abs(opt_exit_stamp - exit_stamp) > MAX_MARK_SKEW
        ):
            result["option_status"] = "UNMATCHED_EOD_OBSERVATION_CLOCK"
        else:
            per_contract_debit = (
                case.option_entry_ask.per_share * case.option_multiplier
                + option_round_trip_fee_per_contract / 2
            )
            contracts = floor(allocation / per_contract_debit)
            if contracts < 1:
                result["option_status"] = "INSUFFICIENT_OPTION_ALLOCATION"
            else:
                pnl = contracts * (
                    (case.option_exit_bid.per_share - case.option_entry_ask.per_share)
                    * case.option_multiplier - option_round_trip_fee_per_contract
                )
                result.update({
                    "option_status": "ILLUSTRATIVE_OBSERVED_OPTION_ASK_TO_BID_EOD_REFERENCE",
                    "option_reference_pnl": pnl,
                    "option_reference_return_fraction": pnl / allocation,
                    "option_contracts": contracts,
                })
    elif case.option_reference_status not in {
        "NO_LATER_TWO_SIDED_REFERENCE",
        "ENTRY_REFERENCE_ONLY_NO_SUBSEQUENT_REFERENCE",
        "NOT_ACQUIRED",
        "EXACT_QUERY_SOURCE_GAP",
    }:
        raise CommonClockScenarioError("accepted option path missing required actual mark")
    result["paired_observation_coverage"] = (
        result["stock_reference_pnl"] is not None
        and result["option_reference_pnl"] is not None
    )
    result["result_fingerprint"] = _fingerprint(result)
    return result


def compare_cases(cases: list[SameClockCase], **kwargs: Any) -> dict[str, Any]:
    """Report every original signal; never present available-pair subset as all."""
    if not cases or len({case.case_id for case in cases}) != len(cases):
        raise CommonClockScenarioError("nonempty unique original signal cases required")
    rows = [compare_case(case, **kwargs) for case in cases]
    year_groups: dict[str, dict[str, Any]] = {}
    for year in range(2021, 2027):
        subset = [x for x in rows if x["year"] == year]
        statuses = Counter(x["option_status"] for x in subset)
        year_groups[str(year)] = {
            "full_signal_denominator": len(subset),
            "paired_eod_reference_count": sum(x["paired_observation_coverage"] for x in subset),
            "option_statuses": dict(sorted(statuses.items())),
        }
    output = {
        "contract": CONTRACT,
        "status": "CROSS_INSTRUMENT_COMMON_CLOCK_REFERENCE_ONLY",
        "full_signal_denominator": len(rows),
        "paired_reference_count": sum(r["paired_observation_coverage"] for r in rows),
        "by_calendar_year": year_groups,
        "provider_requests": 0,
        "actual_fills": 0,
        "portfolio_return": None,
        "protected_holdout_is_fresh": False,
        "paper": False,
        "live": False,
        "rows": rows,
    }
    output["report_fingerprint"] = _fingerprint(output)
    return output
