from __future__ import annotations

import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

from packages.core.atomic_io import atomic_write_text
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_storage import AlpacaRawPayloadStore
from packages.providers.alpaca import AlpacaMarketDataClient

from .literature_momseason_policy import (
    LITERATURE_MOMSEASON_FORMATION_START,
    required_lag_reference_dates,
)
from .literature_momseason_source import (
    MOMSEASON_SOURCE_ROOT_RELATIVE,
    MomSeasonSourceAcquirer,
    canonical_json,
    read_gzip_jsonl,
    write_gzip_jsonl,
)


MOMSEASON_TOTAL_RETURN_SOURCE_AUDIT_VERSION = (
    "literature-momseason-total-return-source-audit-v1-pre-target-dual-provider"
)
ALPACA_RESEARCH_NAMESPACE = "literature_momseason_total_return"
MOMSEASON_TOTAL_RETURN_AUDIT_REPORT = "total_return_source_audit.json"
MOMSEASON_TOTAL_RETURN_ALPACA_ACTIONS = "alpaca_corporate_actions.jsonl.gz"
MOMSEASON_TOTAL_RETURN_PRICE_CASES = "alpaca_price_audit_cases.jsonl.gz"

# No Alpaca bar used by this audit may overlap a LIT-01 target month. LIT-01
# formation/target months begin in September 2021, so this boundary is frozen
# at the final day before the first formation month.
MOMSEASON_TOTAL_RETURN_BAR_AUDIT_END = LITERATURE_MOMSEASON_FORMATION_START - timedelta(days=1)

MOMSEASON_AUDIT_MISSING_FACTOR_DIVIDENDS = 12
MOMSEASON_AUDIT_FACTOR_DIVIDENDS = 6
MOMSEASON_AUDIT_SPLITS = 8

_ALPACA_ACTION_COLLECTION_TYPES = {
    "cash_dividends": "cash_dividend",
    "stock_dividends": "stock_dividend",
    "forward_splits": "forward_split",
    "reverse_splits": "reverse_split",
    "unit_splits": "unit_split",
    "spin_offs": "spin_off",
    "cash_mergers": "cash_merger",
    "stock_mergers": "stock_merger",
    "stock_and_cash_mergers": "stock_and_cash_merger",
    "redemptions": "redemption",
    "name_changes": "name_change",
    "worthless_removals": "worthless_removal",
    "rights_distributions": "rights_distribution",
    "partial_calls": "partial_call",
    "reorganizations": "reorganization",
}


def _parse_date(value: object) -> date | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _finite_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _relative_error(observed: float | None, expected: float | None) -> float | None:
    if observed is None or expected is None or expected == 0:
        return None
    return abs(observed - expected) / abs(expected)


def _evenly_spaced_sample(rows: list[dict[str, object]], count: int) -> list[dict[str, object]]:
    """Select deterministic coverage across the full sorted source history."""

    if count <= 0 or not rows:
        return []
    if len(rows) <= count:
        return list(rows)
    if count == 1:
        return [rows[len(rows) // 2]]
    indexes = {
        round(index * (len(rows) - 1) / (count - 1))
        for index in range(count)
    }
    return [rows[index] for index in sorted(indexes)]


def _action_container(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("corporate_actions")
    if isinstance(nested, dict):
        return nested
    return payload


def normalize_alpaca_action_page(
    payload: object,
    *,
    source_page_sha256: str,
) -> list[dict[str, object]]:
    """Flatten Alpaca's per-action-type response arrays without losing raw lineage."""

    container = _action_container(payload)
    result: list[dict[str, object]] = []
    for collection, action_type in _ALPACA_ACTION_COLLECTION_TYPES.items():
        values = container.get(collection)
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, dict):
                continue
            row = dict(value)
            row["_alpaca_collection"] = collection
            row["_alpaca_action_type"] = action_type
            row["_source_page_sha256"] = source_page_sha256
            result.append(row)
    result.sort(
        key=lambda row: (
            str(row.get("process_date") or ""),
            str(row.get("ex_date") or row.get("effective_date") or ""),
            str(row.get("symbol") or row.get("old_symbol") or ""),
            str(row.get("_alpaca_action_type") or ""),
            str(row.get("id") or ""),
        )
    )
    return result


def extract_alpaca_bar_closes(payload: object, symbol: str) -> dict[date, float]:
    """Extract positive finite daily closes for one literal response symbol."""

    if not isinstance(payload, dict):
        return {}
    bars = payload.get("bars")
    if not isinstance(bars, dict):
        return {}
    values = bars.get(symbol)
    if not isinstance(values, list):
        return {}
    result: dict[date, float] = {}
    for item in values:
        if not isinstance(item, dict):
            continue
        session = _parse_date(item.get("t"))
        close = _finite_float(item.get("c"))
        if session is None or close is None or close <= 0:
            continue
        if session in result and not math.isclose(result[session], close, rel_tol=0.0, abs_tol=0.0):
            raise ValueError(f"duplicate Alpaca daily close for {symbol} on {session}")
        result[session] = close
    return result


def _massive_dividend_amounts(row: dict[str, object]) -> tuple[float, ...]:
    values: list[float] = []
    for key in ("cash_amount", "split_adjusted_cash_amount"):
        value = _finite_float(row.get(key))
        if value is not None and value >= 0 and value not in values:
            values.append(value)
    return tuple(values)


def _massive_split_ratio(row: dict[str, object]) -> float | None:
    split_from = _finite_float(row.get("split_from"))
    split_to = _finite_float(row.get("split_to"))
    if split_from is None or split_to is None or split_from <= 0 or split_to <= 0:
        return None
    return split_to / split_from


def _alpaca_split_ratio(row: dict[str, object]) -> float | None:
    old_rate = _finite_float(row.get("old_rate"))
    new_rate = _finite_float(row.get("new_rate"))
    if old_rate is None or new_rate is None or old_rate <= 0 or new_rate <= 0:
        return None
    return new_rate / old_rate


def _best_action_match(
    case: dict[str, object],
    alpaca_actions: list[dict[str, object]],
) -> dict[str, object]:
    ticker = str(case["ticker"])
    event_date = str(case["event_date"])
    kind = str(case["kind"])

    if kind.startswith("dividend_"):
        candidates = [
            row
            for row in alpaca_actions
            if row.get("_alpaca_action_type") == "cash_dividend"
            and str(row.get("symbol") or "") == ticker
            and str(row.get("ex_date") or "") == event_date
        ]
        expected_values = tuple(case.get("massive_cash_amounts") or ())
        ranked: list[tuple[float, dict[str, object]]] = []
        for row in candidates:
            rate = _finite_float(row.get("rate"))
            if rate is None or not expected_values:
                difference = math.inf
            else:
                difference = min(abs(rate - float(value)) for value in expected_values)
            ranked.append((difference, row))
        ranked.sort(key=lambda item: (item[0], str(item[1].get("id") or "")))
        match = ranked[0][1] if ranked else None
        observed = _finite_float(match.get("rate")) if match is not None else None
        expected = None
        if observed is not None and expected_values:
            expected = min((float(value) for value in expected_values), key=lambda value: abs(value - observed))
        return {
            "alpaca_action_match": match is not None,
            "alpaca_action_id": match.get("id") if match is not None else None,
            "alpaca_action_type": match.get("_alpaca_action_type") if match is not None else None,
            "alpaca_value": observed,
            "massive_comparison_value": expected,
            "value_absolute_difference": (
                abs(observed - expected)
                if observed is not None and expected is not None
                else None
            ),
            "value_relative_error": _relative_error(observed, expected),
        }

    candidates = [
        row
        for row in alpaca_actions
        if row.get("_alpaca_action_type") in {"forward_split", "reverse_split"}
        and str(row.get("symbol") or "") == ticker
        and str(row.get("ex_date") or "") == event_date
    ]
    expected_ratio = _finite_float(case.get("massive_split_ratio"))
    ranked = []
    for row in candidates:
        ratio = _alpaca_split_ratio(row)
        difference = (
            abs(ratio - expected_ratio)
            if ratio is not None and expected_ratio is not None
            else math.inf
        )
        ranked.append((difference, row))
    ranked.sort(key=lambda item: (item[0], str(item[1].get("id") or "")))
    match = ranked[0][1] if ranked else None
    observed_ratio = _alpaca_split_ratio(match) if match is not None else None
    return {
        "alpaca_action_match": match is not None,
        "alpaca_action_id": match.get("id") if match is not None else None,
        "alpaca_action_type": match.get("_alpaca_action_type") if match is not None else None,
        "alpaca_value": observed_ratio,
        "massive_comparison_value": expected_ratio,
        "value_absolute_difference": (
            abs(observed_ratio - expected_ratio)
            if observed_ratio is not None and expected_ratio is not None
            else None
        ),
        "value_relative_error": _relative_error(observed_ratio, expected_ratio),
    }


class MomSeasonTotalReturnSourceAudit:
    """Audit Alpaca total-return semantics against Massive before any target read.

    This package is intentionally source-only. Corporate-action metadata is acquired
    only through the final pre-formation date, and every price window is bracketed
    entirely before September 2021. Therefore the audit cannot read a LIT-01 target
    month, the existing protected window, broker state, orders, PAPER, or LIVE state.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        alpaca_client: AlpacaMarketDataClient | None = None,
    ) -> None:
        self.settings = settings
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        self.massive = MomSeasonSourceAcquirer(settings)
        self.alpaca = alpaca_client or AlpacaMarketDataClient(settings)
        self.raw_store = AlpacaRawPayloadStore(
            settings, namespace=ALPACA_RESEARCH_NAMESPACE
        )
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / MOMSEASON_SOURCE_ROOT_RELATIVE / "total_return_source"

    def alpaca_actions_path(self) -> Path:
        return self.root / MOMSEASON_TOTAL_RETURN_ALPACA_ACTIONS

    def price_cases_path(self) -> Path:
        return self.root / MOMSEASON_TOTAL_RETURN_PRICE_CASES

    def report_path(self) -> Path:
        return self.root / MOMSEASON_TOTAL_RETURN_AUDIT_REPORT

    def _safe_source_start(self) -> date:
        return min(required_lag_reference_dates(self.calendar))

    def _massive_prerequisites_available(self) -> bool:
        return all(
            self.massive.action_path(name).is_file()
            for name in ("splits", "dividends")
        )

    def _load_massive_actions(self) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        return (
            read_gzip_jsonl(self.massive.action_path("splits")),
            read_gzip_jsonl(self.massive.action_path("dividends")),
        )

    def _select_cases(self) -> list[dict[str, object]]:
        splits, dividends = self._load_massive_actions()
        start = self._safe_source_start()
        end = MOMSEASON_TOTAL_RETURN_BAR_AUDIT_END

        missing_factor_dividends: list[dict[str, object]] = []
        factor_dividends: list[dict[str, object]] = []
        for row in dividends:
            event_date = _parse_date(row.get("ex_dividend_date"))
            ticker = str(row.get("ticker") or "")
            amounts = _massive_dividend_amounts(row)
            if not ticker or event_date is None or not (start <= event_date <= end) or not amounts:
                continue
            case = {
                "kind": (
                    "dividend_missing_factor"
                    if row.get("historical_adjustment_factor") in (None, "")
                    else "dividend_with_factor"
                ),
                "ticker": ticker,
                "event_date": event_date.isoformat(),
                "massive_action_id": row.get("id"),
                "massive_cash_amounts": list(amounts),
                "massive_historical_adjustment_factor": row.get(
                    "historical_adjustment_factor"
                ),
            }
            if case["kind"] == "dividend_missing_factor":
                missing_factor_dividends.append(case)
            else:
                factor_dividends.append(case)

        split_cases: list[dict[str, object]] = []
        for row in splits:
            event_date = _parse_date(row.get("execution_date"))
            ticker = str(row.get("ticker") or "")
            ratio = _massive_split_ratio(row)
            if not ticker or event_date is None or not (start <= event_date <= end) or ratio is None:
                continue
            split_cases.append(
                {
                    "kind": "split",
                    "ticker": ticker,
                    "event_date": event_date.isoformat(),
                    "massive_action_id": row.get("id"),
                    "massive_split_ratio": ratio,
                    "massive_historical_adjustment_factor": row.get(
                        "historical_adjustment_factor"
                    ),
                }
            )

        sort_key = lambda row: (
            str(row["event_date"]),
            str(row["ticker"]),
            str(row.get("massive_action_id") or ""),
        )
        missing_factor_dividends.sort(key=sort_key)
        factor_dividends.sort(key=sort_key)
        split_cases.sort(key=sort_key)

        selected = [
            *_evenly_spaced_sample(
                missing_factor_dividends, MOMSEASON_AUDIT_MISSING_FACTOR_DIVIDENDS
            ),
            *_evenly_spaced_sample(
                factor_dividends, MOMSEASON_AUDIT_FACTOR_DIVIDENDS
            ),
            *_evenly_spaced_sample(split_cases, MOMSEASON_AUDIT_SPLITS),
        ]
        selected.sort(key=lambda row: (str(row["event_date"]), str(row["ticker"]), str(row["kind"])))
        for index, row in enumerate(selected, start=1):
            row["case_id"] = f"case_{index:03d}_{row['kind']}_{row['ticker']}_{row['event_date']}"
        return selected

    def _bracketing_sessions(self, event_date: date) -> tuple[date, date] | None:
        sessions = tuple(
            self.calendar.sessions_in_range(
                event_date - timedelta(days=10),
                event_date + timedelta(days=10),
            )
        )
        prior = [item for item in sessions if item < event_date]
        on_or_after = [item for item in sessions if item >= event_date]
        if not prior or not on_or_after:
            return None
        start = prior[-1]
        end = on_or_after[0]
        if end > MOMSEASON_TOTAL_RETURN_BAR_AUDIT_END:
            return None
        return start, end

    def acquire_alpaca_actions(self, *, force: bool = False) -> dict[str, object]:
        target = self.alpaca_actions_path()
        if target.is_file() and not force:
            rows = read_gzip_jsonl(target)
            return {"path": str(target), "skipped": True, "row_count": len(rows)}

        start = self._safe_source_start()
        end = MOMSEASON_TOTAL_RETURN_BAR_AUDIT_END
        rows: list[dict[str, object]] = []
        page_count = 0
        for page in self.alpaca.corporate_action_pages(
            start=start.isoformat(), end=end.isoformat()
        ):
            raw_record = self.raw_store.persist(
                page,
                category="corporate_actions",
                partition=f"{start.isoformat()}_{end.isoformat()}",
            )
            rows.extend(
                normalize_alpaca_action_page(
                    page.payload,
                    source_page_sha256=raw_record.sha256,
                )
            )
            page_count += 1
            print(
                "LIT-01 Alpaca corporate actions: "
                f"page={page_count} normalized_rows={len(rows)}"
            )
        count = write_gzip_jsonl(target, rows)
        return {
            "path": str(target),
            "skipped": False,
            "page_count": page_count,
            "row_count": count,
        }

    def _acquire_case_prices(
        self,
        case: dict[str, object],
        alpaca_actions: list[dict[str, object]],
    ) -> dict[str, object]:
        event_date = date.fromisoformat(str(case["event_date"]))
        bracket = self._bracketing_sessions(event_date)
        result = dict(case)
        result.update(_best_action_match(case, alpaca_actions))
        if bracket is None:
            result["price_status"] = "NO_SAFE_SESSION_BRACKET"
            return result
        start, end = bracket
        result["price_start_session"] = start.isoformat()
        result["price_end_session"] = end.isoformat()

        closes_by_adjustment: dict[str, dict[date, float]] = {}
        page_hashes: dict[str, list[str]] = {"raw": [], "all": []}
        for adjustment in ("raw", "all"):
            closes: dict[date, float] = {}
            for page in self.alpaca.historical_bar_pages(
                symbols=[str(case["ticker"])],
                start=start.isoformat(),
                end=end.isoformat(),
                adjustment=adjustment,
                asof="-",
                timeframe="1Day",
            ):
                raw_record = self.raw_store.persist(
                    page,
                    category=f"bars_{adjustment}",
                    partition=str(case["case_id"]),
                )
                page_hashes[adjustment].append(raw_record.sha256)
                page_closes = extract_alpaca_bar_closes(page.payload, str(case["ticker"]))
                for session, close in page_closes.items():
                    if session in closes and not math.isclose(
                        closes[session], close, rel_tol=0.0, abs_tol=0.0
                    ):
                        raise ValueError(
                            f"conflicting Alpaca {adjustment} close for "
                            f"{case['ticker']} on {session}"
                        )
                    closes[session] = close
            closes_by_adjustment[adjustment] = closes

        raw_start = closes_by_adjustment["raw"].get(start)
        raw_end = closes_by_adjustment["raw"].get(end)
        adjusted_start = closes_by_adjustment["all"].get(start)
        adjusted_end = closes_by_adjustment["all"].get(end)
        result.update(
            {
                "raw_source_page_sha256": page_hashes["raw"],
                "adjusted_all_source_page_sha256": page_hashes["all"],
                "raw_start_close": raw_start,
                "raw_end_close": raw_end,
                "adjusted_start_close": adjusted_start,
                "adjusted_end_close": adjusted_end,
            }
        )
        if None in {raw_start, raw_end, adjusted_start, adjusted_end}:
            result["price_status"] = "INCOMPLETE_ALPACA_ENDPOINTS"
            return result

        assert raw_start is not None
        assert raw_end is not None
        assert adjusted_start is not None
        assert adjusted_end is not None
        raw_return = raw_end / raw_start - 1.0
        adjusted_return = adjusted_end / adjusted_start - 1.0
        start_scale = adjusted_start / raw_start
        end_scale = adjusted_end / raw_end
        scale_change = end_scale / start_scale

        if str(case["kind"]) == "split":
            expected_scale_change = _finite_float(case.get("massive_split_ratio"))
        else:
            action_rate = _finite_float(result.get("alpaca_value"))
            if action_rate is None:
                amounts = tuple(case.get("massive_cash_amounts") or ())
                action_rate = _finite_float(amounts[0]) if amounts else None
            expected_scale_change = (
                raw_start / (raw_start - action_rate)
                if action_rate is not None and 0 <= action_rate < raw_start
                else None
            )

        result.update(
            {
                "price_status": "COMPLETE",
                "raw_return": raw_return,
                "adjusted_total_return": adjusted_return,
                "adjusted_minus_raw_return": adjusted_return - raw_return,
                "start_adjustment_scale": start_scale,
                "end_adjustment_scale": end_scale,
                "observed_scale_change": scale_change,
                "expected_event_scale_change": expected_scale_change,
                "scale_change_relative_error": _relative_error(
                    scale_change, expected_scale_change
                ),
            }
        )
        return result

    def acquire_price_audit_cases(self, *, force: bool = False) -> dict[str, object]:
        target = self.price_cases_path()
        if target.is_file() and not force:
            rows = read_gzip_jsonl(target)
            return {"path": str(target), "skipped": True, "row_count": len(rows)}
        if not self.alpaca_actions_path().is_file():
            raise RuntimeError("Alpaca corporate-action cache is required before price audit")

        alpaca_actions = read_gzip_jsonl(self.alpaca_actions_path())
        cases = self._select_cases()
        results: list[dict[str, object]] = []
        for index, case in enumerate(cases, start=1):
            item = self._acquire_case_prices(case, alpaca_actions)
            results.append(item)
            print(
                "LIT-01 Alpaca adjusted-price audit: "
                f"{index}/{len(cases)} case={case['case_id']} "
                f"action_match={item.get('alpaca_action_match')} "
                f"price_status={item.get('price_status')}"
            )
        count = write_gzip_jsonl(target, results)
        return {"path": str(target), "skipped": False, "row_count": count}

    @staticmethod
    def _metric_summary(values: Iterable[float | None]) -> dict[str, float | int | None]:
        clean = sorted(float(value) for value in values if value is not None and math.isfinite(value))
        if not clean:
            return {"count": 0, "min": None, "median": None, "max": None}
        middle = len(clean) // 2
        if len(clean) % 2:
            median = clean[middle]
        else:
            median = (clean[middle - 1] + clean[middle]) / 2.0
        return {
            "count": len(clean),
            "min": clean[0],
            "median": median,
            "max": clean[-1],
        }

    def run(
        self,
        *,
        acquire: bool = False,
        force_acquire: bool = False,
    ) -> dict[str, object]:
        if not self._massive_prerequisites_available():
            report = {
                "status": "TOTAL_RETURN_SOURCE_PREREQUISITE_REQUIRED",
                "audit_version": MOMSEASON_TOTAL_RETURN_SOURCE_AUDIT_VERSION,
                "note": "Run the accepted LIT-01 Massive source acquisition first.",
                "target_outcome_rows_read": 0,
                "protected_return_rows_read": 0,
                "protected_holdout_consumed": False,
                "provider_writes_performed": 0,
                "broker_reads_performed": 0,
                "broker_writes_performed": 0,
                "order_writes_performed": 0,
                "paper_submits_performed": 0,
                "live_writes_performed": 0,
            }
            self.root.mkdir(parents=True, exist_ok=True)
            atomic_write_text(self.report_path(), canonical_json(report) + "\n")
            report["report_path"] = str(self.report_path())
            return report

        acquisition: dict[str, object] | None = None
        if acquire:
            acquisition = {
                "alpaca_corporate_actions": self.acquire_alpaca_actions(force=force_acquire),
            }
            acquisition["alpaca_price_audit_cases"] = self.acquire_price_audit_cases(
                force=force_acquire
            )

        actions_available = self.alpaca_actions_path().is_file()
        prices_available = self.price_cases_path().is_file()
        cases = read_gzip_jsonl(self.price_cases_path()) if prices_available else []
        complete_cases = [row for row in cases if row.get("price_status") == "COMPLETE"]
        matched_cases = [row for row in cases if row.get("alpaca_action_match") is True]
        by_kind: dict[str, dict[str, int]] = {}
        for kind in ("dividend_missing_factor", "dividend_with_factor", "split"):
            kind_rows = [row for row in cases if row.get("kind") == kind]
            by_kind[kind] = {
                "selected": len(kind_rows),
                "alpaca_action_matched": sum(
                    row.get("alpaca_action_match") is True for row in kind_rows
                ),
                "complete_price_cases": sum(
                    row.get("price_status") == "COMPLETE" for row in kind_rows
                ),
            }

        if not actions_available or not prices_available:
            status = "TOTAL_RETURN_SOURCE_ACQUISITION_REQUIRED"
        elif not cases or not complete_cases:
            status = "TOTAL_RETURN_SOURCE_AUDIT_INSUFFICIENT"
        else:
            # Deliberately not called PASS: the first real provider response must be
            # inspected before ATLAS freezes mechanical reconciliation tolerances.
            status = "TOTAL_RETURN_SOURCE_AUDIT_READY_FOR_REVIEW"

        report = {
            "status": status,
            "audit_version": MOMSEASON_TOTAL_RETURN_SOURCE_AUDIT_VERSION,
            "safe_bar_audit_start": self._safe_source_start().isoformat(),
            "safe_bar_audit_end": MOMSEASON_TOTAL_RETURN_BAR_AUDIT_END.isoformat(),
            "first_lit01_target_month": LITERATURE_MOMSEASON_FORMATION_START.isoformat(),
            "alpaca_global_adjustment_config_mutated": False,
            "existing_canonical_market_data_mutated": False,
            "alpaca_actions_available": actions_available,
            "alpaca_price_cases_available": prices_available,
            "selected_case_count": len(cases),
            "alpaca_action_match_count": len(matched_cases),
            "complete_price_case_count": len(complete_cases),
            "case_counts": by_kind,
            "value_relative_error": self._metric_summary(
                _finite_float(row.get("value_relative_error")) for row in matched_cases
            ),
            "scale_change_relative_error": self._metric_summary(
                _finite_float(row.get("scale_change_relative_error"))
                for row in complete_cases
            ),
            "acquisition": acquisition,
            "note": (
                "This source-only audit compares Massive split/dividend evidence with "
                "Alpaca corporate actions and raw-versus-adjustment=all daily bars using "
                "only dates before the first LIT-01 target month. READY_FOR_REVIEW is "
                "not scientific acceptance and does not open development outcomes."
            ),
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_writes_performed": 0,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path(), canonical_json(report) + "\n")
        report["report_path"] = str(self.report_path())
        return report


assert MOMSEASON_TOTAL_RETURN_BAR_AUDIT_END < LITERATURE_MOMSEASON_FORMATION_START
