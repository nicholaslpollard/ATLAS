from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_policy import ALPACA_BACKFILL_END, ALPACA_BACKFILL_START
from packages.data.alpaca_backfill_quality import ALPACA_BACKFILL_QUALITY_BASELINE_CONTRACT_VERSION
from packages.data.alpaca_backfill_session_quality import (
    ALPACA_BACKFILL_SESSION_QUALITY_CONTRACT_VERSION,
)
from packages.data.alpaca_backfill_validated_evidence import (
    ALPACA_BACKFILL_VALIDATED_EVIDENCE_CONTRACT_VERSION,
    AlpacaBackfillValidatedEvidenceBuilder,
    AlpacaBackfillValidatedEvidenceValidator,
)


ALPACA_BACKFILL_QUALITY_OUTLIER_CONTRACT_VERSION = (
    "historical-backfill-quality-outliers-v1-raw-return-diagnostics"
)
RAW_OUTLIER_POLICY = "DIAGNOSTIC_RAW_UNADJUSTED_NOT_AUTOMATIC_EXCLUSION"


def simple_return(previous_close: float, close: float) -> float:
    if previous_close <= 0.0 or close <= 0.0:
        raise ValueError("raw return requires positive closes")
    return (close / previous_close) - 1.0


def absolute_return_bucket(value: float) -> str:
    absolute = abs(value)
    if absolute >= 5.0:
        return "GE_500_PCT"
    if absolute >= 2.5:
        return "GE_250_PCT"
    if absolute >= 1.0:
        return "GE_100_PCT"
    if absolute >= 0.5:
        return "GE_50_PCT"
    if absolute >= 0.25:
        return "GE_25_PCT"
    return "LT_25_PCT"


class AlpacaBackfillQualityOutlierBuilder:
    """Gate 5-C raw-return diagnostics over validated Parquet evidence."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        root = settings.resolved_path(settings.data.paths.derived) / "historical_backfill" / "alpaca"
        self.quality_root = root / "quality"
        self.cache_builder = AlpacaBackfillValidatedEvidenceBuilder(settings)
        self.cache_validator = AlpacaBackfillValidatedEvidenceValidator(settings)
        self.report_path = self.quality_root / "return_outlier_report.json"
        self.top_outliers_path = self.quality_root / "top_raw_return_outliers.parquet"
        self.market_clusters_path = self.quality_root / "market_raw_return_clusters.parquet"

    def run(self) -> dict[str, object]:
        cache_validation = self.cache_validator.run()
        if cache_validation.get("pass") is not True:
            raise RuntimeError("Gate 5-C requires a passing validated-evidence cache")
        cache_report = json.loads(
            self.cache_builder.report_path.read_text(encoding="utf-8")
        )
        if cache_report.get("contract_version") != ALPACA_BACKFILL_VALIDATED_EVIDENCE_CONTRACT_VERSION:
            raise RuntimeError("Gate 5-C validated-evidence contract mismatch")

        paths = [
            self.cache_builder._partition_paths(year)[0]
            for year in range(ALPACA_BACKFILL_START.year, ALPACA_BACKFILL_END.year + 1)
        ]
        if not all(path.is_file() for path in paths):
            raise RuntimeError("Gate 5-C validated-evidence partition missing")

        self.quality_root.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect(":memory:")
        try:
            con.read_parquet([str(path) for path in paths]).create_view("evidence")
            con.execute(
                "CREATE TEMP VIEW trade_sequence AS "
                "SELECT provider_symbol, session_date, close, "
                "lag(session_date) OVER (PARTITION BY provider_symbol ORDER BY session_date) AS previous_session_date, "
                "lag(close) OVER (PARTITION BY provider_symbol ORDER BY session_date) AS previous_close "
                "FROM evidence WHERE bar_class='TRADE_BACKED'"
            )
            con.execute(
                "CREATE TEMP VIEW raw_returns AS "
                "SELECT provider_symbol, session_date, previous_session_date, previous_close, close, "
                "(close / previous_close) - 1.0 AS simple_return, "
                "abs((close / previous_close) - 1.0) AS absolute_return, "
                "date_diff('day', previous_session_date, session_date) AS calendar_gap_days "
                "FROM trade_sequence WHERE previous_close IS NOT NULL"
            )

            aggregate = con.execute(
                "SELECT count(*), "
                "sum(CASE WHEN absolute_return >= 0.25 THEN 1 ELSE 0 END), "
                "sum(CASE WHEN absolute_return >= 0.50 THEN 1 ELSE 0 END), "
                "sum(CASE WHEN absolute_return >= 1.00 THEN 1 ELSE 0 END), "
                "sum(CASE WHEN absolute_return >= 2.50 THEN 1 ELSE 0 END), "
                "sum(CASE WHEN absolute_return >= 5.00 THEN 1 ELSE 0 END), "
                "max(absolute_return), "
                "count(DISTINCT CASE WHEN absolute_return >= 1.00 THEN provider_symbol END), "
                "count(DISTINCT CASE WHEN absolute_return >= 1.00 THEN session_date END), "
                "sum(CASE WHEN previous_close <= 0 OR close <= 0 THEN 1 ELSE 0 END) "
                "FROM raw_returns"
            ).fetchone()
            assert aggregate is not None

            cluster = con.execute(
                "SELECT coalesce(max(extreme_100_count),0), coalesce(max(extreme_100_ratio),0.0) "
                "FROM ("
                "SELECT session_date, count(*) AS transition_count, "
                "sum(CASE WHEN absolute_return >= 1.00 THEN 1 ELSE 0 END) AS extreme_100_count, "
                "sum(CASE WHEN absolute_return >= 1.00 THEN 1 ELSE 0 END)::DOUBLE / count(*) AS extreme_100_ratio "
                "FROM raw_returns GROUP BY session_date)"
            ).fetchone()
            assert cluster is not None

            temp_outliers = unique_temp_path(self.top_outliers_path)
            con.execute(
                "COPY (SELECT provider_symbol, session_date, previous_session_date, "
                "previous_close, close, simple_return, absolute_return, calendar_gap_days "
                "FROM raw_returns ORDER BY absolute_return DESC, provider_symbol, session_date LIMIT 500) "
                "TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
                [str(temp_outliers)],
            )
            replace_with_retry(temp_outliers, self.top_outliers_path)

            temp_clusters = unique_temp_path(self.market_clusters_path)
            con.execute(
                "COPY (SELECT session_date, count(*) AS transition_count, "
                "sum(CASE WHEN absolute_return >= 0.50 THEN 1 ELSE 0 END) AS extreme_50_count, "
                "sum(CASE WHEN absolute_return >= 1.00 THEN 1 ELSE 0 END) AS extreme_100_count, "
                "sum(CASE WHEN absolute_return >= 1.00 THEN 1 ELSE 0 END)::DOUBLE / count(*) AS extreme_100_ratio, "
                "max(absolute_return) AS max_absolute_return "
                "FROM raw_returns GROUP BY session_date "
                "ORDER BY extreme_100_ratio DESC, extreme_100_count DESC, session_date LIMIT 250) "
                "TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
                [str(temp_clusters)],
            )
            replace_with_retry(temp_clusters, self.market_clusters_path)
        finally:
            con.close()

        transition_rows = int(aggregate[0])
        trade_rows = int(cache_report.get("trade_backed_rows", -1))
        observed_symbols = int(cache_report.get("observed_symbols", -1))
        report = {
            "contract_version": ALPACA_BACKFILL_QUALITY_OUTLIER_CONTRACT_VERSION,
            "validated_evidence_contract_version": ALPACA_BACKFILL_VALIDATED_EVIDENCE_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "canonical_data_modified": False,
            "raw_outlier_policy": RAW_OUTLIER_POLICY,
            "source_fingerprint": cache_report.get("source_fingerprint"),
            "trade_backed_rows": trade_rows,
            "observed_symbols": observed_symbols,
            "transition_rows": transition_rows,
            "expected_transition_rows": trade_rows - observed_symbols,
            "transition_accounting_exact": transition_rows == trade_rows - observed_symbols,
            "absolute_return_ge_25pct": int(aggregate[1] or 0),
            "absolute_return_ge_50pct": int(aggregate[2] or 0),
            "absolute_return_ge_100pct": int(aggregate[3] or 0),
            "absolute_return_ge_250pct": int(aggregate[4] or 0),
            "absolute_return_ge_500pct": int(aggregate[5] or 0),
            "max_absolute_return": float(aggregate[6] or 0.0),
            "symbols_with_ge_100pct_return": int(aggregate[7] or 0),
            "sessions_with_ge_100pct_return": int(aggregate[8] or 0),
            "nonpositive_return_input_rows": int(aggregate[9] or 0),
            "max_ge_100pct_returns_same_session": int(cluster[0] or 0),
            "max_ge_100pct_session_ratio": float(cluster[1] or 0.0),
            "top_outliers_path": str(self.top_outliers_path),
            "market_clusters_path": str(self.market_clusters_path),
            "report_path": str(self.report_path),
        }
        if not report["transition_accounting_exact"] or report["nonpositive_return_input_rows"] != 0:
            raise RuntimeError("Gate 5-C return accounting invariant failed")
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report


def gate5_acceptance_checks(
    quality: dict[str, Any],
    session: dict[str, Any],
    cache_validation: dict[str, Any],
    outlier: dict[str, Any],
) -> dict[str, bool]:
    return {
        "quality_contract": quality.get("contract_version") == ALPACA_BACKFILL_QUALITY_BASELINE_CONTRACT_VERSION,
        "quality_canonical_untouched": quality.get("canonical_data_modified") is False,
        "quality_zero_definite_invalid_rows": int(quality.get("definite_invalid_rows", -1)) == 0,
        "quality_accounting_exact": all(
            quality.get(name) is True
            for name in (
                "row_accounting_exact",
                "quarantine_accounting_exact",
                "symbol_summary_reconciliation_exact",
                "trade_backed_accounting_exact",
            )
        ),
        "session_contract": session.get("contract_version") == ALPACA_BACKFILL_SESSION_QUALITY_CONTRACT_VERSION,
        "session_canonical_untouched": session.get("canonical_data_modified") is False,
        "session_duplicates_zero": int(session.get("duplicate_session_rows", -1)) == 0,
        "session_non_exchange_zero": int(session.get("non_exchange_session_rows", -1)) == 0,
        "session_absent_lifespan_zero": int(session.get("missing_sessions_within_lifespans", -1)) == 0,
        "session_market_zero_coverage_zero": int(session.get("market_sessions_with_zero_raw_coverage", -1)) == 0,
        "session_accounting_exact": all(
            session.get(name) is True
            for name in (
                "raw_row_accounting_exact",
                "parent_classification_accounting_exact",
                "unique_session_accounting_exact",
            )
        ),
        "validated_evidence_pass": cache_validation.get("pass") is True,
        "outlier_contract": outlier.get("contract_version") == ALPACA_BACKFILL_QUALITY_OUTLIER_CONTRACT_VERSION,
        "outlier_canonical_untouched": outlier.get("canonical_data_modified") is False,
        "outlier_source_fingerprint_matches_cache": outlier.get("source_fingerprint") == cache_validation.get("source_fingerprint"),
        "outlier_transition_accounting_exact": outlier.get("transition_accounting_exact") is True,
        "outlier_positive_inputs_only": int(outlier.get("nonpositive_return_input_rows", -1)) == 0,
        "outlier_policy_diagnostic_only": outlier.get("raw_outlier_policy") == RAW_OUTLIER_POLICY,
    }


class AlpacaBackfillGate5Validator:
    """Final Gate 5 acceptance validator using accepted raw checks plus the fast evidence cache."""

    def __init__(self, settings: AtlasSettings) -> None:
        root = settings.resolved_path(settings.data.paths.derived) / "historical_backfill" / "alpaca"
        self.quality_report_path = root / "quality" / "quality_baseline_report.json"
        self.session_report_path = root / "quality" / "session_coverage_report.json"
        self.outlier_report_path = root / "quality" / "return_outlier_report.json"
        self.cache_validator = AlpacaBackfillValidatedEvidenceValidator(settings)

    def run(self) -> dict[str, object]:
        for path in (self.quality_report_path, self.session_report_path, self.outlier_report_path):
            if not path.is_file():
                raise RuntimeError(f"Gate 5 validator missing artifact: {path}")
        quality = json.loads(self.quality_report_path.read_text(encoding="utf-8"))
        session = json.loads(self.session_report_path.read_text(encoding="utf-8"))
        outlier = json.loads(self.outlier_report_path.read_text(encoding="utf-8"))
        cache_validation = self.cache_validator.run()
        checks = gate5_acceptance_checks(quality, session, cache_validation, outlier)
        required_paths = (
            Path(str(outlier.get("top_outliers_path") or "")),
            Path(str(outlier.get("market_clusters_path") or "")),
        )
        checks["outlier_artifacts_present"] = all(path.is_file() for path in required_paths)
        return {
            "checks": checks,
            "cache_validation": cache_validation,
            "outlier": outlier,
            "pass": all(checks.values()),
        }
