from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from packages.core.atomic_io import replace_with_retry, unique_temp_path, atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_candidate_canonical import AlpacaBackfillCandidateCanonicalBuilder
from packages.data.alpaca_backfill_seam import (
    ALPACA_BACKFILL_CANDIDATE_BOUNDARY_SESSION,
    ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION,
    ALPACA_BACKFILL_SEAM_TARGET_SESSION,
    ALPACA_BACKFILL_SEAM_REQUEST_START,
    ALPACA_BACKFILL_SEAM_REQUEST_END,
    seam_source_fingerprint,
)
from packages.data.alpaca_backfill_validated_evidence import sha256_file, stable_source_fingerprint
from packages.data.paths import MarketDataPaths


ALPACA_BACKFILL_SEAM_LIFECYCLE_CONTRACT_VERSION = (
    "historical-backfill-seam-v2-boundary-lifecycle-corporate-action-evidence"
)
PROVIDER_CLOSE_WITHIN_1BP_MIN_FRACTION = 0.99
PROVIDER_MATCHED_MIN_FRACTION = 0.90
PROVIDER_OHLC_P95_MAX_RELATIVE_DIFF = 0.0001
LARGE_BOUNDARY_MOVE_RELATIVE = 0.25


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sql_string(value: str | Path) -> str:
    return "'" + str(value).replace("\\", "/").replace("'", "''") + "'"


def classify_boundary_presence(friday: bool, massive_monday: bool, alpaca_monday: bool) -> str:
    key = (bool(friday), bool(massive_monday), bool(alpaca_monday))
    return {
        (True, True, True): "FRIDAY_MONDAY_BOTH_PROVIDERS",
        (True, True, False): "FRIDAY_MONDAY_MASSIVE_ONLY",
        (True, False, True): "FRIDAY_ALPACA_ONLY_MONDAY",
        (True, False, False): "FRIDAY_TERMINAL_OR_UNOBSERVED",
        (False, True, True): "MONDAY_NEW_BOTH_PROVIDERS",
        (False, True, False): "MONDAY_NEW_MASSIVE_ONLY",
        (False, False, True): "ALPACA_ONLY_MONDAY_OUTSIDE_BOUNDARY",
        (False, False, False): "NO_BOUNDARY_OBSERVATION",
    }[key]


def provider_bridge_compatible(report: dict[str, object]) -> bool:
    if report.get("structural_pass") is not True:
        return False
    safe = int(report.get("alpaca_safe_target_symbols", 0))
    massive = int(report.get("massive_target_symbols", 0))
    matched = int(report.get("matched_exact_symbols", 0))
    denominator = min(safe, massive)
    match_fraction = matched / denominator if denominator > 0 else 0.0
    close_fraction = float(report.get("close_within_1bp_fraction") or 0.0)
    ohlc_p95 = float(report.get("ohlc_relative_diff_p95") or 0.0)
    return (
        match_fraction >= PROVIDER_MATCHED_MIN_FRACTION
        and close_fraction >= PROVIDER_CLOSE_WITHIN_1BP_MIN_FRACTION
        and ohlc_p95 <= PROVIDER_OHLC_P95_MAX_RELATIVE_DIFF
    )


def _read_rows(path: Path, order_by: str | None = None) -> list[dict[str, object]]:
    if not path.is_file():
        raise RuntimeError(f"Gate 7-B required artifact is missing: {path}")
    query = f"SELECT * FROM read_parquet({_sql_string(path)}, hive_partitioning=false)"
    if order_by:
        query += f" ORDER BY {order_by}"
    con = duckdb.connect(":memory:")
    try:
        cursor = con.execute(query)
        columns = [item[0] for item in cursor.description]
        values = cursor.fetchall()
    finally:
        con.close()
    return [dict(zip(columns, row)) for row in values]


def _write_parquet(path: Path, rows: list[dict[str, object]], columns: tuple[str, ...], order_by: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=list(columns))
    temp = unique_temp_path(path)
    con = duckdb.connect(":memory:")
    try:
        con.register("artifact_df", frame)
        con.execute(
            f"COPY (SELECT * FROM artifact_df ORDER BY {order_by}) TO {_sql_string(temp)} "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
    finally:
        con.close()
    replace_with_retry(temp, path)


def evaluate_cross_seam_rename(
    event: dict[str, object],
    *,
    boundary_by_symbol: dict[str, dict[str, object]],
    anomaly_casefold: set[str],
    segment_by_symbol: dict[str, dict[str, object]],
) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    old_symbol = _text(event.get("source_symbol"))
    new_symbol = _text(event.get("target_symbol"))
    old_cusip = _text(event.get("source_cusip"))
    new_cusip = _text(event.get("target_cusip"))
    if str(event.get("event_type")) != "name_changes":
        reasons.append("NOT_NAME_CHANGE")
    if old_symbol is None or new_symbol is None:
        reasons.append("MISSING_SYMBOL")
        return False, tuple(sorted(set(reasons)))
    if old_symbol == new_symbol:
        reasons.append("SAME_LITERAL")
    if old_symbol.casefold() == new_symbol.casefold():
        reasons.append("CASE_ONLY_LITERAL_CHANGE")
    if old_cusip is None or new_cusip is None:
        reasons.append("MISSING_CUSIP")
    elif old_cusip != new_cusip:
        reasons.append("CUSIP_CHANGED")

    old = boundary_by_symbol.get(old_symbol)
    new = boundary_by_symbol.get(new_symbol)
    if old is None:
        reasons.append("OLD_NOT_BOUNDARY_OBSERVED")
    else:
        if not bool(old.get("candidate_friday_present")):
            reasons.append("OLD_NOT_FRIDAY_PRESENT")
        if bool(old.get("massive_monday_present")) or bool(old.get("alpaca_monday_present")):
            reasons.append("OLD_STILL_OBSERVED_MONDAY")
    if new is None:
        reasons.append("NEW_NOT_BOUNDARY_OBSERVED")
    else:
        if bool(new.get("candidate_friday_present")):
            reasons.append("NEW_ALREADY_FRIDAY_PRESENT")
        if not bool(new.get("massive_monday_present")):
            reasons.append("NEW_NOT_MASSIVE_MONDAY")
        if not bool(new.get("alpaca_monday_present")):
            reasons.append("NEW_NOT_ALPACA_MONDAY")

    if old_symbol.casefold() in anomaly_casefold or new_symbol.casefold() in anomaly_casefold:
        reasons.append("GATE7A_CASEFOLD_ANOMALY")
    old_segment = segment_by_symbol.get(old_symbol)
    if old_segment is None:
        reasons.append("OLD_IDENTITY_SEGMENT_MISSING")
    elif bool(old_segment.get("identity_ambiguous")):
        reasons.append("OLD_IDENTITY_AMBIGUOUS")
    elif _text(old_segment.get("last_candidate_session")) not in {
        ALPACA_BACKFILL_CANDIDATE_BOUNDARY_SESSION.isoformat(),
        None,
    }:
        reasons.append("OLD_CANDIDATE_BOUNDARY_NOT_FINAL")

    return len(reasons) == 0, tuple(sorted(set(reasons)))


class AlpacaBackfillSeamLifecycleAudit:
    """Gate 7-B local lifecycle reconciliation over accepted Gate 7-A evidence."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.candidate = AlpacaBackfillCandidateCanonicalBuilder(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        root = derived / "historical_backfill" / "alpaca"
        self.seam_v1_root = root / "seam" / "v1"
        self.root = root / "seam" / "v2"
        self.parent_report_path = self.seam_v1_root / "seam_probe_report.json"
        self.safe_bars_path = self.seam_v1_root / "alpaca_2021-08-16_safe_bars.parquet"
        self.anomalies_path = self.seam_v1_root / "response_symbol_anomalies.parquet"
        self.provider_comparison_path = self.seam_v1_root / "same_session_provider_comparison.parquet"
        self.boundary_status_path = self.seam_v1_root / "boundary_symbol_status.parquet"
        self.event_ledger_path = root / "identity" / "corporate_action_events.parquet"
        self.identity_segments_path = self.candidate.identity_segment_output_path
        self.classification_path = self.root / "boundary_lifecycle_classification.parquet"
        self.rename_evidence_path = self.root / "cross_seam_rename_evidence.parquet"
        self.large_moves_path = self.root / "boundary_large_moves.parquet"
        self.provider_outliers_path = self.root / "same_session_provider_price_outliers.parquet"
        self.report_path = self.root / "seam_lifecycle_report.json"
        self.candidate_boundary_path = self.paths.canonical_file(
            Timeframe.DAY_1, ALPACA_BACKFILL_CANDIDATE_BOUNDARY_SESSION
        )
        # The Gate 6 candidate is isolated; replace production-root path with candidate path.
        self.candidate_boundary_path = (
            self.candidate.bar_root
            / "year=2021"
            / "date=2021-08-13"
            / "part-000.parquet"
        )
        self.massive_boundary_path = self.paths.canonical_file(
            Timeframe.DAY_1, ALPACA_BACKFILL_SEAM_TARGET_SESSION
        )
        self.massive_reference_path = self.paths.reference_snapshot_file(ALPACA_BACKFILL_SEAM_TARGET_SESSION)

    @staticmethod
    def _symbols(path: Path) -> list[str]:
        rows = _read_rows(path)
        return sorted({_text(row.get("symbol")) for row in rows if _text(row.get("symbol")) is not None})

    def _current_parent_fingerprint(self, parent: dict[str, object]) -> str:
        if not self.candidate.report_path.is_file():
            raise RuntimeError("Gate 7-B requires Gate 6 candidate manifest")
        candidate_report = json.loads(self.candidate.report_path.read_text(encoding="utf-8"))
        candidate_symbols = self._symbols(self.candidate_boundary_path)
        massive_symbols = self._symbols(self.massive_boundary_path)
        symbols = sorted(set(candidate_symbols).union(massive_symbols))
        cfg = self.settings.alpaca.market_data
        return seam_source_fingerprint(
            candidate_fingerprint=str(candidate_report["source_fingerprint"]),
            candidate_boundary_sha256=sha256_file(self.candidate_boundary_path),
            massive_boundary_sha256=sha256_file(self.massive_boundary_path),
            symbols=symbols,
            symbol_batch_size=int(cfg.symbol_batch_size),
            feed=str(cfg.feed),
            adjustment=str(cfg.adjustment),
            asof=str(cfg.asof),
            timeframe=str(cfg.timeframe),
        )

    def _load_parent(self) -> dict[str, object]:
        if not self.parent_report_path.is_file():
            raise RuntimeError("Gate 7-B requires Gate 7-A report")
        parent = json.loads(self.parent_report_path.read_text(encoding="utf-8"))
        if parent.get("contract_version") != ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION:
            raise RuntimeError("Gate 7-B Gate 7-A contract mismatch")
        if parent.get("structural_pass") is not True:
            raise RuntimeError("Gate 7-B requires Gate 7-A structural PASS")
        if parent.get("canonical_data_modified") is not False:
            raise RuntimeError("Gate 7-A did not preserve canonical safety")
        for path in (
            self.safe_bars_path,
            self.anomalies_path,
            self.provider_comparison_path,
            self.boundary_status_path,
            self.event_ledger_path,
            self.identity_segments_path,
        ):
            if not path.is_file():
                raise RuntimeError(f"Gate 7-B required evidence is missing: {path}")
        current = self._current_parent_fingerprint(parent)
        if current != parent.get("source_fingerprint"):
            raise RuntimeError("Gate 7-A seam source fingerprint is stale")
        return parent

    def _source_fingerprint(self, parent: dict[str, object]) -> str:
        reference_sha = sha256_file(self.massive_reference_path) if self.massive_reference_path.is_file() else None
        return stable_source_fingerprint(
            {
                "contract_version": ALPACA_BACKFILL_SEAM_LIFECYCLE_CONTRACT_VERSION,
                "gate7a_source_fingerprint": parent["source_fingerprint"],
                "safe_bars_sha256": sha256_file(self.safe_bars_path),
                "anomalies_sha256": sha256_file(self.anomalies_path),
                "provider_comparison_sha256": sha256_file(self.provider_comparison_path),
                "boundary_status_sha256": sha256_file(self.boundary_status_path),
                "corporate_action_events_sha256": sha256_file(self.event_ledger_path),
                "identity_segments_sha256": sha256_file(self.identity_segments_path),
                "massive_reference_sha256": reference_sha,
            }
        )

    def run(self) -> dict[str, object]:
        parent = self._load_parent()
        source_fingerprint = self._source_fingerprint(parent)

        safe_symbols = {str(row["symbol"]) for row in _read_rows(self.safe_bars_path) if _text(row.get("symbol"))}
        anomaly_rows = _read_rows(self.anomalies_path)
        anomaly_casefold: set[str] = set()
        for row in anomaly_rows:
            for field in ("requested_symbol", "returned_symbol"):
                symbol = _text(row.get(field))
                if symbol is not None:
                    anomaly_casefold.add(symbol.casefold())

        segments = _read_rows(self.identity_segments_path, "symbol")
        segment_by_symbol = {str(row["symbol"]): row for row in segments if _text(row.get("symbol"))}
        boundary_rows = _read_rows(self.boundary_status_path, "symbol")

        reference_by_symbol: dict[str, dict[str, object]] = {}
        if self.massive_reference_path.is_file():
            con = duckdb.connect(":memory:")
            try:
                cursor = con.execute(
                    f"SELECT * FROM read_parquet({_sql_string(self.massive_reference_path)}, hive_partitioning=false)"
                )
                columns = [item[0] for item in cursor.description]
                for values in cursor.fetchall():
                    row = dict(zip(columns, values))
                    ticker = _text(row.get("ticker"))
                    if ticker is not None and ticker not in reference_by_symbol:
                        reference_by_symbol[ticker] = row
            finally:
                con.close()

        classification_rows: list[dict[str, object]] = []
        boundary_by_symbol: dict[str, dict[str, object]] = {}
        presence_counts: Counter[str] = Counter()
        identity_counts: Counter[str] = Counter()

        for row in boundary_rows:
            symbol = str(row["symbol"])
            friday = bool(row.get("candidate_friday_present"))
            massive = bool(row.get("massive_monday_present"))
            alpaca = symbol in safe_symbols
            anomaly = symbol.casefold() in anomaly_casefold
            segment = segment_by_symbol.get(symbol)
            ambiguous = bool(segment and segment.get("identity_ambiguous"))
            asset_reference = bool(segment and segment.get("asset_id_multiplicity_reference"))
            presence_class = classify_boundary_presence(friday, massive, alpaca)

            if anomaly:
                identity_status = "REVIEW_CASEFOLD_ANOMALY"
            elif ambiguous:
                identity_status = "REVIEW_PRESEAM_IDENTITY_AMBIGUOUS"
            elif friday and massive and alpaca:
                identity_status = "SAFE_ADJACENT_ALPACA_AND_MASSIVE_EXACT_LITERAL_BRIDGE"
            elif friday and alpaca and not massive:
                identity_status = "MASSIVE_COVERAGE_DISCONTINUITY_WITH_ALPACA_CONTINUATION"
            elif friday and massive and not alpaca:
                identity_status = "REVIEW_MASSIVE_ONLY_CROSS_SEAM_CONTINUITY"
            elif friday:
                identity_status = "NO_CROSS_SEAM_CONTINUITY_EVIDENCE"
            else:
                identity_status = "NO_PRESEAM_CANDIDATE_IDENTITY"

            ref = reference_by_symbol.get(symbol, {})
            revised = {
                **row,
                "alpaca_monday_present": alpaca,
                "gate7a_identity_anomaly": anomaly,
                "presence_class": presence_class,
                "identity_status": identity_status,
                "preseam_identity_chain_id": segment.get("identity_chain_id") if segment else None,
                "preseam_segment_id": segment.get("segment_id") if segment else None,
                "preseam_identity_ambiguous": ambiguous,
                "preseam_asset_id_multiplicity_reference": asset_reference,
                "massive_instrument_id": ref.get("instrument_id"),
                "massive_identity_key": ref.get("identity_key"),
                "massive_identity_quality": ref.get("identity_quality"),
            }
            classification_rows.append(revised)
            boundary_by_symbol[symbol] = revised
            presence_counts[presence_class] += 1
            identity_counts[identity_status] += 1

        classification_columns = tuple(classification_rows[0].keys())
        _write_parquet(self.classification_path, classification_rows, classification_columns, "symbol")

        events = _read_rows(self.event_ledger_path, "event_key")
        rename_candidates: list[dict[str, object]] = []
        for event in events:
            if str(event.get("event_type")) != "name_changes":
                continue
            source = _text(event.get("source_symbol"))
            target = _text(event.get("target_symbol"))
            if source not in boundary_by_symbol or target not in boundary_by_symbol:
                continue
            safe, reasons = evaluate_cross_seam_rename(
                event,
                boundary_by_symbol=boundary_by_symbol,
                anomaly_casefold=anomaly_casefold,
                segment_by_symbol=segment_by_symbol,
            )
            rename_candidates.append(
                {
                    "event_key": event.get("event_key"),
                    "provider_event_id": event.get("provider_event_id"),
                    "event_date": event.get("event_date"),
                    "process_date": event.get("process_date"),
                    "effective_date": event.get("effective_date"),
                    "old_symbol": source,
                    "new_symbol": target,
                    "cusip": event.get("source_cusip") if event.get("source_cusip") == event.get("target_cusip") else None,
                    "preseam_identity_chain_id": segment_by_symbol.get(source or "", {}).get("identity_chain_id"),
                    "preseam_segment_id": segment_by_symbol.get(source or "", {}).get("segment_id"),
                    "massive_target_instrument_id": reference_by_symbol.get(target or "", {}).get("instrument_id"),
                    "safe_to_bridge_initial": safe,
                    "review_reasons": ",".join(reasons),
                }
            )

        # Fail closed on branching or conflicting-CUSIP seam rename evidence.
        source_targets: dict[str, set[str]] = defaultdict(set)
        target_sources: dict[str, set[str]] = defaultdict(set)
        node_cusips: dict[str, set[str]] = defaultdict(set)
        for row in rename_candidates:
            if not bool(row["safe_to_bridge_initial"]):
                continue
            old = str(row["old_symbol"])
            new = str(row["new_symbol"])
            source_targets[old].add(new)
            target_sources[new].add(old)
            cusip = _text(row.get("cusip"))
            if cusip is not None:
                node_cusips[old].add(cusip)
                node_cusips[new].add(cusip)

        safe_rename_edges = 0
        rename_review_rows = 0
        for row in rename_candidates:
            reasons = [item for item in str(row.get("review_reasons") or "").split(",") if item]
            if bool(row["safe_to_bridge_initial"]):
                old = str(row["old_symbol"])
                new = str(row["new_symbol"])
                if len(source_targets[old]) > 1:
                    reasons.append("SEAM_SOURCE_BRANCHING")
                if len(target_sources[new]) > 1:
                    reasons.append("SEAM_TARGET_BRANCHING")
                if len(node_cusips[old]) > 1 or len(node_cusips[new]) > 1:
                    reasons.append("SEAM_NODE_MULTIPLE_CUSIPS")
            final_safe = bool(row["safe_to_bridge_initial"]) and not reasons
            row["safe_to_bridge"] = final_safe
            row["review_reasons"] = ",".join(sorted(set(reasons)))
            row["continuity_basis"] = (
                "MATCHING_CUSIP_CLEAN_ADJACENT_SEAM_NAME_CHANGE" if final_safe else "REVIEW_REQUIRED"
            )
            safe_rename_edges += int(final_safe)
            rename_review_rows += int(not final_safe)

        rename_columns = (
            "event_key", "provider_event_id", "event_date", "process_date", "effective_date",
            "old_symbol", "new_symbol", "cusip", "preseam_identity_chain_id", "preseam_segment_id",
            "massive_target_instrument_id", "safe_to_bridge_initial", "safe_to_bridge",
            "review_reasons", "continuity_basis",
        )
        _write_parquet(self.rename_evidence_path, rename_candidates, rename_columns, "old_symbol, new_symbol, event_key")

        large_moves = [
            row for row in classification_rows
            if bool(row.get("candidate_friday_present"))
            and bool(row.get("massive_monday_present"))
            and (
                float(row.get("friday_close_to_monday_open_relative_move") or 0.0) >= LARGE_BOUNDARY_MOVE_RELATIVE
                or float(row.get("friday_close_to_monday_close_relative_move") or 0.0) >= LARGE_BOUNDARY_MOVE_RELATIVE
            )
        ]
        if large_moves:
            large_columns = tuple(large_moves[0].keys())
        else:
            large_columns = classification_columns
        _write_parquet(self.large_moves_path, large_moves, large_columns, "symbol")

        comparison_rows = _read_rows(self.provider_comparison_path, "symbol")
        provider_outliers = [
            row for row in comparison_rows
            if float(row.get("max_ohlc_relative_diff") or 0.0) > PROVIDER_OHLC_P95_MAX_RELATIVE_DIFF
        ]
        provider_columns = tuple(comparison_rows[0].keys()) if comparison_rows else ("symbol",)
        _write_parquet(self.provider_outliers_path, provider_outliers, provider_columns, "symbol")

        union_symbols = int(parent.get("union_symbols", -1))
        exact_safe_bridges = int(identity_counts["SAFE_ADJACENT_ALPACA_AND_MASSIVE_EXACT_LITERAL_BRIDGE"])
        coverage_discontinuities = int(identity_counts["MASSIVE_COVERAGE_DISCONTINUITY_WITH_ALPACA_CONTINUATION"])
        review_identity_rows = sum(count for status, count in identity_counts.items() if status.startswith("REVIEW_"))

        report = {
            "contract_version": ALPACA_BACKFILL_SEAM_LIFECYCLE_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "canonical_data_modified": False,
            "source_fingerprint": source_fingerprint,
            "gate7a_source_fingerprint": parent["source_fingerprint"],
            "candidate_boundary_session": ALPACA_BACKFILL_CANDIDATE_BOUNDARY_SESSION.isoformat(),
            "massive_boundary_session": ALPACA_BACKFILL_SEAM_TARGET_SESSION.isoformat(),
            "provider_price_bridge_compatible": provider_bridge_compatible(parent),
            "provider_close_within_1bp_min_fraction": PROVIDER_CLOSE_WITHIN_1BP_MIN_FRACTION,
            "provider_matched_min_fraction": PROVIDER_MATCHED_MIN_FRACTION,
            "provider_ohlc_p95_max_relative_diff": PROVIDER_OHLC_P95_MAX_RELATIVE_DIFF,
            "boundary_symbols": len(classification_rows),
            "expected_boundary_symbols": union_symbols,
            "presence_class_counts": dict(sorted(presence_counts.items())),
            "identity_status_counts": dict(sorted(identity_counts.items())),
            "safe_exact_literal_bridges": exact_safe_bridges,
            "massive_coverage_discontinuities": coverage_discontinuities,
            "identity_review_rows": int(review_identity_rows),
            "corporate_action_events_scanned": len(events),
            "cross_seam_name_change_evidence_rows": len(rename_candidates),
            "safe_cross_seam_rename_edges": safe_rename_edges,
            "cross_seam_rename_review_rows": rename_review_rows,
            "large_boundary_move_rows": len(large_moves),
            "same_session_provider_price_outlier_rows": len(provider_outliers),
            "massive_reference_snapshot_present": self.massive_reference_path.is_file(),
            "massive_reference_symbols_resolved": sum(
                1 for row in classification_rows if _text(row.get("massive_instrument_id")) is not None
            ),
            "classification_path": str(self.classification_path),
            "rename_evidence_path": str(self.rename_evidence_path),
            "large_moves_path": str(self.large_moves_path),
            "provider_outliers_path": str(self.provider_outliers_path),
            "report_path": str(self.report_path),
        }
        checks = {
            "gate7a_contract": parent.get("contract_version") == ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION,
            "gate7a_structural_pass": parent.get("structural_pass") is True,
            "gate7a_source_fingerprint_current": parent.get("source_fingerprint") == self._current_parent_fingerprint(parent),
            "provider_price_bridge_compatible": report["provider_price_bridge_compatible"] is True,
            "boundary_symbol_accounting_exact": report["boundary_symbols"] == report["expected_boundary_symbols"],
            "presence_class_accounting_exact": sum(presence_counts.values()) == report["boundary_symbols"],
            "identity_status_accounting_exact": sum(identity_counts.values()) == report["boundary_symbols"],
            "safe_rename_edges_nonbranching": all(len(values) <= 1 for values in source_targets.values()) and all(len(values) <= 1 for values in target_sources.values()),
            "canonical_data_untouched": report["canonical_data_modified"] is False,
        }
        report["structural_checks"] = checks
        report["structural_pass"] = all(checks.values())
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        return report
