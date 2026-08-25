from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .phase25_gate0 import PHASE25_GATE0_REPORT_CONTRACT_VERSION, Phase25Gate0Inventory
from .phase25_policy import (
    PHASE25_BROKER_READS,
    PHASE25_BROKER_WRITES,
    PHASE25_EXACT_PIT_REFERENCE_REQUIRED_FOR_AUTHORITATIVE_PHASE7_REPLAY,
    PHASE25_FUTURE_REFERENCE_METADATA_AUTHORITY_ALLOWED,
    PHASE25_GATE1_CONTRACT_VERSION,
    PHASE25_LIVE_WRITES,
    PHASE25_ORDER_WRITES,
    PHASE25_PAPER_SUBMITS,
    PHASE25_PHASE11_SUPPORT_WRITES,
    PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
    PHASE25_PROVIDER_READS,
    PHASE25_PROVIDER_WRITES,
    PHASE25_PROXY_UNIVERSE_SUPPORT_AUTHORITY_ALLOWED,
    PHASE25_ROUTE_REPLAY_ORIGIN,
    phase25_gate0_policy_fingerprint,
    phase25_gate1_policy_fingerprint,
)


PHASE25_GATE1_REPORT_CONTRACT_VERSION = (
    "phase25-gate1-report-v1-provider-native-first-seen-reference-identity-scope"
)


class Phase25Gate1Error(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate1Error(f"missing required JSON evidence: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate1Error(f"invalid JSON evidence: {path}") from exc
    if not isinstance(value, dict):
        raise Phase25Gate1Error(f"JSON evidence must be an object: {path}")
    return value


@dataclass(frozen=True, slots=True)
class SymbolEvidence:
    symbol: str
    first_seen: str
    last_seen: str
    session_count: int
    reference_observation_count: int
    reference_instrument_count: int
    exact_first_seen_reference_count: int
    exact_first_seen_classifiable_count: int
    prior_or_same_reference_count: int
    future_reference_count: int
    metadata_variant_count: int
    authoritative_interval_instrument_count: int
    ticker_observation_instrument_count: int
    category: str
    authoritative_interval_covers_first_seen: bool
    bounded_invariant_metadata_proxy_candidate: bool


def classify_symbol_evidence(
    *,
    reference_observation_count: int,
    reference_instrument_count: int,
    exact_first_seen_reference_count: int,
    exact_first_seen_classifiable_count: int,
    prior_or_same_reference_count: int,
    future_reference_count: int,
    metadata_variant_count: int,
    authoritative_interval_instrument_count: int,
) -> tuple[str, bool, bool]:
    """Classify local PIT evidence without granting any replay/support authority.

    The bounded-invariant flag is deliberately a *proxy-candidate* diagnostic only.
    It means local observations bracket the first-seen date and agree on the static
    classification fields. It is not proof that no unobserved metadata change occurred.
    """

    ambiguous = reference_instrument_count > 1 or authoritative_interval_instrument_count > 1
    interval_covers = authoritative_interval_instrument_count == 1
    if ambiguous:
        category = "AMBIGUOUS_LOCAL_IDENTITY"
    elif exact_first_seen_reference_count > 0 and exact_first_seen_classifiable_count > 0:
        category = "EXACT_FIRST_SEEN_REFERENCE"
    elif prior_or_same_reference_count > 0:
        category = "PRIOR_REFERENCE_ONLY"
    elif reference_observation_count > 0 and future_reference_count > 0:
        category = "FUTURE_ONLY_REFERENCE"
    else:
        category = "NO_LOCAL_REFERENCE"

    bracketed_invariant = bool(
        not ambiguous
        and prior_or_same_reference_count > 0
        and future_reference_count > 0
        and metadata_variant_count == 1
        and reference_instrument_count == 1
    )
    return category, interval_covers, bracketed_invariant


class Phase25Gate1ScopeInventory:
    """Provider-free symbol/identity scope proof after Gate0.

    Gate1 does not fetch missing reference evidence and does not compute strategy
    outcomes. It measures how much of the canonical replay population is anchored by
    exact/prior/future local reference observations and authoritative ticker intervals.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate1"

    def report_path(self, through_date: date) -> Path:
        return self.root / f"through={through_date}" / "reference_scope_inventory.json"

    def _gate0_evidence(self, through_date: date) -> tuple[Path, dict[str, object]]:
        path = Phase25Gate0Inventory(self.settings).report_path(through_date)
        report = _read_json(path)
        if report.get("contract_version") != PHASE25_GATE0_REPORT_CONTRACT_VERSION:
            raise Phase25Gate1Error("Gate0 report contract mismatch")
        if report.get("through_date") != through_date.isoformat():
            raise Phase25Gate1Error("Gate0 report through-date mismatch")
        if report.get("phase25_gate0_policy_fingerprint") != phase25_gate0_policy_fingerprint():
            raise Phase25Gate1Error("Gate0 policy fingerprint mismatch")
        if report.get("pass") is not True:
            raise Phase25Gate1Error("Gate0 evidence is not passing")
        for key in (
            "provider_reads",
            "provider_writes",
            "broker_reads",
            "broker_writes",
            "order_writes",
            "paper_submits",
            "live_writes",
            "phase11_support_writes",
            "protected_strategy_evidence_reads",
        ):
            if int(report.get(key, -1)) != 0:
                raise Phase25Gate1Error(f"Gate0 authority counter is nonzero: {key}")
        return path, report

    def _reference_snapshot_dates(self, through_date: date) -> tuple[date, ...]:
        root = (
            self.settings.resolved_path(self.settings.data.paths.canonical)
            / "reference"
            / "massive"
            / "tickers"
        )
        result: list[date] = []
        for path in sorted(root.glob("date=*")) if root.exists() else []:
            text = path.name.removeprefix("date=")
            try:
                value = date.fromisoformat(text)
            except ValueError:
                continue
            if PHASE25_ROUTE_REPLAY_ORIGIN <= value <= through_date and (path / "part-000.parquet").is_file():
                result.append(value)
        return tuple(result)

    def _reference_lineage(self, dates: tuple[date, ...]) -> str:
        entries: list[str] = []
        for session in dates:
            snapshot = self.paths.reference_snapshot_file(session)
            manifest = self.paths.reference_snapshot_manifest(session)
            if not manifest.is_file():
                raise Phase25Gate1Error(f"reference manifest missing for local snapshot {session}")
            entries.append(
                ":".join(
                    (
                        session.isoformat(),
                        sha256_file(snapshot),
                        sha256_file(manifest),
                    )
                )
            )
        return hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()

    def _symbol_rows(self, through_date: date) -> tuple[list[dict[str, Any]], int, tuple[date, ...]]:
        reference_dates = self._reference_snapshot_dates(through_date)
        if not reference_dates:
            raise Phase25Gate1Error("Gate1 requires at least one local reference snapshot in replay scope")

        intervals = self.paths.authoritative_ticker_intervals_file()
        observations = self.paths.ticker_observations_file()
        if not intervals.is_file() or not observations.is_file():
            raise Phase25Gate1Error("Gate1 requires accepted ticker observation and authoritative interval views")

        con = connect_utc(":memory:")
        try:
            con.execute(
                f"""
                CREATE TEMP TABLE phase25_bars AS
                SELECT symbol, CAST(session_date AS DATE) AS session_date
                FROM read_parquet({sql_string(self.paths.glob_for_timeframe(Timeframe.DAY_1))}, union_by_name=true, hive_partitioning=false)
                WHERE CAST(session_date AS DATE) BETWEEN ? AND ?
                """,
                [PHASE25_ROUTE_REPLAY_ORIGIN, through_date],
            )
            total_symbol_sessions = int(
                con.execute(
                    "SELECT count(*) FROM (SELECT DISTINCT symbol, session_date FROM phase25_bars)"
                ).fetchone()[0]
            )
            con.execute(
                f"""
                CREATE TEMP TABLE phase25_refs AS
                SELECT
                    instrument_id,
                    ticker,
                    identity_quality,
                    CAST(as_of_date AS DATE) AS as_of_date,
                    market,
                    locale,
                    primary_exchange,
                    security_type,
                    active,
                    delisted_utc
                FROM read_parquet({sql_string(self.paths.reference_snapshot_glob())}, union_by_name=true, hive_partitioning=false)
                WHERE CAST(as_of_date AS DATE) BETWEEN ? AND ?
                """,
                [PHASE25_ROUTE_REPLAY_ORIGIN, through_date],
            )
            con.execute(
                f"""
                CREATE TEMP TABLE phase25_intervals AS
                SELECT instrument_id, ticker, CAST(valid_from_date AS DATE) AS valid_from_date,
                       CAST(valid_to_date_exclusive AS DATE) AS valid_to_date_exclusive
                FROM read_parquet({sql_string(intervals)})
                WHERE continuity_authority = true
                """
            )
            con.execute(
                f"""
                CREATE TEMP TABLE phase25_observations AS
                SELECT instrument_id, ticker
                FROM read_parquet({sql_string(observations)})
                """
            )

            cursor = con.execute(
                """
                WITH bars AS (
                    SELECT symbol,
                           min(session_date) AS first_seen,
                           max(session_date) AS last_seen,
                           count(DISTINCT session_date) AS session_count
                    FROM phase25_bars
                    GROUP BY symbol
                ), ref_stats AS (
                    SELECT
                        b.symbol,
                        b.first_seen,
                        count(r.ticker) AS reference_observation_count,
                        count(DISTINCT r.instrument_id) AS reference_instrument_count,
                        count(*) FILTER (WHERE r.as_of_date = b.first_seen) AS exact_first_seen_reference_count,
                        count(*) FILTER (
                            WHERE r.as_of_date = b.first_seen
                              AND r.identity_quality IN ('strong', 'medium')
                              AND r.market IS NOT NULL
                              AND r.locale IS NOT NULL
                              AND r.primary_exchange IS NOT NULL
                              AND r.security_type IS NOT NULL
                              AND r.active IS NOT NULL
                        ) AS exact_first_seen_classifiable_count,
                        count(*) FILTER (WHERE r.as_of_date <= b.first_seen) AS prior_or_same_reference_count,
                        count(*) FILTER (WHERE r.as_of_date > b.first_seen) AS future_reference_count,
                        count(DISTINCT concat_ws('|',
                            coalesce(lower(trim(CAST(r.market AS VARCHAR))), '<null>'),
                            coalesce(lower(trim(CAST(r.locale AS VARCHAR))), '<null>'),
                            coalesce(upper(trim(CAST(r.primary_exchange AS VARCHAR))), '<null>'),
                            coalesce(upper(trim(CAST(r.security_type AS VARCHAR))), '<null>')
                        )) FILTER (WHERE r.ticker IS NOT NULL) AS metadata_variant_count
                    FROM bars b
                    LEFT JOIN phase25_refs r ON r.ticker = b.symbol
                    GROUP BY b.symbol, b.first_seen
                ), interval_stats AS (
                    SELECT
                        b.symbol,
                        count(DISTINCT i.instrument_id) AS authoritative_interval_instrument_count
                    FROM bars b
                    LEFT JOIN phase25_intervals i
                      ON i.ticker = b.symbol
                     AND b.first_seen >= i.valid_from_date
                     AND (i.valid_to_date_exclusive IS NULL OR b.first_seen < i.valid_to_date_exclusive)
                    GROUP BY b.symbol
                ), observation_stats AS (
                    SELECT b.symbol,
                           count(DISTINCT o.instrument_id) AS ticker_observation_instrument_count
                    FROM bars b
                    LEFT JOIN phase25_observations o ON o.ticker = b.symbol
                    GROUP BY b.symbol
                )
                SELECT
                    b.symbol,
                    b.first_seen,
                    b.last_seen,
                    b.session_count,
                    rs.reference_observation_count,
                    rs.reference_instrument_count,
                    rs.exact_first_seen_reference_count,
                    rs.exact_first_seen_classifiable_count,
                    rs.prior_or_same_reference_count,
                    rs.future_reference_count,
                    rs.metadata_variant_count,
                    isx.authoritative_interval_instrument_count,
                    os.ticker_observation_instrument_count
                FROM bars b
                JOIN ref_stats rs USING (symbol, first_seen)
                JOIN interval_stats isx USING (symbol)
                JOIN observation_stats os USING (symbol)
                ORDER BY b.first_seen, b.symbol
                """
            )
            columns = [item[0] for item in cursor.description]
            rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        finally:
            con.close()
        return rows, total_symbol_sessions, reference_dates

    def run(self, *, through_date: date) -> dict[str, object]:
        if through_date < PHASE25_ROUTE_REPLAY_ORIGIN:
            raise Phase25Gate1Error("through_date predates the locked Phase25 replay origin")
        if not self.calendar.is_session(through_date):
            raise Phase25Gate1Error(f"through_date is not an exchange session: {through_date}")

        gate0_path, gate0 = self._gate0_evidence(through_date)
        rows, total_symbol_sessions, reference_dates = self._symbol_rows(through_date)
        if not rows:
            raise Phase25Gate1Error("canonical replay population produced no symbols")

        evidence: list[SymbolEvidence] = []
        category_counts: Counter[str] = Counter()
        category_symbol_sessions: Counter[str] = Counter()
        gap_first_seen: Counter[str] = Counter()
        interval_covered = 0
        bracketed_proxy = 0
        exact_anchor = 0
        ambiguous = 0
        future_only = 0
        no_reference = 0
        prior_only = 0
        observed_identity_unique = 0

        for row in rows:
            category, interval_covers, bracketed = classify_symbol_evidence(
                reference_observation_count=int(row["reference_observation_count"]),
                reference_instrument_count=int(row["reference_instrument_count"]),
                exact_first_seen_reference_count=int(row["exact_first_seen_reference_count"]),
                exact_first_seen_classifiable_count=int(row["exact_first_seen_classifiable_count"]),
                prior_or_same_reference_count=int(row["prior_or_same_reference_count"]),
                future_reference_count=int(row["future_reference_count"]),
                metadata_variant_count=int(row["metadata_variant_count"]),
                authoritative_interval_instrument_count=int(row["authoritative_interval_instrument_count"]),
            )
            item = SymbolEvidence(
                symbol=str(row["symbol"]),
                first_seen=row["first_seen"].isoformat(),
                last_seen=row["last_seen"].isoformat(),
                session_count=int(row["session_count"]),
                reference_observation_count=int(row["reference_observation_count"]),
                reference_instrument_count=int(row["reference_instrument_count"]),
                exact_first_seen_reference_count=int(row["exact_first_seen_reference_count"]),
                exact_first_seen_classifiable_count=int(row["exact_first_seen_classifiable_count"]),
                prior_or_same_reference_count=int(row["prior_or_same_reference_count"]),
                future_reference_count=int(row["future_reference_count"]),
                metadata_variant_count=int(row["metadata_variant_count"]),
                authoritative_interval_instrument_count=int(row["authoritative_interval_instrument_count"]),
                ticker_observation_instrument_count=int(row["ticker_observation_instrument_count"]),
                category=category,
                authoritative_interval_covers_first_seen=interval_covers,
                bounded_invariant_metadata_proxy_candidate=bracketed,
            )
            evidence.append(item)
            category_counts[category] += 1
            category_symbol_sessions[category] += item.session_count
            interval_covered += int(interval_covers)
            bracketed_proxy += int(bracketed)
            observed_identity_unique += int(item.ticker_observation_instrument_count == 1)
            if category == "EXACT_FIRST_SEEN_REFERENCE":
                exact_anchor += 1
            else:
                gap_first_seen[item.first_seen] += 1
            ambiguous += int(category == "AMBIGUOUS_LOCAL_IDENTITY")
            future_only += int(category == "FUTURE_ONLY_REFERENCE")
            no_reference += int(category == "NO_LOCAL_REFERENCE")
            prior_only += int(category == "PRIOR_REFERENCE_ONLY")

        symbol_count = len(evidence)
        gap_symbols = symbol_count - exact_anchor
        gap_dates = len(gap_first_seen)
        top_gap_dates = [
            {"date": day, "symbols_without_exact_first_seen_reference": count}
            for day, count in sorted(
                gap_first_seen.items(), key=lambda item: (-item[1], item[0])
            )[:25]
        ]
        previews: dict[str, list[dict[str, object]]] = {}
        for category in sorted(category_counts):
            previews[category] = [
                {
                    "symbol": item.symbol,
                    "first_seen": item.first_seen,
                    "last_seen": item.last_seen,
                    "session_count": item.session_count,
                    "reference_observation_count": item.reference_observation_count,
                    "reference_instrument_count": item.reference_instrument_count,
                    "authoritative_interval_covers_first_seen": item.authoritative_interval_covers_first_seen,
                }
                for item in evidence
                if item.category == category
            ][:20]

        reference_lineage = self._reference_lineage(reference_dates)
        identity_lineage = {
            "ticker_observations_sha256": sha256_file(self.paths.ticker_observations_file()),
            "authoritative_ticker_intervals_sha256": sha256_file(
                self.paths.authoritative_ticker_intervals_file()
            ),
            "instrument_registry_sha256": sha256_file(self.paths.instrument_registry_file()),
        }
        source_fingerprint = _stable_hash(
            {
                "gate0_report_sha256": sha256_file(gate0_path),
                "reference_lineage_sha256": reference_lineage,
                "identity_lineage": identity_lineage,
                "through_date": through_date.isoformat(),
                "replay_origin": PHASE25_ROUTE_REPLAY_ORIGIN.isoformat(),
                "symbol_count": symbol_count,
                "total_symbol_sessions": total_symbol_sessions,
            }
        )

        recommendation = (
            "GATE2_EXACT_REFERENCE_SCOPE_COMPLETE"
            if gap_symbols == 0 and ambiguous == 0
            else "GATE2_PREREGISTER_EXACT_REFERENCE_ACQUISITION_OR_NONAUTHORITATIVE_PROXY_VALIDATION"
        )
        report_path = self.report_path(through_date)
        report: dict[str, object] = {
            "contract_version": PHASE25_GATE1_REPORT_CONTRACT_VERSION,
            "gate1_policy_contract_version": PHASE25_GATE1_CONTRACT_VERSION,
            "phase25_gate1_policy_fingerprint": phase25_gate1_policy_fingerprint(),
            "phase25_gate0_policy_fingerprint": phase25_gate0_policy_fingerprint(),
            "gate0_report_contract_version": PHASE25_GATE0_REPORT_CONTRACT_VERSION,
            "gate0_report_path": str(gate0_path.resolve()),
            "gate0_report_sha256": sha256_file(gate0_path),
            "replay_origin": PHASE25_ROUTE_REPLAY_ORIGIN.isoformat(),
            "through_date": through_date.isoformat(),
            "replay_session_count": int(gate0["replay_session_count"]),
            "canonical_distinct_symbol_count": symbol_count,
            "canonical_symbol_session_count": total_symbol_sessions,
            "local_reference_snapshot_dates": [item.isoformat() for item in reference_dates],
            "local_reference_snapshot_count": len(reference_dates),
            "reference_lineage_sha256": reference_lineage,
            "identity_lineage": identity_lineage,
            "source_fingerprint": source_fingerprint,
            "category_symbol_counts": dict(sorted(category_counts.items())),
            "category_symbol_session_counts": dict(sorted(category_symbol_sessions.items())),
            "exact_first_seen_reference_symbols": exact_anchor,
            "symbols_without_exact_first_seen_reference": gap_symbols,
            "distinct_gap_first_seen_dates": gap_dates,
            "prior_reference_only_symbols": prior_only,
            "future_only_reference_symbols": future_only,
            "no_local_reference_symbols": no_reference,
            "ambiguous_local_identity_symbols": ambiguous,
            "authoritative_interval_covers_first_seen_symbols": interval_covered,
            "unique_ticker_observation_identity_symbols": observed_identity_unique,
            "bounded_invariant_metadata_proxy_candidate_symbols": bracketed_proxy,
            "bounded_invariant_metadata_proxy_authority": False,
            "future_reference_metadata_authority_allowed": PHASE25_FUTURE_REFERENCE_METADATA_AUTHORITY_ALLOWED,
            "proxy_universe_support_authority_allowed": PHASE25_PROXY_UNIVERSE_SUPPORT_AUTHORITY_ALLOWED,
            "exact_pit_reference_required_for_authoritative_phase7_replay": (
                PHASE25_EXACT_PIT_REFERENCE_REQUIRED_FOR_AUTHORITATIVE_PHASE7_REPLAY
            ),
            "top_gap_first_seen_dates": top_gap_dates,
            "category_previews": previews,
            "recommendation": recommendation,
            "protected_strategy_evidence_reads": PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
            "provider_reads": PHASE25_PROVIDER_READS,
            "provider_writes": PHASE25_PROVIDER_WRITES,
            "broker_reads": PHASE25_BROKER_READS,
            "broker_writes": PHASE25_BROKER_WRITES,
            "order_writes": PHASE25_ORDER_WRITES,
            "paper_submits": PHASE25_PAPER_SUBMITS,
            "live_writes": PHASE25_LIVE_WRITES,
            "phase11_support_writes": PHASE25_PHASE11_SUPPORT_WRITES,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        report["report_fingerprint"] = _stable_hash(
            {
                key: value
                for key, value in report.items()
                if key not in {"generated_at_utc", "report_path", "report_fingerprint"}
            }
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
