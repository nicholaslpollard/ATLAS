from __future__ import annotations

import json
from datetime import UTC, datetime

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .historical_backfill_long_history_preflight import (
    GATE11_LONG_HISTORY_ORIGIN_DATE,
    GATE11_LONG_HISTORY_PREFLIGHT_CONTRACT_VERSION,
    GATE11_PRESEAM_END_DATE,
    HistoricalBackfillLongHistoryMLPreflight,
    _stable_hash,
)


GATE11_LONG_HISTORY_FINGERPRINT_SCOPE = "CONTENT_ONLY_NO_ABSOLUTE_PATHS"


def _without_paths(payload: dict[str, object]) -> dict[str, object]:
    """Drop display-only absolute paths while retaining their content hashes."""

    result: dict[str, object] = {}
    for key, value in payload.items():
        if key.endswith("_path") or key == "dataset_glob":
            continue
        result[key] = value
    return result


class HistoricalBackfillLongHistoryMLPreflightRuntime(
    HistoricalBackfillLongHistoryMLPreflight
):
    """Runtime wrapper for machine-independent, fail-closed Gate 11-A evidence."""

    def _preseam_evidence(self, end_date):  # type: ignore[override]
        evidence = super()._preseam_evidence(end_date)

        # A left join preserves canonical row count even when the right-side feature
        # row is absent. Prove exact one-to-one key coverage independently instead of
        # treating preserved cardinality as evidence of feature completeness.
        bar_glob = self.paths.glob_for_timeframe(Timeframe.DAY_1)
        feature_glob = self.paths.feature_glob(Timeframe.DAY_1)
        con = connect_utc(":memory:")
        try:
            row = con.execute(
                f"""
                WITH bars AS (
                    SELECT symbol, CAST(session_date AS DATE) AS session_date
                    FROM read_parquet({sql_string(bar_glob)}, hive_partitioning=true)
                    WHERE CAST(session_date AS DATE)
                        BETWEEN DATE '{GATE11_LONG_HISTORY_ORIGIN_DATE}'
                            AND DATE '{GATE11_PRESEAM_END_DATE}'
                ),
                feature_counts AS (
                    SELECT
                        symbol,
                        CAST(timestamp_utc AS DATE) AS session_date,
                        count(*) AS feature_rows
                    FROM read_parquet(
                        {sql_string(feature_glob)},
                        hive_partitioning=true,
                        union_by_name=true
                    )
                    WHERE CAST(timestamp_utc AS DATE)
                        BETWEEN DATE '{GATE11_LONG_HISTORY_ORIGIN_DATE}'
                            AND DATE '{GATE11_PRESEAM_END_DATE}'
                    GROUP BY symbol, CAST(timestamp_utc AS DATE)
                )
                SELECT
                    count(*) AS canonical_rows,
                    count(*) FILTER (WHERE coalesce(f.feature_rows, 0) = 0) AS missing_feature_rows,
                    count(*) FILTER (WHERE coalesce(f.feature_rows, 0) > 1) AS duplicate_feature_keys,
                    coalesce(sum(f.feature_rows), 0) AS matched_feature_rows
                FROM bars b
                LEFT JOIN feature_counts f
                  ON f.symbol=b.symbol
                 AND f.session_date=b.session_date
                """
            ).fetchone()
        finally:
            con.close()

        evidence["feature_key_audit_canonical_rows"] = int(row[0])
        evidence["missing_feature_rows"] = int(row[1])
        evidence["duplicate_feature_keys"] = int(row[2])
        evidence["matched_feature_rows"] = int(row[3])
        return evidence

    def run(self) -> dict[str, object]:
        report = super().run()
        accepted = dict(report["accepted_phase10_A"])  # type: ignore[arg-type]
        rebase = dict(report["B_rebase_evidence"])  # type: ignore[arg-type]
        preseam = dict(  # type: ignore[arg-type]
            report["C_preseam_feasibility_before_structural_reconciliation"]
        )
        feature_lineage = report["feature_lineage"]
        comparison = report["comparison_policy"]

        fingerprint_payload = {
            "contract_version": GATE11_LONG_HISTORY_PREFLIGHT_CONTRACT_VERSION,
            "fingerprint_scope": GATE11_LONG_HISTORY_FINGERPRINT_SCOPE,
            "as_of_date": report["as_of_date"],
            "gate9c_validation_sha256": sha256_file(self.gate9_validation_path),
            "gate10c_writer_sha256": sha256_file(self.gate10_report_path),
            "gate10c_validation_sha256": sha256_file(self.gate10_validation_path),
            "comparison_policy": comparison,
            "accepted_phase10": _without_paths(accepted),
            "feature_lineage": feature_lineage,
            "B_rebase": _without_paths(rebase),
            "C_preseam": _without_paths(preseam),
        }
        report["source_fingerprint"] = _stable_hash(fingerprint_payload)
        report["fingerprint_scope"] = GATE11_LONG_HISTORY_FINGERPRINT_SCOPE
        checks = dict(report["checks"])  # type: ignore[arg-type]
        checks["preseam_feature_join_exact"] = bool(
            int(preseam["feature_key_audit_canonical_rows"]) == int(preseam["source_rows"])
            and int(preseam["missing_feature_rows"]) == 0
            and int(preseam["duplicate_feature_keys"]) == 0
            and int(preseam["matched_feature_rows"]) == int(preseam["source_rows"])
        )
        checks["source_fingerprint_excludes_absolute_paths"] = True
        report["checks"] = checks
        report["pass"] = all(bool(value) for value in checks.values())
        report["generated_at_utc"] = datetime.now(UTC).isoformat()
        atomic_write_text(
            self.report_path,
            json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        )
        report["report_path"] = str(self.report_path.resolve())
        return report
