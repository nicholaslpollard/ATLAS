from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_seam import ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION
from packages.data.alpaca_backfill_seam_coverage import (
    ALPACA_BACKFILL_SEAM_COVERAGE_CONTRACT_VERSION,
    SEAM_RESET_POLICY,
)
from packages.data.alpaca_backfill_seam_lifecycle import (
    ALPACA_BACKFILL_SEAM_LIFECYCLE_CONTRACT_VERSION,
)
from packages.data.alpaca_backfill_validated_evidence import sha256_file, stable_source_fingerprint


ALPACA_BACKFILL_SEAM_FINAL_CONTRACT_VERSION = (
    "historical-backfill-seam-final-v1-explicit-bridge-or-reset"
)

SAFE_EXACT_LITERAL_STATUS = "SAFE_ADJACENT_ALPACA_AND_MASSIVE_EXACT_LITERAL_BRIDGE"
MASSIVE_DISCONTINUITY_STATUS = "MASSIVE_COVERAGE_DISCONTINUITY_WITH_ALPACA_CONTINUATION"
NO_CONTINUITY_STATUS = "NO_CROSS_SEAM_CONTINUITY_EVIDENCE"
NO_PRESEAM_STATUS = "NO_PRESEAM_CANDIDATE_IDENTITY"

BRIDGE_EXACT_LITERAL = "BRIDGE_EXACT_LITERAL"
RESET_AT_PROVIDER_SEAM = "RESET_AT_PROVIDER_SEAM"
TERMINATE_PRESEAM_CONTINUITY = "TERMINATE_PRESEAM_CONTINUITY"
QUARANTINE_SEAM_CONTINUITY = "QUARANTINE_SEAM_CONTINUITY"
POSTSEAM_ONLY = "POSTSEAM_ONLY"


def promotion_decision(identity_status: str) -> str:
    if identity_status == SAFE_EXACT_LITERAL_STATUS:
        return BRIDGE_EXACT_LITERAL
    if identity_status == MASSIVE_DISCONTINUITY_STATUS:
        return RESET_AT_PROVIDER_SEAM
    if identity_status == NO_CONTINUITY_STATUS:
        return TERMINATE_PRESEAM_CONTINUITY
    if identity_status.startswith("REVIEW_"):
        return QUARANTINE_SEAM_CONTINUITY
    if identity_status == NO_PRESEAM_STATUS:
        return POSTSEAM_ONLY
    raise ValueError(f"unsupported Gate 7 identity status: {identity_status}")


def continuity_allowed(decision: str) -> bool:
    return decision == BRIDGE_EXACT_LITERAL


def _sql_string(value: str | Path) -> str:
    return "'" + str(value).replace("\\", "/").replace("'", "''") + "'"


def _read_rows(path: Path, order_by: str = "symbol") -> list[dict[str, object]]:
    if not path.is_file():
        raise RuntimeError(f"Gate 7 final required artifact is missing: {path}")
    con = duckdb.connect(":memory:")
    try:
        cursor = con.execute(
            f"SELECT * FROM read_parquet({_sql_string(path)}, hive_partitioning=false) "
            f"ORDER BY {order_by}"
        )
        columns = [item[0] for item in cursor.description]
        rows = cursor.fetchall()
    finally:
        con.close()
    return [dict(zip(columns, row)) for row in rows]


def _write_parquet(path: Path, rows: list[dict[str, object]], columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=list(columns))
    temp = unique_temp_path(path)
    con = duckdb.connect(":memory:")
    try:
        con.register("artifact_df", frame)
        con.execute(
            f"COPY (SELECT * FROM artifact_df ORDER BY symbol) TO {_sql_string(temp)} "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
    finally:
        con.close()
    replace_with_retry(temp, path)


class AlpacaBackfillSeamFinalValidator:
    """Close Gate 7 with one explicit promotion decision per seam symbol.

    The final map is deliberately fail-closed. Exact-literal continuity is allowed
    only for the Gate 7-B evidence class that has Friday candidate data, Monday
    Alpaca confirmation, Monday Massive confirmation, and no identity blocker.
    Massive seam coverage discontinuities preserve pre-seam history but reset state
    at the provider boundary. Review rows are never bridged automatically.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        derived = settings.resolved_path(settings.data.paths.derived)
        seam_root = derived / "historical_backfill" / "alpaca" / "seam"
        self.v1_root = seam_root / "v1"
        self.v2_root = seam_root / "v2"
        self.v3_root = seam_root / "v3"
        self.root = seam_root / "final"

        self.gate7a_report_path = self.v1_root / "seam_probe_report.json"
        self.gate7b_report_path = self.v2_root / "seam_lifecycle_report.json"
        self.gate7c_report_path = self.v3_root / "massive_coverage_horizon_report.json"
        self.lifecycle_path = self.v2_root / "boundary_lifecycle_classification.parquet"
        self.coverage_path = self.v3_root / "massive_coverage_discontinuities.parquet"
        self.decision_path = self.root / "seam_promotion_decisions.parquet"
        self.report_path = self.root / "gate7_final_report.json"

    @staticmethod
    def _load_report(path: Path, label: str) -> dict[str, object]:
        if not path.is_file():
            raise RuntimeError(f"Gate 7 final requires {label} report: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def run(self) -> dict[str, object]:
        gate7a = self._load_report(self.gate7a_report_path, "Gate 7-A")
        gate7b = self._load_report(self.gate7b_report_path, "Gate 7-B")
        gate7c = self._load_report(self.gate7c_report_path, "Gate 7-C")

        if gate7a.get("contract_version") != ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION:
            raise RuntimeError("Gate 7 final Gate 7-A contract mismatch")
        if gate7b.get("contract_version") != ALPACA_BACKFILL_SEAM_LIFECYCLE_CONTRACT_VERSION:
            raise RuntimeError("Gate 7 final Gate 7-B contract mismatch")
        if gate7c.get("contract_version") != ALPACA_BACKFILL_SEAM_COVERAGE_CONTRACT_VERSION:
            raise RuntimeError("Gate 7 final Gate 7-C contract mismatch")
        if gate7a.get("structural_pass") is not True:
            raise RuntimeError("Gate 7 final requires Gate 7-A PASS")
        if gate7b.get("structural_pass") is not True:
            raise RuntimeError("Gate 7 final requires Gate 7-B PASS")
        if gate7c.get("structural_pass") is not True:
            raise RuntimeError("Gate 7 final requires Gate 7-C PASS")

        lifecycle_rows = _read_rows(self.lifecycle_path)
        coverage_rows = _read_rows(self.coverage_path)
        coverage_by_symbol = {str(row["symbol"]): row for row in coverage_rows}
        if len(coverage_by_symbol) != len(coverage_rows):
            raise RuntimeError("Gate 7 final Gate 7-C coverage symbols are not unique")

        decisions: list[dict[str, object]] = []
        decision_counts: Counter[str] = Counter()
        friday_decision_counts: Counter[str] = Counter()
        duplicate_symbols = 0
        seen: set[str] = set()

        for row in lifecycle_rows:
            symbol = str(row["symbol"])
            if symbol in seen:
                duplicate_symbols += 1
            seen.add(symbol)
            identity_status = str(row["identity_status"])
            decision = promotion_decision(identity_status)
            friday = bool(row.get("candidate_friday_present"))
            coverage = coverage_by_symbol.get(symbol)
            if decision == RESET_AT_PROVIDER_SEAM and coverage is None:
                raise RuntimeError(
                    f"Gate 7 final reset symbol is absent from Gate 7-C coverage evidence: {symbol}"
                )
            if decision != RESET_AT_PROVIDER_SEAM and coverage is not None:
                raise RuntimeError(
                    f"Gate 7 final Gate 7-C coverage symbol is not a reset decision: {symbol}"
                )

            decisions.append(
                {
                    "symbol": symbol,
                    "candidate_friday_present": friday,
                    "massive_monday_present": bool(row.get("massive_monday_present")),
                    "alpaca_monday_present": bool(row.get("alpaca_monday_present")),
                    "identity_status": identity_status,
                    "promotion_decision": decision,
                    "continuity_allowed": continuity_allowed(decision),
                    "continuity_reset_required": decision == RESET_AT_PROVIDER_SEAM,
                    "manual_review_required": decision == QUARANTINE_SEAM_CONTINUITY,
                    "preseam_identity_chain_id": row.get("preseam_identity_chain_id"),
                    "preseam_segment_id": row.get("preseam_segment_id"),
                    "massive_instrument_id": row.get("massive_instrument_id"),
                    "gate7c_coverage_class": coverage.get("coverage_class") if coverage else None,
                    "gate7c_first_massive_session": coverage.get("first_massive_session") if coverage else None,
                    "gate7c_reference_identity_count": coverage.get("reference_identity_count") if coverage else None,
                }
            )
            decision_counts[decision] += 1
            if friday:
                friday_decision_counts[decision] += 1

        columns = (
            "symbol",
            "candidate_friday_present",
            "massive_monday_present",
            "alpaca_monday_present",
            "identity_status",
            "promotion_decision",
            "continuity_allowed",
            "continuity_reset_required",
            "manual_review_required",
            "preseam_identity_chain_id",
            "preseam_segment_id",
            "massive_instrument_id",
            "gate7c_coverage_class",
            "gate7c_first_massive_session",
            "gate7c_reference_identity_count",
        )
        _write_parquet(self.decision_path, decisions, columns)

        reset_symbols = {row["symbol"] for row in decisions if row["promotion_decision"] == RESET_AT_PROVIDER_SEAM}
        coverage_symbols = set(coverage_by_symbol)
        safe_rows = [row for row in decisions if row["promotion_decision"] == BRIDGE_EXACT_LITERAL]
        review_rows = [row for row in decisions if row["promotion_decision"] == QUARANTINE_SEAM_CONTINUITY]
        friday_rows = [row for row in decisions if bool(row["candidate_friday_present"])]

        source_fingerprint = stable_source_fingerprint(
            {
                "contract_version": ALPACA_BACKFILL_SEAM_FINAL_CONTRACT_VERSION,
                "gate7a_source_fingerprint": gate7a["source_fingerprint"],
                "gate7b_source_fingerprint": gate7b["source_fingerprint"],
                "gate7c_source_fingerprint": gate7c["source_fingerprint"],
                "lifecycle_sha256": sha256_file(self.lifecycle_path),
                "coverage_sha256": sha256_file(self.coverage_path),
            }
        )

        report: dict[str, object] = {
            "contract_version": ALPACA_BACKFILL_SEAM_FINAL_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "canonical_data_modified": False,
            "source_fingerprint": source_fingerprint,
            "gate7a_source_fingerprint": gate7a["source_fingerprint"],
            "gate7b_source_fingerprint": gate7b["source_fingerprint"],
            "gate7c_source_fingerprint": gate7c["source_fingerprint"],
            "boundary_symbols": len(decisions),
            "candidate_friday_symbols": len(friday_rows),
            "decision_counts": dict(sorted(decision_counts.items())),
            "friday_decision_counts": dict(sorted(friday_decision_counts.items())),
            "safe_exact_literal_bridges": int(decision_counts[BRIDGE_EXACT_LITERAL]),
            "coverage_reset_symbols": int(decision_counts[RESET_AT_PROVIDER_SEAM]),
            "terminal_preseam_symbols": int(decision_counts[TERMINATE_PRESEAM_CONTINUITY]),
            "quarantined_seam_symbols": int(decision_counts[QUARANTINE_SEAM_CONTINUITY]),
            "postseam_only_symbols": int(decision_counts[POSTSEAM_ONLY]),
            "safe_cross_ticker_rename_edges": int(gate7b.get("safe_cross_seam_rename_edges", -1)),
            "provider_price_bridge_compatible": gate7b.get("provider_price_bridge_compatible") is True,
            "coverage_reset_policy": gate7c.get("promotion_policy"),
            "decision_path": str(self.decision_path),
            "report_path": str(self.report_path),
        }

        checks = {
            "gate7a_contract_and_pass": gate7a.get("contract_version") == ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION and gate7a.get("structural_pass") is True,
            "gate7b_contract_and_pass": gate7b.get("contract_version") == ALPACA_BACKFILL_SEAM_LIFECYCLE_CONTRACT_VERSION and gate7b.get("structural_pass") is True,
            "gate7c_contract_and_pass": gate7c.get("contract_version") == ALPACA_BACKFILL_SEAM_COVERAGE_CONTRACT_VERSION and gate7c.get("structural_pass") is True,
            "fingerprint_chain_exact": gate7b.get("gate7a_source_fingerprint") == gate7a.get("source_fingerprint") and gate7c.get("gate7b_source_fingerprint") == gate7b.get("source_fingerprint"),
            "boundary_symbol_accounting_exact": len(decisions) == int(gate7b.get("boundary_symbols", -1)) == int(gate7a.get("union_symbols", -2)),
            "decision_symbols_unique": duplicate_symbols == 0 and len(seen) == len(decisions),
            "decision_accounting_exact": sum(decision_counts.values()) == len(decisions),
            "friday_decision_accounting_exact": sum(friday_decision_counts.values()) == len(friday_rows),
            "safe_bridge_count_exact": int(decision_counts[BRIDGE_EXACT_LITERAL]) == int(gate7b.get("safe_exact_literal_bridges", -1)),
            "safe_bridges_have_three_way_presence": all(bool(row["candidate_friday_present"]) and bool(row["massive_monday_present"]) and bool(row["alpaca_monday_present"]) for row in safe_rows),
            "coverage_reset_count_exact": int(decision_counts[RESET_AT_PROVIDER_SEAM]) == int(gate7b.get("massive_coverage_discontinuities", -1)) == int(gate7c.get("target_discontinuity_symbols", -2)),
            "coverage_reset_population_exact": reset_symbols == coverage_symbols,
            "coverage_reset_policy_exact": gate7c.get("promotion_policy") == SEAM_RESET_POLICY and all(str(row.get("promotion_policy")) == SEAM_RESET_POLICY for row in coverage_rows),
            "review_rows_never_bridged": all(not bool(row["continuity_allowed"]) and bool(row["manual_review_required"]) for row in review_rows),
            "cross_ticker_bridges_fail_closed": int(gate7b.get("safe_cross_seam_rename_edges", -1)) == 0,
            "provider_price_bridge_compatible": gate7b.get("provider_price_bridge_compatible") is True,
            "all_parent_canonical_safety": gate7a.get("canonical_data_modified") is False and gate7b.get("canonical_data_modified") is False and gate7c.get("canonical_data_modified") is False,
            "canonical_data_untouched": report["canonical_data_modified"] is False,
        }
        report["checks"] = checks
        report["gate7_pass"] = all(checks.values())
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        return report
