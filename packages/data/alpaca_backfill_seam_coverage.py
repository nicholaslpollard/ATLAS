from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pandas as pd

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_seam import ALPACA_BACKFILL_SEAM_TARGET_SESSION
from packages.data.alpaca_backfill_seam_lifecycle import (
    ALPACA_BACKFILL_SEAM_LIFECYCLE_CONTRACT_VERSION,
)
from packages.data.alpaca_backfill_validated_evidence import sha256_file, stable_source_fingerprint
from packages.data.paths import MarketDataPaths


ALPACA_BACKFILL_SEAM_COVERAGE_CONTRACT_VERSION = (
    "historical-backfill-seam-v3-massive-coverage-horizon-continuity-reset"
)
MASSIVE_COVERAGE_HORIZON_SESSIONS = 20
MASSIVE_COVERAGE_DISCONTINUITY_STATUS = (
    "MASSIVE_COVERAGE_DISCONTINUITY_WITH_ALPACA_CONTINUATION"
)
SEAM_RESET_POLICY = "PRESERVE_PRESEAM_HISTORY_RESET_CONTINUITY_AT_PROVIDER_SEAM"


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sql_string(value: str | Path) -> str:
    return "'" + str(value).replace("\\", "/").replace("'", "''") + "'"


def classify_massive_coverage(
    *,
    reference_identity_count: int,
    first_massive_session: date | None,
) -> str:
    if reference_identity_count > 1:
        return "REVIEW_MASSIVE_REFERENCE_IDENTITY_AMBIGUOUS"
    if first_massive_session is not None and reference_identity_count == 1:
        return "MASSIVE_COVERAGE_RESUMES_UNIQUE_REFERENCE"
    if first_massive_session is not None:
        return "REVIEW_MASSIVE_BAR_WITHOUT_SEAM_REFERENCE"
    if reference_identity_count == 1:
        return "MASSIVE_REFERENCE_PRESENT_NO_BAR_IN_HORIZON"
    return "MASSIVE_REFERENCE_ABSENT_NO_BAR_IN_HORIZON"


def seam_promotion_policy(_coverage_class: str) -> str:
    # These symbols are in this audit precisely because Alpaca traded them on the
    # first Massive production session while Massive did not.  Regardless of what
    # Massive does later, continuity across 2021-08-13 -> 2021-08-16 cannot be
    # silently inferred.  Valid pre-seam history remains usable, but state/identity
    # continuity must restart on the Massive side unless a later explicit bridge is
    # separately accepted.
    return SEAM_RESET_POLICY


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


class AlpacaBackfillSeamCoverageAudit:
    """Gate 7-C local audit of Massive coverage after the provider seam.

    This gate never backfills Massive with Alpaca after the locked source boundary.
    It characterizes symbols that Alpaca still traded on 2021-08-16 while Massive
    did not, and locks them to a continuity-reset policy for later promotion.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        root = derived / "historical_backfill" / "alpaca" / "seam"
        self.v2_root = root / "v2"
        self.root = root / "v3"
        self.parent_report_path = self.v2_root / "seam_lifecycle_report.json"
        self.classification_path = self.v2_root / "boundary_lifecycle_classification.parquet"
        self.reference_path = self.paths.reference_snapshot_file(ALPACA_BACKFILL_SEAM_TARGET_SESSION)
        self.detail_path = self.root / "massive_coverage_discontinuities.parquet"
        self.report_path = self.root / "massive_coverage_horizon_report.json"
        canonical = settings.resolved_path(settings.data.paths.canonical)
        self.daily_root = canonical / "stocks" / "1d"

    def _load_parent(self) -> dict[str, object]:
        if not self.parent_report_path.is_file():
            raise RuntimeError("Gate 7-C requires the Gate 7-B lifecycle report")
        if not self.classification_path.is_file():
            raise RuntimeError("Gate 7-C requires the Gate 7-B lifecycle classification")
        if not self.reference_path.is_file():
            raise RuntimeError("Gate 7-C requires the Massive 2021-08-16 reference snapshot")
        parent = json.loads(self.parent_report_path.read_text(encoding="utf-8"))
        if parent.get("contract_version") != ALPACA_BACKFILL_SEAM_LIFECYCLE_CONTRACT_VERSION:
            raise RuntimeError("Gate 7-C Gate 7-B contract mismatch")
        if parent.get("structural_pass") is not True:
            raise RuntimeError("Gate 7-C requires Gate 7-B structural PASS")
        if parent.get("canonical_data_modified") is not False:
            raise RuntimeError("Gate 7-B did not preserve canonical safety")
        return parent

    def _horizon_files(self) -> list[tuple[date, Path]]:
        rows: list[tuple[date, Path]] = []
        year_root = self.daily_root / "year=2021"
        for path in year_root.glob("date=*/part-000.parquet"):
            try:
                session = date.fromisoformat(path.parent.name.removeprefix("date="))
            except ValueError:
                continue
            if session >= ALPACA_BACKFILL_SEAM_TARGET_SESSION:
                rows.append((session, path))
        rows.sort(key=lambda item: item[0])
        selected = rows[:MASSIVE_COVERAGE_HORIZON_SESSIONS]
        if len(selected) != MASSIVE_COVERAGE_HORIZON_SESSIONS:
            raise RuntimeError(
                "Gate 7-C requires at least "
                f"{MASSIVE_COVERAGE_HORIZON_SESSIONS} Massive daily sessions from the seam; "
                f"found {len(selected)}"
            )
        if selected[0][0] != ALPACA_BACKFILL_SEAM_TARGET_SESSION:
            raise RuntimeError(
                "Gate 7-C Massive horizon does not start on the locked 2021-08-16 seam"
            )
        return selected

    def _target_symbols(self, parent: dict[str, object]) -> list[str]:
        con = duckdb.connect(":memory:")
        try:
            rows = con.execute(
                f"SELECT symbol FROM read_parquet({_sql_string(self.classification_path)}, "
                "hive_partitioning=false) WHERE identity_status = ? ORDER BY symbol",
                [MASSIVE_COVERAGE_DISCONTINUITY_STATUS],
            ).fetchall()
        finally:
            con.close()
        symbols = [str(row[0]) for row in rows]
        expected = int(parent.get("massive_coverage_discontinuities", -1))
        if len(symbols) != expected:
            raise RuntimeError(
                "Gate 7-C discontinuity population does not match Gate 7-B report: "
                f"rows={len(symbols)} report={expected}"
            )
        if len(symbols) != len(set(symbols)):
            raise RuntimeError("Gate 7-C discontinuity symbols are not unique")
        return symbols

    def _coverage_rows(
        self,
        symbols: list[str],
        horizon: list[tuple[date, Path]],
    ) -> tuple[list[dict[str, object]], dict[str, int], dict[str, int]]:
        targets = pd.DataFrame({"symbol": symbols})
        paths_sql = ",".join(_sql_string(path) for _, path in horizon)
        con = duckdb.connect(":memory:")
        try:
            con.register("targets", targets)
            bar_cursor = con.execute(
                f"""
                SELECT b.symbol,
                       min(CAST(b.session_date AS DATE)) AS first_massive_session,
                       count(*) AS horizon_bar_rows,
                       count(DISTINCT CAST(b.session_date AS DATE)) AS horizon_sessions
                FROM read_parquet([{paths_sql}], hive_partitioning=false) b
                INNER JOIN targets t USING(symbol)
                GROUP BY b.symbol
                """
            )
            bar_map = {
                str(symbol): {
                    "first_massive_session": first_session,
                    "horizon_bar_rows": int(row_count),
                    "horizon_sessions": int(session_count),
                }
                for symbol, first_session, row_count, session_count in bar_cursor.fetchall()
            }

            ref_cursor = con.execute(
                f"""
                SELECT r.ticker,
                       count(DISTINCT r.instrument_id) AS identity_count,
                       min(r.instrument_id) AS instrument_id,
                       min(r.primary_exchange) AS primary_exchange,
                       min(r.security_type) AS security_type
                FROM read_parquet({_sql_string(self.reference_path)}, hive_partitioning=false) r
                INNER JOIN targets t ON r.ticker = t.symbol
                GROUP BY r.ticker
                """
            )
            ref_map = {
                str(ticker): {
                    "reference_identity_count": int(identity_count),
                    "massive_instrument_id": instrument_id,
                    "primary_exchange": primary_exchange,
                    "security_type": security_type,
                }
                for ticker, identity_count, instrument_id, primary_exchange, security_type
                in ref_cursor.fetchall()
            }
        finally:
            con.close()

        horizon_index = {session: index for index, (session, _path) in enumerate(horizon)}
        rows: list[dict[str, object]] = []
        exchange_counts: Counter[str] = Counter()
        security_counts: Counter[str] = Counter()

        for symbol in symbols:
            bar = bar_map.get(symbol, {})
            ref = ref_map.get(symbol, {})
            first_session = bar.get("first_massive_session")
            if first_session is not None and not isinstance(first_session, date):
                first_session = date.fromisoformat(str(first_session)[:10])
            identity_count = int(ref.get("reference_identity_count", 0))
            coverage_class = classify_massive_coverage(
                reference_identity_count=identity_count,
                first_massive_session=first_session if isinstance(first_session, date) else None,
            )
            first_index = (
                horizon_index.get(first_session) if isinstance(first_session, date) else None
            )
            primary_exchange = _text(ref.get("primary_exchange"))
            security_type = _text(ref.get("security_type"))
            if identity_count == 1 and primary_exchange is not None:
                exchange_counts[primary_exchange] += 1
            if identity_count == 1 and security_type is not None:
                security_counts[security_type] += 1
            rows.append(
                {
                    "symbol": symbol,
                    "coverage_class": coverage_class,
                    "promotion_policy": seam_promotion_policy(coverage_class),
                    "reference_identity_count": identity_count,
                    "massive_instrument_id": ref.get("massive_instrument_id") if identity_count == 1 else None,
                    "primary_exchange": primary_exchange if identity_count == 1 else None,
                    "security_type": security_type if identity_count == 1 else None,
                    "first_massive_session": first_session.isoformat() if isinstance(first_session, date) else None,
                    "first_massive_horizon_index": int(first_index) if first_index is not None else None,
                    "horizon_bar_rows": int(bar.get("horizon_bar_rows", 0)),
                    "horizon_sessions": int(bar.get("horizon_sessions", 0)),
                }
            )
        return rows, dict(sorted(exchange_counts.items())), dict(sorted(security_counts.items()))

    def run(self) -> dict[str, object]:
        parent = self._load_parent()
        horizon = self._horizon_files()
        symbols = self._target_symbols(parent)
        rows, exchange_counts, security_counts = self._coverage_rows(symbols, horizon)

        columns = (
            "symbol",
            "coverage_class",
            "promotion_policy",
            "reference_identity_count",
            "massive_instrument_id",
            "primary_exchange",
            "security_type",
            "first_massive_session",
            "first_massive_horizon_index",
            "horizon_bar_rows",
            "horizon_sessions",
        )
        _write_parquet(self.detail_path, rows, columns)

        coverage_counts = Counter(str(row["coverage_class"]) for row in rows)
        first_session_counts = Counter(
            str(row["first_massive_session"])
            for row in rows
            if row.get("first_massive_session") is not None
        )
        reference_unique = sum(int(row["reference_identity_count"] == 1) for row in rows)
        reference_absent = sum(int(row["reference_identity_count"] == 0) for row in rows)
        reference_ambiguous = sum(int(row["reference_identity_count"] > 1) for row in rows)
        resumes = sum(int(row.get("first_massive_session") is not None) for row in rows)
        never_in_horizon = len(rows) - resumes
        appears_on_seam = sum(
            int(row.get("first_massive_session") == ALPACA_BACKFILL_SEAM_TARGET_SESSION.isoformat())
            for row in rows
        )

        horizon_hashes = [
            {"session": session.isoformat(), "sha256": sha256_file(path), "path": str(path)}
            for session, path in horizon
        ]
        source_fingerprint = stable_source_fingerprint(
            {
                "contract_version": ALPACA_BACKFILL_SEAM_COVERAGE_CONTRACT_VERSION,
                "gate7b_source_fingerprint": parent["source_fingerprint"],
                "gate7b_classification_sha256": sha256_file(self.classification_path),
                "massive_reference_sha256": sha256_file(self.reference_path),
                "horizon": [(item["session"], item["sha256"]) for item in horizon_hashes],
                "symbols": symbols,
                "seam_reset_policy": SEAM_RESET_POLICY,
            }
        )

        report: dict[str, object] = {
            "contract_version": ALPACA_BACKFILL_SEAM_COVERAGE_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "canonical_data_modified": False,
            "source_fingerprint": source_fingerprint,
            "gate7b_source_fingerprint": parent["source_fingerprint"],
            "seam_session": ALPACA_BACKFILL_SEAM_TARGET_SESSION.isoformat(),
            "horizon_session_count": len(horizon),
            "horizon_first_session": horizon[0][0].isoformat(),
            "horizon_last_session": horizon[-1][0].isoformat(),
            "target_discontinuity_symbols": len(symbols),
            "expected_discontinuity_symbols": int(parent["massive_coverage_discontinuities"]),
            "coverage_class_counts": dict(sorted(coverage_counts.items())),
            "first_massive_session_counts": dict(sorted(first_session_counts.items())),
            "massive_reference_unique_symbols": reference_unique,
            "massive_reference_absent_symbols": reference_absent,
            "massive_reference_ambiguous_symbols": reference_ambiguous,
            "massive_coverage_resumes_within_horizon": resumes,
            "massive_no_bar_within_horizon": never_in_horizon,
            "targets_appearing_on_locked_seam_session": appears_on_seam,
            "unique_reference_exchange_counts": exchange_counts,
            "unique_reference_security_type_counts": security_counts,
            "promotion_policy": SEAM_RESET_POLICY,
            "horizon_file_hashes": horizon_hashes,
            "detail_path": str(self.detail_path),
            "report_path": str(self.report_path),
        }
        checks = {
            "gate7b_contract": parent.get("contract_version") == ALPACA_BACKFILL_SEAM_LIFECYCLE_CONTRACT_VERSION,
            "gate7b_structural_pass": parent.get("structural_pass") is True,
            "target_population_exact": report["target_discontinuity_symbols"] == report["expected_discontinuity_symbols"],
            "horizon_complete": report["horizon_session_count"] == MASSIVE_COVERAGE_HORIZON_SESSIONS,
            "horizon_starts_at_locked_seam": report["horizon_first_session"] == ALPACA_BACKFILL_SEAM_TARGET_SESSION.isoformat(),
            "locked_seam_absence_reconfirmed": report["targets_appearing_on_locked_seam_session"] == 0,
            "coverage_class_accounting_exact": sum(coverage_counts.values()) == len(symbols),
            "reference_accounting_exact": reference_unique + reference_absent + reference_ambiguous == len(symbols),
            "all_discontinuities_reset_continuity": all(row["promotion_policy"] == SEAM_RESET_POLICY for row in rows),
            "canonical_data_untouched": report["canonical_data_modified"] is False,
        }
        report["structural_checks"] = checks
        report["structural_pass"] = all(checks.values())
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        return report
