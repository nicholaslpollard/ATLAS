from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_candidate_canonical import (
    ALPACA_BACKFILL_CANDIDATE_CANONICAL_CONTRACT_VERSION,
    AlpacaBackfillCandidateCanonicalBuilder,
    AlpacaBackfillCandidateCanonicalValidator,
    candidate_daily_relative_path,
    candidate_source_id,
)
from packages.data.alpaca_backfill_policy import ALPACA_BACKFILL_END, ALPACA_BACKFILL_START
from packages.data.alpaca_backfill_seam import ALPACA_BACKFILL_SEAM_TARGET_SESSION
from packages.data.alpaca_backfill_seam_final import (
    ALPACA_BACKFILL_SEAM_FINAL_CONTRACT_VERSION,
    AlpacaBackfillSeamFinalValidator,
)
from packages.data.alpaca_backfill_validated_evidence import sha256_file, stable_source_fingerprint
from packages.schemas.canonical_market import (
    CANONICAL_STOCK_DAILY_SCHEMA_VERSION,
    canonical_stock_daily_schema_matches,
)


ALPACA_BACKFILL_CANONICAL_PROMOTION_CONTRACT_VERSION = (
    "historical-backfill-canonical-promotion-v1-journaled-session-atomic"
)
PROMOTION_ROLE = "PRODUCTION_CANONICAL_DAILY_HISTORY"
PROMOTION_STATUS_PREFLIGHT = "PREFLIGHT_PASS"
PROMOTION_STATUS_APPLYING = "APPLYING"
PROMOTION_STATUS_FAILED = "FAILED"
PROMOTION_STATUS_COMPLETE = "COMPLETE"

COPY_NEW = "COPY_NEW"
REUSE_EXACT = "REUSE_EXACT"
FAIL_COLLISION = "FAIL_COLLISION"


def _sql_string(value: str | Path) -> str:
    return "'" + str(value).replace("\\", "/").replace("'", "''") + "'"


def _sql_path_list(paths: list[Path]) -> str:
    return "[" + ",".join(_sql_string(path) for path in paths) + "]"


def session_date_from_daily_path(path: Path) -> date:
    name = Path(path).parent.name
    if not name.startswith("date="):
        raise ValueError(f"canonical daily path lacks date= partition: {path}")
    try:
        return date.fromisoformat(name.split("=", 1)[1])
    except ValueError as exc:
        raise ValueError(f"invalid canonical daily date partition: {path}") from exc


def promotion_action(*, target_exists: bool, target_sha256: str | None, candidate_sha256: str) -> str:
    if not target_exists:
        return COPY_NEW
    if target_sha256 == candidate_sha256:
        return REUSE_EXACT
    return FAIL_COLLISION


def inventory_fingerprint(rows: list[dict[str, object]]) -> str:
    stable_rows = [
        {
            "session_date": str(row["session_date"]),
            "relative_path": str(row["relative_path"]).replace("\\", "/"),
            "sha256": str(row["sha256"]),
        }
        for row in rows
    ]
    stable_rows.sort(key=lambda row: (row["session_date"], row["relative_path"]))
    return stable_source_fingerprint({"files": stable_rows})


def promotion_source_fingerprint(
    *,
    candidate_fingerprint: str,
    gate7_fingerprint: str,
    gate7_decision_sha256: str,
    candidate_inventory_fingerprint: str,
    massive_baseline_fingerprint: str,
) -> str:
    return stable_source_fingerprint(
        {
            "contract_version": ALPACA_BACKFILL_CANONICAL_PROMOTION_CONTRACT_VERSION,
            "canonical_daily_schema_version": CANONICAL_STOCK_DAILY_SCHEMA_VERSION,
            "candidate_fingerprint": candidate_fingerprint,
            "gate7_fingerprint": gate7_fingerprint,
            "gate7_decision_sha256": gate7_decision_sha256,
            "candidate_inventory_fingerprint": candidate_inventory_fingerprint,
            "massive_baseline_fingerprint": massive_baseline_fingerprint,
            "start_date": ALPACA_BACKFILL_START.isoformat(),
            "candidate_end_date": ALPACA_BACKFILL_END.isoformat(),
            "seam_session": ALPACA_BACKFILL_SEAM_TARGET_SESSION.isoformat(),
        }
    )


def gate8_acceptance_checks(report: dict[str, object]) -> dict[str, bool]:
    return {
        "promotion_contract": report.get("contract_version")
        == ALPACA_BACKFILL_CANONICAL_PROMOTION_CONTRACT_VERSION,
        "promotion_status_complete": report.get("status") == PROMOTION_STATUS_COMPLETE,
        "candidate_hashes_exact": report.get("candidate_hashes_exact") is True,
        "promoted_hashes_exact": report.get("promoted_hashes_exact") is True,
        "massive_baseline_unchanged": report.get("massive_baseline_unchanged") is True,
        "row_accounting_exact": report.get("row_accounting_exact") is True,
        "session_accounting_exact": report.get("session_accounting_exact") is True,
        "production_schema_exact": report.get("production_schema_exact") is True,
        "production_semantics_exact": report.get("production_semantics_exact") is True,
        "duplicate_keys_zero": int(report.get("duplicate_keys", -1)) == 0,
        "seam_not_overwritten": report.get("seam_not_overwritten") is True,
        "gate7_policy_bound": report.get("gate7_policy_bound") is True,
    }


class AlpacaBackfillCanonicalPromotion:
    """Gate 8 journaled promotion of accepted Alpaca daily candidate history.

    The whole promotion is resumable, while each individual canonical session file is
    copied to a same-directory temporary path and atomically promoted. Existing target
    files are never replaced: an exact SHA match is reusable evidence; any other
    preexisting content is a hard collision. The Massive era is fingerprinted before
    writes and must remain byte-for-byte unchanged afterward.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)
        self.candidate_builder = AlpacaBackfillCandidateCanonicalBuilder(settings)
        self.candidate_validator = AlpacaBackfillCandidateCanonicalValidator(settings)
        self.gate7_validator = AlpacaBackfillSeamFinalValidator(settings)

        self.canonical_root = settings.resolved_path(settings.data.paths.canonical)
        self.canonical_daily_root = self.canonical_root / "stocks" / "1d"
        derived = settings.resolved_path(settings.data.paths.derived)
        self.derived_root = derived / "historical_backfill" / "alpaca" / "promotion" / "v1"
        self.preflight_report_path = self.derived_root / "gate8_preflight_report.json"
        manifests = settings.resolved_path(settings.data.paths.manifests)
        self.promotion_manifest_path = (
            manifests / "historical_backfill" / "alpaca" / "canonical_promotion_v1.json"
        )
        self.gate7_report_path = (
            derived
            / "historical_backfill"
            / "alpaca"
            / "seam"
            / "final"
            / "gate7_final_report.json"
        )
        self.gate7_decision_path = (
            derived
            / "historical_backfill"
            / "alpaca"
            / "seam"
            / "final"
            / "seam_promotion_decisions.parquet"
        )

    def _load_parents(self) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        if not self.candidate_builder.report_path.is_file():
            raise RuntimeError("Gate 8 requires the accepted Gate 6 candidate manifest")
        candidate_report = json.loads(
            self.candidate_builder.report_path.read_text(encoding="utf-8")
        )
        if (
            candidate_report.get("contract_version")
            != ALPACA_BACKFILL_CANDIDATE_CANONICAL_CONTRACT_VERSION
        ):
            raise RuntimeError("Gate 8 Gate 6 candidate contract mismatch")
        candidate_validation = self.candidate_validator.run()
        if candidate_validation.get("pass") is not True:
            raise RuntimeError("Gate 8 requires a passing Gate 6 candidate validator")

        gate7_report = self.gate7_validator.run()
        if gate7_report.get("contract_version") != ALPACA_BACKFILL_SEAM_FINAL_CONTRACT_VERSION:
            raise RuntimeError("Gate 8 Gate 7 final contract mismatch")
        if gate7_report.get("gate7_pass") is not True:
            raise RuntimeError("Gate 8 requires final Gate 7 PASS")
        if not self.gate7_decision_path.is_file():
            raise RuntimeError("Gate 8 requires the final Gate 7 seam decision map")
        return candidate_report, candidate_validation, gate7_report

    def _candidate_inventory(
        self, candidate_report: dict[str, Any]
    ) -> list[dict[str, object]]:
        candidate_root = Path(str(candidate_report["candidate_root"]))
        sessions = self.calendar.sessions_in_range(ALPACA_BACKFILL_START, ALPACA_BACKFILL_END)
        rows: list[dict[str, object]] = []
        for session in sessions:
            relative = candidate_daily_relative_path(session)
            path = candidate_root / relative
            if not path.is_file():
                raise RuntimeError(f"Gate 8 candidate session file is missing: {path}")
            rows.append(
                {
                    "session_date": session.isoformat(),
                    "relative_path": relative.as_posix(),
                    "path": str(path),
                    "sha256": sha256_file(path),
                }
            )
        if len(rows) != int(candidate_report.get("candidate_sessions", -1)):
            raise RuntimeError(
                "Gate 8 candidate session inventory does not match Gate 6 report: "
                f"files={len(rows)} report={candidate_report.get('candidate_sessions')}"
            )
        return rows

    def _canonical_inventory(self) -> dict[date, Path]:
        result: dict[date, Path] = {}
        if not self.canonical_daily_root.exists():
            return result
        for path in self.canonical_daily_root.glob("year=*/date=*/part-000.parquet"):
            session = session_date_from_daily_path(path)
            if session in result:
                raise RuntimeError(f"duplicate canonical daily session path: {session}")
            result[session] = path
        return result

    def _massive_baseline(
        self, canonical_inventory: dict[date, Path]
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for session, path in sorted(canonical_inventory.items()):
            if session < ALPACA_BACKFILL_SEAM_TARGET_SESSION:
                continue
            rows.append(
                {
                    "session_date": session.isoformat(),
                    "relative_path": path.relative_to(self.canonical_root).as_posix(),
                    "path": str(path),
                    "sha256": sha256_file(path),
                }
            )
        return rows

    @staticmethod
    def _schema_exact(paths: list[Path]) -> bool:
        if not paths:
            return False
        con = duckdb.connect(":memory:")
        try:
            description = con.execute(
                f"DESCRIBE SELECT * FROM read_parquet({_sql_path_list(paths)}, "
                "hive_partitioning=false)"
            ).fetchall()
        finally:
            con.close()
        return canonical_stock_daily_schema_matches(description)

    @staticmethod
    def _massive_semantics(paths: list[Path]) -> dict[str, int]:
        if not paths:
            return {"rows": 0, "semantic_mismatches": 1}
        con = duckdb.connect(":memory:")
        try:
            row = con.execute(
                f"""
                SELECT count(*) AS rows,
                       count(*) FILTER (
                           WHERE provider != 'massive'
                              OR timeframe != '1d'
                              OR dataset != 'stock_daily_aggregates'
                              OR session_segment != 'regular'
                       ) AS semantic_mismatches
                FROM read_parquet({_sql_path_list(paths)}, hive_partitioning=false)
                """
            ).fetchone()
        finally:
            con.close()
        assert row is not None
        return {"rows": int(row[0]), "semantic_mismatches": int(row[1])}

    def preflight(self) -> dict[str, object]:
        candidate_report, candidate_validation, gate7_report = self._load_parents()
        candidate_files = self._candidate_inventory(candidate_report)
        candidate_by_session = {
            date.fromisoformat(str(item["session_date"])): item for item in candidate_files
        }
        canonical_inventory = self._canonical_inventory()

        collision_mismatches: list[str] = []
        preexisting_exact = 0
        for session, item in candidate_by_session.items():
            target = canonical_inventory.get(session)
            if target is None:
                continue
            target_sha = sha256_file(target)
            action = promotion_action(
                target_exists=True,
                target_sha256=target_sha,
                candidate_sha256=str(item["sha256"]),
            )
            if action == REUSE_EXACT:
                preexisting_exact += 1
            else:
                collision_mismatches.append(session.isoformat())

        unexpected_target_sessions = [
            session.isoformat()
            for session in sorted(canonical_inventory)
            if ALPACA_BACKFILL_START <= session < ALPACA_BACKFILL_SEAM_TARGET_SESSION
            and session not in candidate_by_session
        ]

        massive_files = self._massive_baseline(canonical_inventory)
        massive_paths = [Path(str(item["path"])) for item in massive_files]
        massive_semantics = self._massive_semantics(massive_paths)
        massive_schema_exact = self._schema_exact(massive_paths)
        massive_first = massive_files[0]["session_date"] if massive_files else None

        candidate_inventory_fp = inventory_fingerprint(candidate_files)
        massive_baseline_fp = inventory_fingerprint(massive_files)
        decision_sha = sha256_file(self.gate7_decision_path)
        source_fingerprint = promotion_source_fingerprint(
            candidate_fingerprint=str(candidate_report["source_fingerprint"]),
            gate7_fingerprint=str(gate7_report["source_fingerprint"]),
            gate7_decision_sha256=decision_sha,
            candidate_inventory_fingerprint=candidate_inventory_fp,
            massive_baseline_fingerprint=massive_baseline_fp,
        )

        checks = {
            "gate6_contract_and_pass": candidate_report.get("contract_version")
            == ALPACA_BACKFILL_CANDIDATE_CANONICAL_CONTRACT_VERSION
            and candidate_validation.get("pass") is True,
            "gate7_contract_and_pass": gate7_report.get("contract_version")
            == ALPACA_BACKFILL_SEAM_FINAL_CONTRACT_VERSION
            and gate7_report.get("gate7_pass") is True,
            "candidate_session_accounting_exact": len(candidate_files)
            == int(candidate_report.get("candidate_sessions", -1)),
            "candidate_row_accounting_exact": int(candidate_report.get("candidate_rows", -1))
            == int(candidate_report.get("expected_trade_backed_rows", -2)),
            "candidate_hashes_present": all(bool(item.get("sha256")) for item in candidate_files),
            "target_collisions_clean": not collision_mismatches,
            "target_session_namespace_clean": not unexpected_target_sessions,
            "massive_baseline_present": bool(massive_files),
            "massive_baseline_starts_at_seam": massive_first
            == ALPACA_BACKFILL_SEAM_TARGET_SESSION.isoformat(),
            "massive_baseline_schema_exact": massive_schema_exact,
            "massive_baseline_semantics_exact": massive_semantics["semantic_mismatches"] == 0,
            "gate7_decision_map_bound": decision_sha == sha256_file(self.gate7_decision_path),
            "production_writes_zero": True,
        }

        report: dict[str, object] = {
            "contract_version": ALPACA_BACKFILL_CANONICAL_PROMOTION_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "status": PROMOTION_STATUS_PREFLIGHT if all(checks.values()) else "PREFLIGHT_FAIL",
            "production_writes": 0,
            "promotion_role": PROMOTION_ROLE,
            "source_fingerprint": source_fingerprint,
            "candidate_source_fingerprint": candidate_report["source_fingerprint"],
            "gate7_source_fingerprint": gate7_report["source_fingerprint"],
            "gate7_decision_sha256": decision_sha,
            "candidate_inventory_fingerprint": candidate_inventory_fp,
            "massive_baseline_fingerprint": massive_baseline_fp,
            "candidate_rows": int(candidate_report["candidate_rows"]),
            "candidate_sessions": len(candidate_files),
            "candidate_symbols": int(candidate_report["observed_symbols"]),
            "candidate_first_session": candidate_files[0]["session_date"],
            "candidate_last_session": candidate_files[-1]["session_date"],
            "preexisting_exact_candidate_sessions": preexisting_exact,
            "collision_mismatch_sessions": collision_mismatches,
            "unexpected_target_sessions": unexpected_target_sessions,
            "massive_baseline_sessions": len(massive_files),
            "massive_baseline_first_session": massive_first,
            "massive_baseline_last_session": massive_files[-1]["session_date"] if massive_files else None,
            "massive_baseline_rows": massive_semantics["rows"],
            "massive_baseline_semantic_mismatches": massive_semantics["semantic_mismatches"],
            "massive_baseline_schema_exact": massive_schema_exact,
            "candidate_files": candidate_files,
            "massive_baseline_files": massive_files,
            "checks": checks,
            "pass": all(checks.values()),
            "preflight_report_path": str(self.preflight_report_path),
            "promotion_manifest_path": str(self.promotion_manifest_path),
        }
        atomic_write_text(
            self.preflight_report_path,
            json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        )
        return report

    @staticmethod
    def _copy_exact(source: Path, target: Path, expected_sha256: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = unique_temp_path(target)
        try:
            shutil.copy2(source, temp)
            if sha256_file(temp) != expected_sha256:
                raise RuntimeError(f"Gate 8 staged copy hash mismatch: {source} -> {target}")
            replace_with_retry(temp, target)
            if sha256_file(target) != expected_sha256:
                raise RuntimeError(f"Gate 8 promoted file hash mismatch: {target}")
        except Exception:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def _write_journal(self, payload: dict[str, object]) -> None:
        atomic_write_text(
            self.promotion_manifest_path,
            json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        )

    def _massive_baseline_unchanged(self, baseline: list[dict[str, object]]) -> bool:
        for item in baseline:
            path = Path(str(item["path"]))
            if not path.is_file() or sha256_file(path) != item.get("sha256"):
                return False
        return True

    def _promoted_stats(
        self,
        target_paths: list[Path],
        *,
        expected_source_id: str,
    ) -> dict[str, object]:
        con = duckdb.connect(":memory:")
        try:
            description = con.execute(
                f"DESCRIBE SELECT * FROM read_parquet({_sql_path_list(target_paths)}, "
                "hive_partitioning=false)"
            ).fetchall()
            row = con.execute(
                f"""
                WITH promoted AS (
                    SELECT * FROM read_parquet({_sql_path_list(target_paths)}, hive_partitioning=false)
                )
                SELECT count(*) AS rows,
                       count(DISTINCT session_date) AS sessions,
                       count(DISTINCT symbol) AS symbols,
                       count(*) - count(DISTINCT (symbol, session_date)) AS duplicate_keys,
                       count(*) FILTER (
                           WHERE provider != 'alpaca'
                              OR timeframe != '1d'
                              OR dataset != 'stock_daily_aggregates'
                              OR session_segment != 'regular'
                              OR source_id != ?
                              OR is_adjusted != FALSE
                              OR provider_timestamp_utc IS NULL
                       ) AS semantic_mismatches,
                       min(session_date) AS first_session,
                       max(session_date) AS last_session
                FROM promoted
                """,
                [expected_source_id],
            ).fetchone()
        finally:
            con.close()
        assert row is not None
        return {
            "rows": int(row[0]),
            "sessions": int(row[1]),
            "symbols": int(row[2]),
            "duplicate_keys": int(row[3]),
            "semantic_mismatches": int(row[4]),
            "first_session": str(row[5]),
            "last_session": str(row[6]),
            "schema_exact": canonical_stock_daily_schema_matches(description),
        }

    def apply(self) -> dict[str, object]:
        preflight = self.preflight()
        if preflight.get("pass") is not True:
            raise RuntimeError("Gate 8 promotion refused because preflight did not pass")

        journal: dict[str, object] = {
            "contract_version": ALPACA_BACKFILL_CANONICAL_PROMOTION_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "status": PROMOTION_STATUS_APPLYING,
            "promotion_role": PROMOTION_ROLE,
            "source_fingerprint": preflight["source_fingerprint"],
            "candidate_source_fingerprint": preflight["candidate_source_fingerprint"],
            "gate7_source_fingerprint": preflight["gate7_source_fingerprint"],
            "gate7_decision_sha256": preflight["gate7_decision_sha256"],
            "preflight_report_sha256": sha256_file(self.preflight_report_path),
            "copied_sessions": 0,
            "reused_exact_sessions": 0,
            "completed_through": None,
        }
        self._write_journal(journal)

        copied = 0
        reused = 0
        current_year: int | None = None
        try:
            for item in preflight["candidate_files"]:
                session = date.fromisoformat(str(item["session_date"]))
                if session >= ALPACA_BACKFILL_SEAM_TARGET_SESSION:
                    raise RuntimeError(f"Gate 8 refused post-seam candidate session: {session}")
                source = Path(str(item["path"]))
                target = self.canonical_root / str(item["relative_path"])
                expected_sha = str(item["sha256"])
                if target.exists():
                    action = promotion_action(
                        target_exists=True,
                        target_sha256=sha256_file(target),
                        candidate_sha256=expected_sha,
                    )
                    if action != REUSE_EXACT:
                        raise RuntimeError(f"Gate 8 target collision changed after preflight: {target}")
                    reused += 1
                else:
                    self._copy_exact(source, target, expected_sha)
                    copied += 1

                if current_year is None:
                    current_year = session.year
                if session.year != current_year:
                    current_year = session.year
                    journal.update(
                        {
                            "copied_sessions": copied,
                            "reused_exact_sessions": reused,
                            "completed_through": session.isoformat(),
                        }
                    )
                    self._write_journal(journal)

            candidate_targets = [
                self.canonical_root / str(item["relative_path"])
                for item in preflight["candidate_files"]
            ]
            target_hashes_exact = all(
                path.is_file()
                and sha256_file(path) == str(item["sha256"])
                for path, item in zip(candidate_targets, preflight["candidate_files"])
            )
            candidate_hashes_exact = all(
                Path(str(item["path"])).is_file()
                and sha256_file(Path(str(item["path"]))) == str(item["sha256"])
                for item in preflight["candidate_files"]
            )
            massive_unchanged = self._massive_baseline_unchanged(
                list(preflight["massive_baseline_files"])
            )
            expected_source_id = candidate_source_id(
                str(preflight["candidate_source_fingerprint"])
            )
            stats = self._promoted_stats(candidate_targets, expected_source_id=expected_source_id)

            report: dict[str, object] = {
                **journal,
                "generated_at_utc": datetime.now(UTC).isoformat(),
                "status": PROMOTION_STATUS_COMPLETE,
                "copied_sessions": copied,
                "reused_exact_sessions": reused,
                "completed_through": preflight["candidate_last_session"],
                "candidate_rows": preflight["candidate_rows"],
                "candidate_sessions": preflight["candidate_sessions"],
                "candidate_symbols": preflight["candidate_symbols"],
                "promoted_rows": stats["rows"],
                "promoted_sessions": stats["sessions"],
                "promoted_symbols": stats["symbols"],
                "duplicate_keys": stats["duplicate_keys"],
                "semantic_mismatches": stats["semantic_mismatches"],
                "first_session": stats["first_session"],
                "last_session": stats["last_session"],
                "candidate_hashes_exact": candidate_hashes_exact,
                "promoted_hashes_exact": target_hashes_exact,
                "massive_baseline_unchanged": massive_unchanged,
                "row_accounting_exact": stats["rows"] == int(preflight["candidate_rows"]),
                "session_accounting_exact": stats["sessions"]
                == int(preflight["candidate_sessions"]),
                "production_schema_exact": stats["schema_exact"] is True,
                "production_semantics_exact": stats["semantic_mismatches"] == 0,
                "seam_not_overwritten": all(
                    date.fromisoformat(str(item["session_date"]))
                    < ALPACA_BACKFILL_SEAM_TARGET_SESSION
                    for item in preflight["candidate_files"]
                )
                and self._massive_baseline_unchanged(list(preflight["massive_baseline_files"])),
                "gate7_policy_bound": sha256_file(self.gate7_decision_path)
                == preflight["gate7_decision_sha256"],
                "massive_baseline_fingerprint": preflight["massive_baseline_fingerprint"],
                "candidate_inventory_fingerprint": preflight["candidate_inventory_fingerprint"],
                "promotion_manifest_path": str(self.promotion_manifest_path),
                "preflight_report_path": str(self.preflight_report_path),
            }
            checks = gate8_acceptance_checks(report)
            report["checks"] = checks
            report["pass"] = all(checks.values())
            self._write_journal(report)
            if report["pass"] is not True:
                raise RuntimeError("Gate 8 post-promotion validation failed")
            return report
        except Exception as exc:
            journal.update(
                {
                    "generated_at_utc": datetime.now(UTC).isoformat(),
                    "status": PROMOTION_STATUS_FAILED,
                    "copied_sessions": copied,
                    "reused_exact_sessions": reused,
                    "last_error": f"{type(exc).__name__}: {exc}",
                }
            )
            self._write_journal(journal)
            raise

    def validate(self) -> dict[str, object]:
        if not self.promotion_manifest_path.is_file():
            raise RuntimeError("Gate 8 promotion manifest is missing")
        report = json.loads(self.promotion_manifest_path.read_text(encoding="utf-8"))
        checks = gate8_acceptance_checks(report)
        report["checks"] = checks
        report["pass"] = all(checks.values())
        return report
