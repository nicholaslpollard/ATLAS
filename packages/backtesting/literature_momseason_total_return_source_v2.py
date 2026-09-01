from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Iterable

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.providers.alpaca import AlpacaMarketDataClient

from .literature_momseason_policy import LITERATURE_MOMSEASON_FORMATION_START
from .literature_momseason_source import canonical_json, read_gzip_jsonl, write_gzip_jsonl
from .literature_momseason_total_return_source import (
    ALPACA_RESEARCH_NAMESPACE,
    MOMSEASON_AUDIT_FACTOR_DIVIDENDS,
    MOMSEASON_AUDIT_MISSING_FACTOR_DIVIDENDS,
    MOMSEASON_AUDIT_SPLITS,
    MOMSEASON_TOTAL_RETURN_BAR_AUDIT_END,
    MomSeasonTotalReturnSourceAudit,
    _alpaca_split_ratio,
    _evenly_spaced_sample,
    _finite_float,
    _relative_error,
    extract_alpaca_bar_closes,
)


MOMSEASON_TOTAL_RETURN_SOURCE_AUDIT_V2_VERSION = (
    "literature-momseason-total-return-source-audit-v2-overlap-stratified-pre-target"
)
MOMSEASON_TOTAL_RETURN_PRICE_CASES_V2 = "price_audit_cases_v2.jsonl.gz"
MOMSEASON_TOTAL_RETURN_AUDIT_REPORT_V2 = "total_return_source_audit_v2.json"
MOMSEASON_TOTAL_RETURN_COVERAGE_EXAMPLES_V2 = "coverage_examples_v2.jsonl.gz"
MOMSEASON_AUDIT_COVERAGE_EXAMPLES_PER_KIND = 5


ActionIndex = dict[tuple[str, str, str], list[dict[str, object]]]


def _alpaca_action_key(row: dict[str, object]) -> tuple[str, str, str] | None:
    action_type = str(row.get("_alpaca_action_type") or "")
    ticker = str(row.get("symbol") or "")
    event_date = str(row.get("ex_date") or "")
    if not ticker or not event_date:
        return None
    if action_type == "cash_dividend":
        return ("dividend", ticker, event_date)
    if action_type in {"forward_split", "reverse_split"}:
        return ("split", ticker, event_date)
    return None


def build_alpaca_action_index(rows: Iterable[dict[str, object]]) -> ActionIndex:
    index: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        key = _alpaca_action_key(row)
        if key is not None:
            index[key].append(row)
    for values in index.values():
        values.sort(key=lambda row: str(row.get("id") or ""))
    return dict(index)


def _massive_case_key(case: dict[str, object]) -> tuple[str, str, str]:
    kind = str(case["kind"])
    family = "dividend" if kind.startswith("dividend_") else "split"
    return family, str(case["ticker"]), str(case["event_date"])


def _massive_dividend_cash_amount(row: dict[str, object]) -> float | None:
    # Massive documents cash_amount as the original per-share payment. That is the
    # amount compatible with raw prices around the historical ex-date. The separate
    # split_adjusted_cash_amount is normalized to the current share basis and is kept
    # only as provenance/diagnostic evidence below.
    value = _finite_float(row.get("cash_amount"))
    if value is not None and value >= 0:
        return value
    fallback = _finite_float(row.get("split_adjusted_cash_amount"))
    return fallback if fallback is not None and fallback >= 0 else None


def _massive_split_ratio(row: dict[str, object]) -> float | None:
    split_from = _finite_float(row.get("split_from"))
    split_to = _finite_float(row.get("split_to"))
    if split_from is None or split_to is None or split_from <= 0 or split_to <= 0:
        return None
    return split_to / split_from


def _best_overlap_match(
    case: dict[str, object],
    candidates: list[dict[str, object]],
) -> dict[str, object]:
    kind = str(case["kind"])
    if not candidates:
        return {
            "alpaca_action_match": False,
            "alpaca_action_id": None,
            "alpaca_action_type": None,
            "alpaca_value": None,
            "massive_comparison_value": None,
            "value_absolute_difference": None,
            "value_relative_error": None,
        }

    if kind.startswith("dividend_"):
        massive_value = _finite_float(case.get("massive_cash_amount"))
        ranked: list[tuple[float, str, dict[str, object]]] = []
        for row in candidates:
            alpaca_value = _finite_float(row.get("rate"))
            difference = (
                abs(alpaca_value - massive_value)
                if alpaca_value is not None and massive_value is not None
                else math.inf
            )
            ranked.append((difference, str(row.get("id") or ""), row))
        ranked.sort(key=lambda item: (item[0], item[1]))
        match = ranked[0][2]
        alpaca_value = _finite_float(match.get("rate"))
    else:
        massive_value = _finite_float(case.get("massive_split_ratio"))
        ranked = []
        for row in candidates:
            alpaca_value = _alpaca_split_ratio(row)
            difference = (
                abs(alpaca_value - massive_value)
                if alpaca_value is not None and massive_value is not None
                else math.inf
            )
            ranked.append((difference, str(row.get("id") or ""), row))
        ranked.sort(key=lambda item: (item[0], item[1]))
        match = ranked[0][2]
        alpaca_value = _alpaca_split_ratio(match)

    return {
        "alpaca_action_match": True,
        "alpaca_action_id": match.get("id"),
        "alpaca_action_type": match.get("_alpaca_action_type"),
        "alpaca_value": alpaca_value,
        "massive_comparison_value": massive_value,
        "value_absolute_difference": (
            abs(alpaca_value - massive_value)
            if alpaca_value is not None and massive_value is not None
            else None
        ),
        "value_relative_error": _relative_error(alpaca_value, massive_value),
    }


def expected_scale_change_from_massive(
    case: dict[str, object], raw_start: float
) -> float | None:
    if str(case["kind"]) == "split":
        return _finite_float(case.get("massive_split_ratio"))
    amount = _finite_float(case.get("massive_cash_amount"))
    if amount is None or amount < 0 or amount >= raw_start:
        return None
    return raw_start / (raw_start - amount)


def expected_scale_change_from_alpaca(
    case: dict[str, object], raw_start: float
) -> float | None:
    value = _finite_float(case.get("alpaca_value"))
    if value is None:
        return None
    if str(case["kind"]) == "split":
        return value if value > 0 else None
    if value < 0 or value >= raw_start:
        return None
    return raw_start / (raw_start - value)


class MomSeasonTotalReturnSourceAuditV2(MomSeasonTotalReturnSourceAudit):
    """Overlap-stratified v2 audit preserving the v1 result as immutable evidence.

    V2 fixes two source-methodology issues discovered by the first real provider run:

    * adjustment-validation cases are selected from exact Massive/Alpaca action
      overlaps before any adjusted price is inspected; non-overlaps are reported as a
      separate coverage diagnostic rather than being treated as adjustment failures;
    * Alpaca historical bars use the event date as the symbol ``asof`` date, allowing
      provider-supported entity/name mapping while remaining point-in-time to the
      source event.

    The expected adjustment is computed independently from Massive's original
    ``cash_amount`` or split ratio and from Alpaca's action value. This means a blank
    Massive cumulative ``historical_adjustment_factor`` does not make the test
    circular: the Massive amount itself must explain Alpaca's raw-vs-all price scale.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        alpaca_client: AlpacaMarketDataClient | None = None,
    ) -> None:
        super().__init__(settings, alpaca_client=alpaca_client)

    def price_cases_v2_path(self) -> Path:
        return self.root / MOMSEASON_TOTAL_RETURN_PRICE_CASES_V2

    def coverage_examples_v2_path(self) -> Path:
        return self.root / MOMSEASON_TOTAL_RETURN_COVERAGE_EXAMPLES_V2

    def report_v2_path(self) -> Path:
        return self.root / MOMSEASON_TOTAL_RETURN_AUDIT_REPORT_V2

    def _all_massive_cases(self) -> list[dict[str, object]]:
        splits, dividends = self._load_massive_actions()
        start = self._safe_source_start()
        end = MOMSEASON_TOTAL_RETURN_BAR_AUDIT_END
        cases: list[dict[str, object]] = []

        for row in dividends:
            event_text = str(row.get("ex_dividend_date") or "")
            ticker = str(row.get("ticker") or "")
            try:
                event_date = date.fromisoformat(event_text)
            except ValueError:
                continue
            amount = _massive_dividend_cash_amount(row)
            if (
                not ticker
                or amount is None
                or not (start <= event_date <= end)
            ):
                continue
            cases.append(
                {
                    "kind": (
                        "dividend_missing_factor"
                        if row.get("historical_adjustment_factor") in (None, "")
                        else "dividend_with_factor"
                    ),
                    "ticker": ticker,
                    "event_date": event_date.isoformat(),
                    "massive_action_id": row.get("id"),
                    "massive_cash_amount": amount,
                    "massive_split_adjusted_cash_amount": row.get(
                        "split_adjusted_cash_amount"
                    ),
                    "massive_historical_adjustment_factor": row.get(
                        "historical_adjustment_factor"
                    ),
                }
            )

        for row in splits:
            event_text = str(row.get("execution_date") or "")
            ticker = str(row.get("ticker") or "")
            try:
                event_date = date.fromisoformat(event_text)
            except ValueError:
                continue
            ratio = _massive_split_ratio(row)
            if (
                not ticker
                or ratio is None
                or not (start <= event_date <= end)
            ):
                continue
            cases.append(
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

        cases.sort(
            key=lambda row: (
                str(row["kind"]),
                str(row["event_date"]),
                str(row["ticker"]),
                str(row.get("massive_action_id") or ""),
            )
        )
        return cases

    def _selection(self) -> tuple[list[dict[str, object]], dict[str, object], list[dict[str, object]]]:
        if not self.alpaca_actions_path().is_file():
            raise RuntimeError("v1 Alpaca corporate-action cache is required for v2 selection")
        alpaca_actions = read_gzip_jsonl(self.alpaca_actions_path())
        index = build_alpaca_action_index(alpaca_actions)
        massive_cases = self._all_massive_cases()

        by_kind_overlap: dict[str, list[dict[str, object]]] = defaultdict(list)
        by_kind_nonoverlap: dict[str, list[dict[str, object]]] = defaultdict(list)
        for case in massive_cases:
            candidates = index.get(_massive_case_key(case), [])
            enriched = dict(case)
            enriched.update(_best_overlap_match(case, candidates))
            bucket = by_kind_overlap if candidates else by_kind_nonoverlap
            bucket[str(case["kind"])].append(enriched)

        counts_requested = {
            "dividend_missing_factor": MOMSEASON_AUDIT_MISSING_FACTOR_DIVIDENDS,
            "dividend_with_factor": MOMSEASON_AUDIT_FACTOR_DIVIDENDS,
            "split": MOMSEASON_AUDIT_SPLITS,
        }
        selected: list[dict[str, object]] = []
        coverage_examples: list[dict[str, object]] = []
        summary: dict[str, object] = {}
        for kind, requested in counts_requested.items():
            overlap = sorted(
                by_kind_overlap.get(kind, []),
                key=lambda row: (
                    str(row["event_date"]),
                    str(row["ticker"]),
                    str(row.get("massive_action_id") or ""),
                ),
            )
            nonoverlap = sorted(
                by_kind_nonoverlap.get(kind, []),
                key=lambda row: (
                    str(row["event_date"]),
                    str(row["ticker"]),
                    str(row.get("massive_action_id") or ""),
                ),
            )
            picked = _evenly_spaced_sample(overlap, requested)
            selected.extend(picked)
            examples = _evenly_spaced_sample(
                nonoverlap, MOMSEASON_AUDIT_COVERAGE_EXAMPLES_PER_KIND
            )
            for row in examples:
                item = dict(row)
                item["coverage_status"] = "NO_EXACT_ALPACA_ACTION_OVERLAP"
                coverage_examples.append(item)
            summary[kind] = {
                "massive_candidate_rows": len(overlap) + len(nonoverlap),
                "exact_alpaca_action_overlap_rows": len(overlap),
                "no_exact_alpaca_action_overlap_rows": len(nonoverlap),
                "price_audit_selected_from_overlap": len(picked),
                "price_audit_requested": requested,
            }

        selected.sort(
            key=lambda row: (
                str(row["event_date"]),
                str(row["ticker"]),
                str(row["kind"]),
            )
        )
        for index_number, row in enumerate(selected, start=1):
            row["case_id"] = (
                f"v2_case_{index_number:03d}_{row['kind']}_{row['ticker']}_{row['event_date']}"
            )
        coverage_examples.sort(
            key=lambda row: (
                str(row["kind"]),
                str(row["event_date"]),
                str(row["ticker"]),
            )
        )
        return selected, summary, coverage_examples

    def _acquire_case_prices_v2(self, case: dict[str, object]) -> dict[str, object]:
        event_date = date.fromisoformat(str(case["event_date"]))
        bracket = self._bracketing_sessions(event_date)
        result = dict(case)
        if bracket is None:
            result["price_status"] = "NO_SAFE_SESSION_BRACKET"
            return result

        start, end = bracket
        if end > MOMSEASON_TOTAL_RETURN_BAR_AUDIT_END:
            raise RuntimeError("LIT-01 v2 source audit attempted to cross pre-target bar barrier")
        result["price_start_session"] = start.isoformat()
        result["price_end_session"] = end.isoformat()
        result["alpaca_symbol_asof"] = event_date.isoformat()

        closes_by_adjustment: dict[str, dict[date, float]] = {}
        page_hashes: dict[str, list[str]] = {"raw": [], "all": []}
        response_symbols: dict[str, set[str]] = {"raw": set(), "all": set()}
        for adjustment in ("raw", "all"):
            closes: dict[date, float] = {}
            for page in self.alpaca.historical_bar_pages(
                symbols=[str(case["ticker"])],
                start=start.isoformat(),
                end=end.isoformat(),
                adjustment=adjustment,
                asof=event_date.isoformat(),
                timeframe="1Day",
            ):
                raw_record = self.raw_store.persist(
                    page,
                    category=f"v2_bars_{adjustment}",
                    partition=str(case["case_id"]),
                )
                page_hashes[adjustment].append(raw_record.sha256)
                if isinstance(page.payload, dict) and isinstance(page.payload.get("bars"), dict):
                    response_symbols[adjustment].update(
                        str(value) for value in page.payload["bars"].keys()
                    )
                page_closes = extract_alpaca_bar_closes(
                    page.payload, str(case["ticker"])
                )
                for session, close in page_closes.items():
                    if session in closes and not math.isclose(
                        closes[session], close, rel_tol=0.0, abs_tol=0.0
                    ):
                        raise ValueError(
                            f"conflicting Alpaca v2 {adjustment} close for "
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
                "raw_response_symbols": sorted(response_symbols["raw"]),
                "adjusted_all_response_symbols": sorted(response_symbols["all"]),
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
        start_scale = adjusted_start / raw_start
        end_scale = adjusted_end / raw_end
        observed_scale_change = end_scale / start_scale
        massive_expected = expected_scale_change_from_massive(result, raw_start)
        alpaca_expected = expected_scale_change_from_alpaca(result, raw_start)
        result.update(
            {
                "price_status": "COMPLETE",
                "raw_return": raw_end / raw_start - 1.0,
                "adjusted_total_return": adjusted_end / adjusted_start - 1.0,
                "start_adjustment_scale": start_scale,
                "end_adjustment_scale": end_scale,
                "observed_scale_change": observed_scale_change,
                "massive_expected_event_scale_change": massive_expected,
                "alpaca_expected_event_scale_change": alpaca_expected,
                "massive_scale_change_relative_error": _relative_error(
                    observed_scale_change, massive_expected
                ),
                "alpaca_scale_change_relative_error": _relative_error(
                    observed_scale_change, alpaca_expected
                ),
            }
        )
        return result

    def acquire_price_audit_cases_v2(self, *, force: bool = False) -> dict[str, object]:
        target = self.price_cases_v2_path()
        coverage_target = self.coverage_examples_v2_path()
        if target.is_file() and coverage_target.is_file() and not force:
            rows = read_gzip_jsonl(target)
            coverage = read_gzip_jsonl(coverage_target)
            return {
                "path": str(target),
                "coverage_path": str(coverage_target),
                "skipped": True,
                "row_count": len(rows),
                "coverage_example_count": len(coverage),
            }

        selected, _selection_summary, coverage_examples = self._selection()
        results: list[dict[str, object]] = []
        for index_number, case in enumerate(selected, start=1):
            item = self._acquire_case_prices_v2(case)
            results.append(item)
            print(
                "LIT-01 Alpaca adjusted-price audit v2: "
                f"{index_number}/{len(selected)} case={case['case_id']} "
                f"price_status={item.get('price_status')} "
                f"asof={item.get('alpaca_symbol_asof')}"
            )
        count = write_gzip_jsonl(target, results)
        coverage_count = write_gzip_jsonl(coverage_target, coverage_examples)
        return {
            "path": str(target),
            "coverage_path": str(coverage_target),
            "skipped": False,
            "row_count": count,
            "coverage_example_count": coverage_count,
        }

    @staticmethod
    def _metric_summary(values: Iterable[float | None]) -> dict[str, float | int | None]:
        clean = sorted(
            float(value)
            for value in values
            if value is not None and math.isfinite(float(value))
        )
        if not clean:
            return {"count": 0, "min": None, "median": None, "max": None}
        middle = len(clean) // 2
        median = (
            clean[middle]
            if len(clean) % 2
            else (clean[middle - 1] + clean[middle]) / 2.0
        )
        return {
            "count": len(clean),
            "min": clean[0],
            "median": median,
            "max": clean[-1],
        }

    @staticmethod
    def _worst_cases(
        rows: Iterable[dict[str, object]], field: str, *, limit: int = 5
    ) -> list[dict[str, object]]:
        values: list[tuple[float, dict[str, object]]] = []
        for row in rows:
            value = _finite_float(row.get(field))
            if value is not None:
                values.append((value, row))
        values.sort(key=lambda item: (-item[0], str(item[1].get("case_id") or "")))
        return [
            {
                "case_id": row.get("case_id"),
                "kind": row.get("kind"),
                "ticker": row.get("ticker"),
                "event_date": row.get("event_date"),
                field: value,
            }
            for value, row in values[:limit]
        ]

    def run_v2(
        self,
        *,
        acquire: bool = False,
        force_acquire: bool = False,
    ) -> dict[str, object]:
        if not self._massive_prerequisites_available():
            status = "TOTAL_RETURN_SOURCE_V2_MASSIVE_PREREQUISITE_REQUIRED"
            selection_summary: dict[str, object] = {}
            acquisition = None
            cases: list[dict[str, object]] = []
        elif not self.alpaca_actions_path().is_file():
            status = "TOTAL_RETURN_SOURCE_V2_ALPACA_ACTION_CACHE_REQUIRED"
            selection_summary = {}
            acquisition = None
            cases = []
        else:
            _selected, selection_summary, coverage_examples = self._selection()
            if not self.coverage_examples_v2_path().is_file():
                write_gzip_jsonl(self.coverage_examples_v2_path(), coverage_examples)
            acquisition = None
            if acquire:
                acquisition = self.acquire_price_audit_cases_v2(force=force_acquire)
            cases = (
                read_gzip_jsonl(self.price_cases_v2_path())
                if self.price_cases_v2_path().is_file()
                else []
            )
            if not cases:
                status = "TOTAL_RETURN_SOURCE_V2_PRICE_ACQUISITION_REQUIRED"
            else:
                missing_complete = sum(
                    row.get("kind") == "dividend_missing_factor"
                    and row.get("price_status") == "COMPLETE"
                    for row in cases
                )
                if missing_complete == 0:
                    status = "TOTAL_RETURN_SOURCE_V2_MISSING_FACTOR_EVIDENCE_INSUFFICIENT"
                else:
                    status = "TOTAL_RETURN_SOURCE_V2_AUDIT_READY_FOR_REVIEW"

        complete = [row for row in cases if row.get("price_status") == "COMPLETE"]
        by_kind: dict[str, dict[str, int]] = {}
        for kind in ("dividend_missing_factor", "dividend_with_factor", "split"):
            kind_rows = [row for row in cases if row.get("kind") == kind]
            by_kind[kind] = {
                "selected_from_exact_action_overlap": len(kind_rows),
                "complete_price_cases": sum(
                    row.get("price_status") == "COMPLETE" for row in kind_rows
                ),
            }

        report = {
            "status": status,
            "audit_version": MOMSEASON_TOTAL_RETURN_SOURCE_AUDIT_V2_VERSION,
            "safe_bar_audit_end": MOMSEASON_TOTAL_RETURN_BAR_AUDIT_END.isoformat(),
            "first_lit01_target_month": LITERATURE_MOMSEASON_FORMATION_START.isoformat(),
            "selection_rule": (
                "Exact ticker+event-date+action-type Massive/Alpaca overlap is selected "
                "before adjusted prices are inspected; non-overlaps are coverage evidence."
            ),
            "alpaca_symbol_mapping_rule": (
                "Historical bar requests use each source event date as Alpaca asof."
            ),
            "massive_dividend_amount_rule": (
                "Use Massive original cash_amount with event-era raw prices; "
                "split_adjusted_cash_amount remains diagnostic only."
            ),
            "selection_summary": selection_summary,
            "case_counts": by_kind,
            "selected_case_count": len(cases),
            "complete_price_case_count": len(complete),
            "provider_value_relative_error": self._metric_summary(
                _finite_float(row.get("value_relative_error")) for row in cases
            ),
            "massive_scale_change_relative_error": self._metric_summary(
                _finite_float(row.get("massive_scale_change_relative_error"))
                for row in complete
            ),
            "alpaca_scale_change_relative_error": self._metric_summary(
                _finite_float(row.get("alpaca_scale_change_relative_error"))
                for row in complete
            ),
            "worst_provider_value_cases": self._worst_cases(
                cases, "value_relative_error"
            ),
            "worst_massive_scale_cases": self._worst_cases(
                complete, "massive_scale_change_relative_error"
            ),
            "acquisition": acquisition,
            "existing_canonical_market_data_mutated": False,
            "alpaca_global_adjustment_config_mutated": False,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_writes_performed": 0,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
            "note": (
                "V2 is still source-only. It preserves v1, separates provider-domain "
                "coverage from adjustment semantics, and independently tests whether "
                "Massive original action values explain Alpaca adjustment=all scaling."
            ),
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_v2_path(), canonical_json(report) + "\n")
        report["report_path"] = str(self.report_v2_path())
        report["coverage_examples_path"] = str(self.coverage_examples_v2_path())
        return report


assert MOMSEASON_TOTAL_RETURN_BAR_AUDIT_END < LITERATURE_MOMSEASON_FORMATION_START
assert ALPACA_RESEARCH_NAMESPACE == "literature_momseason_total_return"
