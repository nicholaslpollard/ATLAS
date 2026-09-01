from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings

from .literature_momseason_source import canonical_json, write_gzip_jsonl
from .literature_momseason_total_return_source import _finite_float
from .literature_momseason_total_return_source_v3 import (
    MOMSEASON_ALPACA_ADJUSTMENT_MAX_RELATIVE_ERROR,
    MOMSEASON_MIN_COMPLETE_CASES_PER_KIND,
    MOMSEASON_SPLIT_RATIO_MAX_RELATIVE_ERROR,
    MOMSEASON_US_EQUITY_BAR_CURRENCY,
    MomSeasonTotalReturnSourceAuditV3,
)


MOMSEASON_TOTAL_RETURN_SOURCE_AUDIT_V4_VERSION = (
    "literature-momseason-total-return-source-audit-v4-usd-scale-corroborated-cached-acceptance"
)
MOMSEASON_TOTAL_RETURN_AUDIT_REPORT_V4 = "total_return_source_audit_v4.json"
MOMSEASON_TOTAL_RETURN_ACCEPTANCE_CASES_V4 = "source_acceptance_cases_v4.jsonl.gz"
MOMSEASON_MIN_MASSIVE_USD_DIVIDEND_CASES = 3
MOMSEASON_MASSIVE_USD_DIVIDEND_SCALE_MAX_RELATIVE_ERROR = 0.001


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


def _metric_pass(
    metric: dict[str, float | int | None],
    *,
    threshold: float,
    minimum_count: int = 1,
) -> bool:
    count = int(metric.get("count") or 0)
    maximum = metric.get("max")
    return (
        count >= minimum_count
        and maximum is not None
        and float(maximum) <= threshold
    )


class MomSeasonTotalReturnSourceAuditV4(MomSeasonTotalReturnSourceAuditV3):
    """Cached source acceptance after v3 exposed missing Alpaca currency metadata.

    V3 remains immutable REVIEW_REQUIRED evidence. Its only failed gate required direct
    same-currency Massive/Alpaca dividend-value comparison, but the retained historical
    Alpaca dividend records do not populate currency metadata. V4 does not infer or
    manufacture that metadata and does not weaken any numerical tolerance.

    Instead, V4 uses two dimensionally valid tests already present in the frozen v2/v3
    evidence:

    * Alpaca's own corporate-action value must explain raw-versus-adjustment=all price
      scaling for every complete event case, independent of a missing display currency;
    * Massive dividends explicitly denominated in USD must independently explain the
      same Alpaca price-scale change, while split ratios provide currency-free external
      corroboration.

    A PASS accepts Alpaca adjustment=all only as the primary historical total-return
    source for LIT-01 source materialization. It does not validate LIT-01 alpha, open a
    target/protected return, or grant PAPER/LIVE/trading authority.
    """

    def report_v4_path(self) -> Path:
        return self.root / MOMSEASON_TOTAL_RETURN_AUDIT_REPORT_V4

    def acceptance_cases_v4_path(self) -> Path:
        return self.root / MOMSEASON_TOTAL_RETURN_ACCEPTANCE_CASES_V4

    def run_v4(self) -> dict[str, object]:
        rows = self._reconcile_cases()
        write_gzip_jsonl(self.acceptance_cases_v4_path(), rows)
        complete = [row for row in rows if row.get("price_status") == "COMPLETE"]

        by_kind: dict[str, dict[str, int]] = {}
        complete_gate = True
        for kind in ("dividend_missing_factor", "dividend_with_factor", "split"):
            kind_rows = [row for row in rows if row.get("kind") == kind]
            kind_complete = [row for row in kind_rows if row.get("price_status") == "COMPLETE"]
            by_kind[kind] = {"selected": len(kind_rows), "complete": len(kind_complete)}
            complete_gate = complete_gate and (
                len(kind_complete) >= MOMSEASON_MIN_COMPLETE_CASES_PER_KIND
            )

        alpaca_internal = _metric(
            _finite_float(row.get("alpaca_scale_change_relative_error"))
            for row in complete
        )
        massive_usd_dividends = [
            row
            for row in complete
            if str(row.get("kind") or "").startswith("dividend_")
            and row.get("massive_currency") == MOMSEASON_US_EQUITY_BAR_CURRENCY
        ]
        massive_usd_scale = _metric(
            _finite_float(row.get("massive_scale_change_relative_error"))
            for row in massive_usd_dividends
        )
        split_scale = _metric(
            _finite_float(row.get("massive_scale_change_relative_error"))
            for row in complete
            if row.get("kind") == "split"
        )

        gates = {
            "minimum_complete_cases_per_kind": complete_gate,
            "alpaca_internal_adjustment_alignment": _metric_pass(
                alpaca_internal,
                threshold=MOMSEASON_ALPACA_ADJUSTMENT_MAX_RELATIVE_ERROR,
                minimum_count=len(complete),
            ),
            "massive_usd_dividend_scale_corroboration": _metric_pass(
                massive_usd_scale,
                threshold=MOMSEASON_MASSIVE_USD_DIVIDEND_SCALE_MAX_RELATIVE_ERROR,
                minimum_count=MOMSEASON_MIN_MASSIVE_USD_DIVIDEND_CASES,
            ),
            "split_ratio_alignment": _metric_pass(
                split_scale,
                threshold=MOMSEASON_SPLIT_RATIO_MAX_RELATIVE_ERROR,
                minimum_count=MOMSEASON_MIN_COMPLETE_CASES_PER_KIND,
            ),
        }
        status = (
            "TOTAL_RETURN_SOURCE_SEMANTICS_PASS_ALPACA_PRIMARY"
            if all(gates.values())
            else "TOTAL_RETURN_SOURCE_SEMANTICS_REVIEW_REQUIRED"
        )

        report = {
            "status": status,
            "audit_version": MOMSEASON_TOTAL_RETURN_SOURCE_AUDIT_V4_VERSION,
            "supersedes_v3_status": False,
            "v3_evidence_preserved": True,
            "v3_failed_gate_root_cause": (
                "Historical Alpaca dividend action records in the retained cache do not "
                "populate currency metadata, so direct same-currency provider-value "
                "comparison is unevaluable and is not inferred."
            ),
            "primary_total_return_source_if_pass": "Alpaca historical daily bars adjustment=all",
            "identity_authority": "ATLAS InstrumentIdentityResolver + Massive PIT reference snapshots",
            "massive_role_if_pass": (
                "PIT identity/reference authority plus independent USD-dividend and split "
                "source corroboration; Massive historical_adjustment_factor is not used "
                "to compute LIT-01 returns"
            ),
            "frozen_source_tolerances": {
                "alpaca_adjustment_max_relative_error": MOMSEASON_ALPACA_ADJUSTMENT_MAX_RELATIVE_ERROR,
                "massive_usd_dividend_scale_max_relative_error": MOMSEASON_MASSIVE_USD_DIVIDEND_SCALE_MAX_RELATIVE_ERROR,
                "split_ratio_max_relative_error": MOMSEASON_SPLIT_RATIO_MAX_RELATIVE_ERROR,
                "minimum_complete_cases_per_kind": MOMSEASON_MIN_COMPLETE_CASES_PER_KIND,
                "minimum_massive_usd_dividend_cases": MOMSEASON_MIN_MASSIVE_USD_DIVIDEND_CASES,
            },
            "gates": gates,
            "selected_case_count": len(rows),
            "complete_price_case_count": len(complete),
            "case_counts": by_kind,
            "alpaca_internal_scale_relative_error": alpaca_internal,
            "massive_usd_dividend_scale_relative_error": massive_usd_scale,
            "split_scale_relative_error": split_scale,
            "massive_usd_dividend_cases": [
                {
                    "case_id": row.get("case_id"),
                    "kind": row.get("kind"),
                    "ticker": row.get("ticker"),
                    "event_date": row.get("event_date"),
                    "massive_currency": row.get("massive_currency"),
                    "massive_scale_change_relative_error": row.get(
                        "massive_scale_change_relative_error"
                    ),
                }
                for row in massive_usd_dividends
            ],
            "source_acceptance_scope": (
                "Source semantics only. No alpha support, research-gate pass, protected "
                "evidence, production integration, PAPER, LIVE, or trading authority."
            ),
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
        atomic_write_text(self.report_v4_path(), canonical_json(report) + "\n")
        report["report_path"] = str(self.report_v4_path())
        report["acceptance_cases_path"] = str(self.acceptance_cases_v4_path())
        return report
