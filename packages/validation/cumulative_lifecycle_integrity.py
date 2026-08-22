from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

from packages.core.enums import Timeframe
from packages.data.alpaca_backfill_identity_policy import (
    ALPACA_BACKFILL_IDENTITY_POLICY_CONTRACT_VERSION,
)
from packages.data.alpaca_backfill_identity_segments import (
    ALPACA_BACKFILL_IDENTITY_SEGMENT_CONTRACT_VERSION,
)
from packages.data.alpaca_backfill_identity_segments_policy import (
    ALPACA_BACKFILL_IDENTITY_SEGMENT_POLICY_CONTRACT_VERSION,
)
from packages.data.alpaca_backfill_policy import ALPACA_BACKFILL_START
from packages.data.duckdb_connection import connect_utc
from packages.features.historical_backfill_feature_handoff import (
    GATE9_FEATURE_HANDOFF_VALIDATION_CONTRACT_VERSION,
)
from packages.features.historical_backfill_feature_state_chain import (
    GATE9_FEATURE_STATE_CHAIN_CONTRACT_VERSION,
)
from packages.features.partition_store import (
    FeaturePartitionManifest,
    feature_dependency_fingerprint,
    sha256_file,
)
from packages.ml.historical_backfill_closeout import HISTORICAL_BACKFILL_CLOSEOUT_CONTRACT_VERSION
from packages.regimes.split_origin_policy import TICKER_HISTORY_ORIGIN_DATE

from .cumulative_foundation import _json, _partition_date
from .cumulative_integrity import CumulativeFoundationIntegrityAuditor


def _state_chain_value_checks(
    manifest: FeaturePartitionManifest,
    chain_row: dict[str, object],
) -> dict[str, bool]:
    """Compare one production daily manifest with its accepted Gate 9-C state-chain row."""

    return {
        "input_state_exact": manifest.input_state_fingerprint
        == str(chain_row["input_state_fingerprint"]),
        "output_state_exact": manifest.output_state_fingerprint
        == str(chain_row["output_state_fingerprint"]),
        "source_sha_exact": manifest.source_sha256 == str(chain_row["source_sha256"]),
        "feature_sha_exact": manifest.feature_sha256
        == str(chain_row["candidate_feature_sha256"]),
        "row_count_exact": int(manifest.row_count) == int(chain_row["row_count"]),
        "symbol_count_exact": int(manifest.symbol_count) == int(chain_row["symbol_count"]),
    }


def _identity_v2_report_checks(report: dict[str, object]) -> dict[str, bool]:
    """Validate the accepted Gate 4-C v2 quarantine policy rather than the superseded v1 report."""

    return {
        "segment_policy_contract": report.get("contract_version")
        == ALPACA_BACKFILL_IDENTITY_SEGMENT_POLICY_CONTRACT_VERSION,
        "parent_segment_contract": report.get("parent_segment_contract_version")
        == ALPACA_BACKFILL_IDENTITY_SEGMENT_CONTRACT_VERSION,
        "identity_policy_contract": report.get("identity_policy_contract_version")
        == ALPACA_BACKFILL_IDENTITY_POLICY_CONTRACT_VERSION,
        "segment_canonical_unchanged": report.get("canonical_data_modified") is False,
        "edge_component_accounting": report.get("edge_component_accounting") is True,
        "chain_coverage_exact": report.get("chain_coverage_exact") is True,
        "eligible_safe_edges_consumed_exact": report.get("eligible_safe_edges_consumed_exact")
        is True,
        "quarantine_accounting_exact": report.get("quarantine_accounting_exact") is True,
    }


class CumulativeFoundationLifecycleAwareAuditor(CumulativeFoundationIntegrityAuditor):
    """Cumulative integrity audit with lifecycle-aware daily feature and Gate 4-C v2 proofs."""

    def _promotion_root(self) -> Path:
        return (
            self.derived_root
            / "historical_backfill"
            / "alpaca"
            / "feature_replay"
            / "v1"
            / "promotion"
            / "v1"
        )

    def _daily_state_chain(self, end_date: date) -> tuple[dict[date, dict[str, object]], dict[str, object]]:
        state_root = self._promotion_root() / "state_chain"
        report_path = state_root / "gate9c_state_chain_report.json"
        report = _json(report_path, "Gate 9-C per-session state-chain report")
        chain_path = Path(str(report.get("chain_path") or state_root / "feature_session_state_chain.parquet"))
        report_checks = {
            "contract_current": report.get("contract_version") == GATE9_FEATURE_STATE_CHAIN_CONTRACT_VERSION,
            "report_pass": report.get("pass") is True,
            "chain_present": chain_path.is_file(),
            "chain_hash_exact": chain_path.is_file()
            and sha256_file(chain_path) == str(report.get("chain_sha256", "")),
            "production_feature_writes_zero": int(report.get("production_feature_writes", -1)) == 0,
        }
        rows: dict[date, dict[str, object]] = {}
        if chain_path.is_file():
            con = connect_utc(":memory:")
            try:
                cursor = con.execute(
                    f"""
                    SELECT
                        session_date,
                        input_state_fingerprint,
                        output_state_fingerprint,
                        lifecycle_event_count,
                        source_sha256,
                        candidate_feature_sha256,
                        row_count,
                        symbol_count
                    FROM read_parquet('{chain_path.as_posix().replace("'", "''")}')
                    WHERE CAST(session_date AS DATE) BETWEEN DATE '{ALPACA_BACKFILL_START}' AND DATE '{end_date}'
                    ORDER BY CAST(session_date AS DATE)
                    """
                )
                columns = [str(item[0]) for item in cursor.description]
                for raw in cursor.fetchall():
                    item = dict(zip(columns, raw, strict=True))
                    key = date.fromisoformat(str(item["session_date"])[:10])
                    if key in rows:
                        raise ValueError(f"duplicate Gate 9-C state-chain session: {key}")
                    rows[key] = item
            finally:
                con.close()
        return rows, {
            "report_path": str(report_path.resolve()),
            "report_sha256": sha256_file(report_path) if report_path.is_file() else None,
            "chain_path": str(chain_path.resolve()),
            "chain_sha256": sha256_file(chain_path) if chain_path.is_file() else None,
            "checks": report_checks,
            "pass": all(report_checks.values()),
        }

    def _daily_handoff_validation(self) -> dict[str, object]:
        path = self._promotion_root() / "gate9c_handoff_validation_report.json"
        report = _json(path, "Gate 9-C production feature handoff validation")
        checks = {
            "contract_current": report.get("contract_version")
            == GATE9_FEATURE_HANDOFF_VALIDATION_CONTRACT_VERSION,
            "report_pass": report.get("pass") is True,
            "live_inventory_exact": int(report.get("live_inventory_failures", -1)) == 0,
            "production_manifests_exact": int(report.get("manifest_failures", -1)) == 0,
            "canonical_source_hashes_exact": int(report.get("source_hash_failures", -1)) == 0,
            "dependency_fingerprints_exact": int(report.get("dependency_failures", -1)) == 0,
            "current_state_exact": int(report.get("state_failures", -1)) == 0,
            "final_manifest_state_chain_exact": int(report.get("final_manifest_failures", -1)) == 0,
        }
        return {
            "path": str(path.resolve()),
            "sha256": sha256_file(path) if path.is_file() else None,
            "checks": checks,
            "pass": all(checks.values()),
        }

    def _audit_daily_feature_manifests(
        self,
        end_date: date,
        progress: Callable[[str], None] | None,
    ) -> dict[str, object]:
        origin = ALPACA_BACKFILL_START
        manifest_dir = self.manifest_root / "features" / Timeframe.DAY_1.value
        manifests = sorted(
            path
            for path in manifest_dir.glob("*/*.json")
            if origin <= date.fromisoformat(path.stem) <= end_date
        )
        forbidden = sorted(
            path for path in manifest_dir.glob("*/*.json") if date.fromisoformat(path.stem) < origin
        )
        source_dates = {
            _partition_date(path)
            for path in self._daily_files()
            if origin <= _partition_date(path) <= end_date
        }
        manifest_dates = {date.fromisoformat(path.stem) for path in manifests}
        chain_rows, chain_evidence = self._daily_state_chain(end_date)
        handoff = self._daily_handoff_validation()
        chain_dates = set(chain_rows)

        failures: list[str] = []
        failure_types: dict[str, int] = {}
        checked = 0

        def fail(trading_date: date, reason: str) -> None:
            failures.append(f"{trading_date}: {reason}")
            failure_types[reason.split(":", 1)[0]] = failure_types.get(reason.split(":", 1)[0], 0) + 1

        for path in manifests:
            trading_date = date.fromisoformat(path.stem)
            errors: list[str] = []
            try:
                record = FeaturePartitionManifest.from_dict(_json(path, "daily feature manifest"))
                record.validate_contract(Timeframe.DAY_1, trading_date)
                source = Path(record.source_path)
                feature = Path(record.feature_path)
                expected_source = self.paths.canonical_file(Timeframe.DAY_1, trading_date)
                expected_feature = self.paths.feature_file(Timeframe.DAY_1, trading_date)
                if source.resolve() != expected_source.resolve():
                    errors.append("SOURCE_PATH: canonical source path mismatch")
                if feature.resolve() != expected_feature.resolve():
                    errors.append("FEATURE_PATH: production feature path mismatch")
                if not source.is_file():
                    errors.append("SOURCE_FILE: bound canonical source missing")
                elif record.source_sha256 != sha256_file(source):
                    errors.append("SOURCE_HASH: canonical source hash mismatch")
                if not feature.is_file():
                    errors.append("FEATURE_FILE: bound feature partition missing")
                elif record.feature_sha256 != sha256_file(feature):
                    errors.append("FEATURE_HASH: feature partition hash mismatch")
                expected_dependency = feature_dependency_fingerprint(
                    source_sha256=record.source_sha256,
                    input_state_fingerprint=record.input_state_fingerprint,
                )
                if record.dependency_fingerprint != expected_dependency:
                    errors.append("DEPENDENCY: dependency fingerprint mismatch")
                chain = chain_rows.get(trading_date)
                if chain is None:
                    errors.append("STATE_CHAIN: Gate 9-C state-chain row missing")
                else:
                    for name, passed in _state_chain_value_checks(record, chain).items():
                        if not passed:
                            errors.append(f"STATE_CHAIN_{name.upper()}: mismatch")
            except Exception as exc:
                errors.append(f"MANIFEST: {type(exc).__name__}: {exc}")
            if errors:
                for error in errors:
                    fail(trading_date, error)
            else:
                checked += 1

        missing_manifest_dates = sorted(source_dates - manifest_dates)
        orphan_manifest_dates = sorted(manifest_dates - source_dates)
        missing_chain_dates = sorted(manifest_dates - chain_dates)
        orphan_chain_dates = sorted(chain_dates - manifest_dates)
        lifecycle_sessions = sorted(
            session
            for session, row in chain_rows.items()
            if int(row.get("lifecycle_event_count") or 0) > 0
        )
        adjacent_state_transitions = 0
        prior_output: str | None = None
        for session in sorted(chain_rows):
            row = chain_rows[session]
            current_input = str(row["input_state_fingerprint"])
            if prior_output is not None and current_input != prior_output:
                adjacent_state_transitions += 1
            prior_output = str(row["output_state_fingerprint"])

        coverage_exact = (
            bool(source_dates)
            and source_dates == manifest_dates == chain_dates
            and end_date in source_dates
        )
        item: dict[str, object] = {
            "origin": origin.isoformat(),
            "lineage_basis": "GATE9C_LIFECYCLE_AWARE_PER_SESSION_STATE_CHAIN",
            "manifest_count": len(manifests),
            "checked_manifest_count": checked,
            "forbidden_pre_origin_manifest_count": len(forbidden),
            "failure_count": len(failures),
            "failure_types": failure_types,
            "failure_samples": failures[:20],
            "source_partition_date_count": len(source_dates),
            "manifest_partition_date_count": len(manifest_dates),
            "state_chain_date_count": len(chain_dates),
            "source_manifest_state_chain_coverage_exact": coverage_exact,
            "missing_manifest_date_count": len(missing_manifest_dates),
            "missing_manifest_dates": [item.isoformat() for item in missing_manifest_dates[:20]],
            "orphan_manifest_date_count": len(orphan_manifest_dates),
            "orphan_manifest_dates": [item.isoformat() for item in orphan_manifest_dates[:20]],
            "missing_state_chain_date_count": len(missing_chain_dates),
            "orphan_state_chain_date_count": len(orphan_chain_dates),
            "lifecycle_event_session_count": len(lifecycle_sessions),
            "lifecycle_event_session_samples": [item.isoformat() for item in lifecycle_sessions[:20]],
            "adjacent_state_transition_count": adjacent_state_transitions,
            "state_chain_evidence": chain_evidence,
            "production_handoff_validation": handoff,
            "state_chain_continuous": not failures and bool(chain_evidence["pass"]),
        }
        item["pass"] = (
            bool(manifests)
            and not forbidden
            and not failures
            and coverage_exact
            and bool(chain_evidence["pass"])
            and bool(handoff["pass"])
        )
        if progress is not None:
            progress(
                f"feature manifests 1d: checked {checked:,}; failures {len(failures):,}; "
                f"lifecycle sessions {len(lifecycle_sessions):,}; state transitions {adjacent_state_transitions:,}"
            )
        return item

    def _audit_subdaily_feature_manifests(
        self,
        timeframe: Timeframe,
        end_date: date,
        progress: Callable[[str], None] | None,
    ) -> dict[str, object]:
        origin = TICKER_HISTORY_ORIGIN_DATE
        manifest_dir = self.manifest_root / "features" / timeframe.value
        manifests = sorted(
            path
            for path in manifest_dir.glob("*/*.json")
            if origin <= date.fromisoformat(path.stem) <= end_date
        )
        forbidden = sorted(
            path for path in manifest_dir.glob("*/*.json") if date.fromisoformat(path.stem) < origin
        )
        source_dates = {
            _partition_date(path)
            for path in self._files_for(timeframe)
            if origin <= _partition_date(path) <= end_date
        }
        manifest_dates = {date.fromisoformat(path.stem) for path in manifests}
        failures: list[str] = []
        failure_types: dict[str, int] = {}
        checked = 0
        prior_output: str | None = None
        for path in manifests:
            trading_date = date.fromisoformat(path.stem)
            errors: list[str] = []
            record: FeaturePartitionManifest | None = None
            try:
                record = FeaturePartitionManifest.from_dict(_json(path, "feature manifest"))
                record.validate_contract(timeframe, trading_date)
                source = Path(record.source_path)
                feature = Path(record.feature_path)
                if not source.is_file():
                    errors.append("SOURCE_FILE: bound source missing")
                elif record.source_sha256 != sha256_file(source):
                    errors.append("SOURCE_HASH: source hash mismatch")
                if not feature.is_file():
                    errors.append("FEATURE_FILE: bound feature missing")
                elif record.feature_sha256 != sha256_file(feature):
                    errors.append("FEATURE_HASH: feature hash mismatch")
                expected_dependency = feature_dependency_fingerprint(
                    source_sha256=record.source_sha256,
                    input_state_fingerprint=record.input_state_fingerprint,
                )
                if record.dependency_fingerprint != expected_dependency:
                    errors.append("DEPENDENCY: dependency fingerprint mismatch")
                if prior_output is not None and record.input_state_fingerprint != prior_output:
                    errors.append("STATE_CHAIN: pairwise state fingerprint discontinuity")
            except Exception as exc:
                errors.append(f"MANIFEST: {type(exc).__name__}: {exc}")
            if record is not None:
                # Advance from the actual neighboring manifest even if a separate hash check failed;
                # this prevents one isolated issue from creating thousands of false chain failures.
                prior_output = record.output_state_fingerprint
            if errors:
                for error in errors:
                    failures.append(f"{trading_date}: {error}")
                    key = error.split(":", 1)[0]
                    failure_types[key] = failure_types.get(key, 0) + 1
            else:
                checked += 1

        missing_manifest_dates = sorted(source_dates - manifest_dates)
        orphan_manifest_dates = sorted(manifest_dates - source_dates)
        coverage_exact = (
            bool(source_dates)
            and source_dates == manifest_dates
            and end_date in source_dates
            and end_date in manifest_dates
        )
        item: dict[str, object] = {
            "origin": origin.isoformat(),
            "lineage_basis": "PAIRWISE_PERSISTED_MANIFEST_STATE_CHAIN",
            "manifest_count": len(manifests),
            "checked_manifest_count": checked,
            "forbidden_pre_origin_manifest_count": len(forbidden),
            "failure_count": len(failures),
            "failure_types": failure_types,
            "failure_samples": failures[:20],
            "state_chain_continuous": len(failures) == 0,
            "source_partition_date_count": len(source_dates),
            "manifest_partition_date_count": len(manifest_dates),
            "source_manifest_date_coverage_exact": coverage_exact,
            "missing_manifest_date_count": len(missing_manifest_dates),
            "missing_manifest_dates": [item.isoformat() for item in missing_manifest_dates[:20]],
            "orphan_manifest_date_count": len(orphan_manifest_dates),
            "orphan_manifest_dates": [item.isoformat() for item in orphan_manifest_dates[:20]],
            "latest_source_date": max(source_dates).isoformat() if source_dates else None,
            "latest_manifest_date": max(manifest_dates).isoformat() if manifest_dates else None,
        }
        item["pass"] = bool(manifests) and not forbidden and not failures and coverage_exact
        if progress is not None:
            progress(
                f"feature manifests {timeframe.value}: checked {checked:,}; failures {len(failures):,}"
            )
        return item

    def _audit_feature_manifests(
        self,
        end_date: date,
        progress: Callable[[str], None] | None,
    ) -> dict[str, object]:
        daily = self._audit_daily_feature_manifests(end_date, progress)
        hourly = self._audit_subdaily_feature_manifests(Timeframe.HOUR_1, end_date, progress)
        four_hour = self._audit_subdaily_feature_manifests(Timeframe.HOUR_4, end_date, progress)
        return {
            Timeframe.DAY_1.value: daily,
            Timeframe.HOUR_1.value: hourly,
            Timeframe.HOUR_4.value: four_hour,
            "pass": bool(daily["pass"]) and bool(hourly["pass"]) and bool(four_hour["pass"]),
        }

    def _audit_accepted_historical_evidence(self) -> dict[str, object]:
        base = self.derived_root / "historical_backfill" / "alpaca"
        identity_root = base / "identity"
        identity_policy_path = identity_root / "identity_report.json"
        identity_segment_path = identity_root / "identity_segment_report.json"
        identity_segments_path = identity_root / "identity_segments.parquet"
        identity_chains_path = identity_root / "identity_chains.parquet"
        safe_edges_path = identity_root / "safe_rename_edges.parquet"
        quarantined_edges_path = identity_root / "quarantined_safe_rename_edges.parquet"
        ambiguous_symbols_path = identity_root / "identity_ambiguous_symbols.parquet"
        identity_policy = _json(identity_policy_path, "Gate 4 identity policy report")
        identity_segments = _json(identity_segment_path, "Gate 4-C v2 identity segment report")

        con = connect_utc(":memory:")
        try:
            duplicate_segment_ids, duplicate_symbols, rows, ambiguous_segment_rows = con.execute(
                f"""
                SELECT
                    count(*) - count(DISTINCT segment_id),
                    count(*) - count(DISTINCT symbol),
                    count(*),
                    count(*) FILTER (WHERE identity_ambiguous = TRUE)
                FROM read_parquet('{identity_segments_path.as_posix().replace("'", "''")}')
                """
            ).fetchone()
            chain_errors = int(
                con.execute(
                    f"""
                    SELECT count(*) FROM (
                        SELECT identity_chain_id
                        FROM read_parquet('{identity_segments_path.as_posix().replace("'", "''")}')
                        GROUP BY identity_chain_id
                        HAVING min(chain_position) <> 0
                           OR max(chain_position) <> max(chain_length) - 1
                           OR count(*) <> max(chain_length)
                           OR count(DISTINCT chain_length) <> 1
                    )
                    """
                ).fetchone()[0]
            )
            chain_rows = int(con.execute(
                f"SELECT count(*) FROM read_parquet('{identity_chains_path.as_posix().replace("'", "''")}')"
            ).fetchone()[0])
            safe_edge_rows = int(con.execute(
                f"SELECT count(*) FROM read_parquet('{safe_edges_path.as_posix().replace("'", "''")}')"
            ).fetchone()[0])
            quarantined_edge_rows = int(con.execute(
                f"SELECT count(*) FROM read_parquet('{quarantined_edges_path.as_posix().replace("'", "''")}')"
            ).fetchone()[0])
            ambiguous_symbol_rows = int(con.execute(
                f"SELECT count(*) FROM read_parquet('{ambiguous_symbols_path.as_posix().replace("'", "''")}')"
            ).fetchone()[0])
        finally:
            con.close()

        identity_checks = {
            "identity_policy_contract": identity_policy.get("contract_version")
            == ALPACA_BACKFILL_IDENTITY_POLICY_CONTRACT_VERSION,
            "identity_policy_canonical_unchanged": identity_policy.get("canonical_data_modified") is False,
            **_identity_v2_report_checks(identity_segments),
            "segment_rows_match_report": int(rows) == int(identity_segments.get("identity_segments", -1)),
            "observed_symbols_match_segments": int(rows) == int(identity_segments.get("observed_symbols", -1)),
            "segment_ids_unique": int(duplicate_segment_ids) == 0,
            "provider_native_symbols_unique_in_segments": int(duplicate_symbols) == 0,
            "chain_positions_structurally_exact": chain_errors == 0,
            "chain_rows_match_report": chain_rows == int(identity_segments.get("identity_chains", -1)),
            "eligible_safe_edge_rows_match_report": safe_edge_rows
            == int(identity_segments.get("identity_eligible_safe_edges", -1)),
            "quarantined_edge_rows_match_report": quarantined_edge_rows
            == int(identity_segments.get("quarantined_unique_safe_edges", -1)),
            "ambiguous_symbol_rows_match_report": ambiguous_symbol_rows
            == int(identity_segments.get("cusip_ambiguous_symbols", -1)),
            "ambiguous_segment_rows_match_report": int(ambiguous_segment_rows)
            == int(identity_segments.get("cusip_ambiguous_symbols", -1)),
        }

        final_path = (
            base
            / "ml_long_history"
            / "v1"
            / "evaluation"
            / "v1"
            / "benchmark"
            / "v1"
            / "historical_extension_final_acceptance.json"
        )
        final = _json(final_path, "historical extension final acceptance")
        disposition = dict(final.get("final_disposition") or {})
        final_checks = dict(final.get("checks") or {})
        closeout_checks = {
            "closeout_contract": final.get("contract_version")
            == HISTORICAL_BACKFILL_CLOSEOUT_CONTRACT_VERSION,
            "closeout_pass": final.get("pass") is True,
            "phase10_model_authority_preserved": disposition.get(
                "accepted_phase10_production_model_remains_authoritative"
            )
            is True,
            "historical_challenger_not_production": disposition.get(
                "historical_C_challenger_is_production"
            )
            is False,
            "final_holdout_not_accessed": final_checks.get("final_holdout_not_accessed") is True,
            "production_registry_unchanged": final_checks.get("production_registry_unchanged") is True,
            "production_ml_writes_zero": int(final.get("production_ml_writes", -1)) == 0,
            "broker_writes_zero": int(final.get("broker_writes", -1)) == 0,
        }
        artifact_paths = {
            "identity_policy": identity_policy_path,
            "identity_segment_report": identity_segment_path,
            "identity_segments": identity_segments_path,
            "identity_chains": identity_chains_path,
            "safe_rename_edges": safe_edges_path,
            "quarantined_safe_rename_edges": quarantined_edges_path,
            "identity_ambiguous_symbols": ambiguous_symbols_path,
        }
        return {
            "identity_policy_path": str(identity_policy_path.resolve()),
            "identity_policy_sha256": sha256_file(identity_policy_path),
            "identity_segment_report_path": str(identity_segment_path.resolve()),
            "identity_segment_report_sha256": sha256_file(identity_segment_path),
            "identity_segments_path": str(identity_segments_path.resolve()),
            "identity_segments_sha256": sha256_file(identity_segments_path),
            "identity_artifact_hashes": {
                name: sha256_file(path) for name, path in artifact_paths.items()
            },
            "identity_rows": int(rows),
            "identity_ambiguous_rows": int(ambiguous_segment_rows),
            "identity_checks": identity_checks,
            "historical_extension_acceptance_path": str(final_path.resolve()),
            "historical_extension_acceptance_sha256": sha256_file(final_path),
            "closeout_checks": closeout_checks,
            "accepted": final.get("pass") is True,
            "phase10_authority_reference_present": closeout_checks[
                "phase10_model_authority_preserved"
            ],
            "pass": all(identity_checks.values()) and all(closeout_checks.values()),
        }
