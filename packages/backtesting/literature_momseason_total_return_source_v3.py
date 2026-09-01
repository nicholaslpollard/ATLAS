from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Iterable

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings

from .literature_momseason_source import canonical_json, read_gzip_jsonl
from .literature_momseason_total_return_source import _finite_float
from .literature_momseason_total_return_source_v2 import (
    MOMSEASON_TOTAL_RETURN_PRICE_CASES_V2,
    MomSeasonTotalReturnSourceAuditV2,
)


MOMSEASON_TOTAL_RETURN_SOURCE_AUDIT_V3_VERSION = (
    "literature-momseason-total-return-source-audit-v3-currency-aware-cached-acceptance"
)
MOMSEASON_TOTAL_RETURN_AUDIT_REPORT_V3 = "total_return_source_audit_v3.json"
MOMSEASON_TOTAL_RETURN_CURRENCY_CASES_V3 = "currency_reconciled_cases_v3.jsonl.gz"

# Source-semantics tolerances are frozen here before any LIT-01 target return is
# opened. They are deliberately loose relative to ordinary floating-point noise but
# tight relative to economically meaningful corporate-action errors.
MOMSEASON_ALPACA_ADJUSTMENT_MAX_RELATIVE_ERROR = 0.001  # 10 bps
MOMSEASON_SPLIT_RATIO_MAX_RELATIVE_ERROR = 0.001  # 10 bps
MOMSEASON_SAME_CURRENCY_VALUE_MAX_RELATIVE_ERROR = 0.001  # 10 bps
MOMSEASON_MIN_COMPLETE_CASES_PER_KIND = 3
MOMSEASON_US_EQUITY_BAR_CURRENCY = "USD"


def _currency(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def _relative_error(observed: float | None, expected: float | None) -> float | None:
    if observed is None or expected is None or expected == 0:
        return None
    return abs(observed - expected) / abs(expected)


def _metric(values: Iterable[float | None]) -> dict[str, float | int | None]:
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


def _by_id(rows: Iterable[dict[str, object]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        key = str(row.get("id") or "")
        if not key:
            continue
        if key in result and result[key] != row:
            raise ValueError(f"duplicate conflicting corporate-action id: {key}")
        result[key] = row
    return result


def _currency_relation(massive: str | None, alpaca: str | None) -> str:
    if massive is None or alpaca is None:
        return "MISSING_CURRENCY_METADATA"
    if massive == alpaca:
        return "SAME_CURRENCY"
    return "CROSS_CURRENCY"


class MomSeasonTotalReturnSourceAuditV3(MomSeasonTotalReturnSourceAuditV2):
    """Cached currency-aware acceptance audit for the LIT-01 total-return source.

    V2 established exact action overlap and raw-vs-adjustment=all price behavior. Its
    largest dividend amount discrepancies were concentrated in foreign issuers, but V2
    did not retain the providers' currency fields in the derived case rows. Comparing a
    CAD dividend directly with a USD stock price is dimensionally invalid.

    V3 performs no provider calls. It joins the immutable v2 cases back to the retained
    Massive and Alpaca action caches, restores currency metadata, and evaluates only
    unit-compatible evidence. A PASS here means only that Alpaca adjustment=all is an
    accepted primary historical total-return source for the next source-capacity stage.
    It does not open development returns, protected returns, PAPER, LIVE, or trading
    authority.
    """

    def currency_cases_v3_path(self) -> Path:
        return self.root / MOMSEASON_TOTAL_RETURN_CURRENCY_CASES_V3

    def report_v3_path(self) -> Path:
        return self.root / MOMSEASON_TOTAL_RETURN_AUDIT_REPORT_V3

    def _reconcile_cases(self) -> list[dict[str, object]]:
        if not self.price_cases_v2_path().is_file():
            raise RuntimeError("LIT-01 v2 price cases are required before v3 reconciliation")
        if not self.alpaca_actions_path().is_file():
            raise RuntimeError("LIT-01 Alpaca action cache is required before v3 reconciliation")

        splits, dividends = self._load_massive_actions()
        massive_actions = _by_id([*splits, *dividends])
        alpaca_actions = _by_id(read_gzip_jsonl(self.alpaca_actions_path()))
        v2_cases = read_gzip_jsonl(self.price_cases_v2_path())

        rows: list[dict[str, object]] = []
        for case in v2_cases:
            item = dict(case)
            kind = str(item.get("kind") or "")
            massive_id = str(item.get("massive_action_id") or "")
            alpaca_id = str(item.get("alpaca_action_id") or "")
            massive_row = massive_actions.get(massive_id, {})
            alpaca_row = alpaca_actions.get(alpaca_id, {})

            massive_currency = _currency(massive_row.get("currency"))
            alpaca_currency = _currency(alpaca_row.get("currency"))
            item["massive_currency"] = massive_currency
            item["alpaca_currency"] = alpaca_currency

            if kind == "split":
                item["currency_relation"] = "NOT_APPLICABLE_SPLIT"
                item["provider_value_comparison_status"] = "RATIO_COMPARABLE"
                item["currency_valid_provider_value_relative_error"] = _finite_float(
                    item.get("value_relative_error")
                )
                item["currency_valid_massive_scale_relative_error"] = _finite_float(
                    item.get("massive_scale_change_relative_error")
                )
                item["currency_valid_alpaca_scale_relative_error"] = _finite_float(
                    item.get("alpaca_scale_change_relative_error")
                )
            else:
                relation = _currency_relation(massive_currency, alpaca_currency)
                item["currency_relation"] = relation
                same_currency = relation == "SAME_CURRENCY"
                item["provider_value_comparison_status"] = (
                    "DIRECTLY_COMPARABLE"
                    if same_currency
                    else "NOT_DIRECTLY_COMPARABLE_CURRENCY"
                )
                item["currency_valid_provider_value_relative_error"] = (
                    _finite_float(item.get("value_relative_error"))
                    if same_currency
                    else None
                )
                item["currency_valid_massive_scale_relative_error"] = (
                    _finite_float(item.get("massive_scale_change_relative_error"))
                    if massive_currency == MOMSEASON_US_EQUITY_BAR_CURRENCY
                    else None
                )
                item["currency_valid_alpaca_scale_relative_error"] = (
                    _finite_float(item.get("alpaca_scale_change_relative_error"))
                    if alpaca_currency == MOMSEASON_US_EQUITY_BAR_CURRENCY
                    else None
                )

            rows.append(item)

        rows.sort(key=lambda row: str(row.get("case_id") or ""))
        return rows

    @staticmethod
    def _worst(
        rows: Iterable[dict[str, object]], field: str, *, limit: int = 8
    ) -> list[dict[str, object]]:
        ranked: list[tuple[float, dict[str, object]]] = []
        for row in rows:
            value = _finite_float(row.get(field))
            if value is not None:
                ranked.append((value, row))
        ranked.sort(key=lambda item: (-item[0], str(item[1].get("case_id") or "")))
        return [
            {
                "case_id": row.get("case_id"),
                "kind": row.get("kind"),
                "ticker": row.get("ticker"),
                "event_date": row.get("event_date"),
                "massive_currency": row.get("massive_currency"),
                "alpaca_currency": row.get("alpaca_currency"),
                field: value,
            }
            for value, row in ranked[:limit]
        ]

    def run_v3(self) -> dict[str, object]:
        rows = self._reconcile_cases()
        from .literature_momseason_source import write_gzip_jsonl

        write_gzip_jsonl(self.currency_cases_v3_path(), rows)

        complete = [row for row in rows if row.get("price_status") == "COMPLETE"]
        by_kind: dict[str, dict[str, int]] = {}
        complete_gate = True
        for kind in ("dividend_missing_factor", "dividend_with_factor", "split"):
            kind_rows = [row for row in rows if row.get("kind") == kind]
            kind_complete = [row for row in kind_rows if row.get("price_status") == "COMPLETE"]
            by_kind[kind] = {
                "selected": len(kind_rows),
                "complete": len(kind_complete),
            }
            complete_gate = complete_gate and (
                len(kind_complete) >= MOMSEASON_MIN_COMPLETE_CASES_PER_KIND
            )

        relation_counts = Counter(
            str(row.get("currency_relation") or "UNKNOWN")
            for row in rows
            if str(row.get("kind") or "").startswith("dividend_")
        )

        same_currency_value = _metric(
            _finite_float(row.get("currency_valid_provider_value_relative_error"))
            for row in rows
            if row.get("currency_relation") == "SAME_CURRENCY"
        )
        massive_valid_scale = _metric(
            _finite_float(row.get("currency_valid_massive_scale_relative_error"))
            for row in complete
        )
        alpaca_valid_scale = _metric(
            _finite_float(row.get("currency_valid_alpaca_scale_relative_error"))
            for row in complete
        )
        split_scale = _metric(
            _finite_float(row.get("currency_valid_massive_scale_relative_error"))
            for row in complete
            if row.get("kind") == "split"
        )

        def metric_pass(metric: dict[str, float | int | None], threshold: float) -> bool:
            count = int(metric.get("count") or 0)
            maximum = metric.get("max")
            return count > 0 and maximum is not None and float(maximum) <= threshold

        gates = {
            "minimum_complete_cases_per_kind": complete_gate,
            "alpaca_adjustment_alignment": metric_pass(
                alpaca_valid_scale, MOMSEASON_ALPACA_ADJUSTMENT_MAX_RELATIVE_ERROR
            ),
            "split_ratio_alignment": metric_pass(
                split_scale, MOMSEASON_SPLIT_RATIO_MAX_RELATIVE_ERROR
            ),
            "same_currency_provider_value_alignment": metric_pass(
                same_currency_value, MOMSEASON_SAME_CURRENCY_VALUE_MAX_RELATIVE_ERROR
            ),
        }
        status = (
            "TOTAL_RETURN_SOURCE_SEMANTICS_PASS_ALPACA_PRIMARY"
            if all(gates.values())
            else "TOTAL_RETURN_SOURCE_SEMANTICS_REVIEW_REQUIRED"
        )

        report = {
            "status": status,
            "audit_version": MOMSEASON_TOTAL_RETURN_SOURCE_AUDIT_V3_VERSION,
            "primary_total_return_source_if_pass": "Alpaca historical daily bars adjustment=all",
            "identity_authority": "ATLAS InstrumentIdentityResolver + Massive PIT reference snapshots",
            "massive_corporate_actions_role_if_pass": (
                "independent source evidence and same-currency reconciliation; missing "
                "Massive historical_adjustment_factor is not used to compute LIT-01 returns"
            ),
            "bar_currency_assumption": MOMSEASON_US_EQUITY_BAR_CURRENCY,
            "frozen_source_tolerances": {
                "alpaca_adjustment_max_relative_error": MOMSEASON_ALPACA_ADJUSTMENT_MAX_RELATIVE_ERROR,
                "split_ratio_max_relative_error": MOMSEASON_SPLIT_RATIO_MAX_RELATIVE_ERROR,
                "same_currency_provider_value_max_relative_error": MOMSEASON_SAME_CURRENCY_VALUE_MAX_RELATIVE_ERROR,
                "minimum_complete_cases_per_kind": MOMSEASON_MIN_COMPLETE_CASES_PER_KIND,
            },
            "gates": gates,
            "selected_case_count": len(rows),
            "complete_price_case_count": len(complete),
            "case_counts": by_kind,
            "dividend_currency_relation_counts": dict(sorted(relation_counts.items())),
            "same_currency_provider_value_relative_error": same_currency_value,
            "currency_valid_massive_scale_relative_error": massive_valid_scale,
            "currency_valid_alpaca_scale_relative_error": alpaca_valid_scale,
            "split_scale_relative_error": split_scale,
            "worst_same_currency_provider_value_cases": self._worst(
                [row for row in rows if row.get("currency_relation") == "SAME_CURRENCY"],
                "currency_valid_provider_value_relative_error",
            ),
            "worst_currency_valid_alpaca_scale_cases": self._worst(
                complete, "currency_valid_alpaca_scale_relative_error"
            ),
            "cross_currency_dividend_examples": [
                {
                    "case_id": row.get("case_id"),
                    "ticker": row.get("ticker"),
                    "event_date": row.get("event_date"),
                    "massive_currency": row.get("massive_currency"),
                    "alpaca_currency": row.get("alpaca_currency"),
                    "raw_provider_value_relative_error": row.get("value_relative_error"),
                }
                for row in rows
                if row.get("currency_relation") == "CROSS_CURRENCY"
            ][:12],
            "provider_calls_performed": 0,
            "existing_canonical_market_data_mutated": False,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_v3_path(), canonical_json(report) + "\n")
        report["report_path"] = str(self.report_v3_path())
        report["currency_cases_path"] = str(self.currency_cases_v3_path())
        return report
