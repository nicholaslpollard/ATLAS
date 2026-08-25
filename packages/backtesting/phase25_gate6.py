from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.discovery.persistence import ACTIVE_DISCOVERY_PERSISTENCE_POLICY
from packages.discovery.scanner import DiscoveryFoundationScanner
from packages.discovery.scoring import DiscoverySetupScanner
from packages.features.partition_store import sha256_file
from packages.schemas.discovery_score import DiscoveryDirection, DiscoveryState
from packages.universe.manager import UniverseManager

from .phase25_gate5 import PHASE25_GATE5_REPORT_CONTRACT_VERSION, Phase25Gate5BulkAcquisition
from .phase25_gate5_policy import phase25_gate5_policy_fingerprint
from .phase25_gate5_validation import (
    PHASE25_GATE5_VALIDATION_CONTRACT_VERSION,
    Phase25Gate5IndependentValidator,
)
from .phase25_gate6_policy import (
    PHASE25_GATE6_CONTRACT_VERSION,
    PHASE25_GATE6_DISCOVERY_OVERRIDES_ALLOWED,
    PHASE25_GATE6_OPERATIONAL_DISCOVERY_STATE_WRITES_ALLOWED,
    PHASE25_GATE6_OVERWRITE_EXISTING_ARTIFACTS_ALLOWED,
    PHASE25_GATE6_PROVIDER_READS,
    PHASE25_GATE6_PROVIDER_WRITES,
    PHASE25_GATE6_REGIME_ROUTING_ALLOWED,
    PHASE25_GATE6_STRATEGY_RETURNS_READ_ALLOWED,
    PHASE25_GATE6_STRATEGY_RULE_EVALUATION_ALLOWED,
    PHASE25_GATE6_SUPPORT_REPLACEMENT_ALLOWED,
    phase25_gate6_policy_fingerprint,
)
from .phase25_policy import (
    PHASE25_BROKER_READS,
    PHASE25_BROKER_WRITES,
    PHASE25_LIVE_WRITES,
    PHASE25_ORDER_WRITES,
    PHASE25_PAPER_SUBMITS,
    PHASE25_PHASE11_SUPPORT_WRITES,
    PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
    PHASE25_ROUTE_REPLAY_ORIGIN,
)


PHASE25_GATE6_REPORT_CONTRACT_VERSION = (
    "phase25-gate6-report-v1-phase7-discovery-chronological-reconstruction"
)
PHASE25_GATE6_SESSION_SUMMARY_CONTRACT_VERSION = (
    "phase25-gate6-session-summary-v1-discovery-funnel"
)
PHASE25_GATE6_POPULATION_CONTRACT_VERSION = (
    "phase25-gate6-population-v1-warm-hot-directional"
)


class Phase25Gate6Error(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate6Error(f"missing required JSON evidence: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate6Error(f"invalid JSON evidence: {path}") from exc
    if not isinstance(value, dict):
        raise Phase25Gate6Error(f"JSON evidence must be an object: {path}")
    return value


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _pair_state(paths: tuple[Path, ...], *, label: str, session: date) -> bool:
    present = [path.is_file() for path in paths]
    if any(present) and not all(present):
        missing = [str(path) for path, exists in zip(paths, present, strict=True) if not exists]
        raise Phase25Gate6Error(
            f"unreconciled partial {label} artifact set for {session}: " + ", ".join(missing)
        )
    return all(present)


class Phase25Gate6DiscoveryReconstruction:
    """Provider-free Phase7/discovery reconstruction with research-only state replay."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = get_market_calendar()
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate6"

    def run_root(self, through_date: date) -> Path:
        return self.root / f"through={through_date}"

    def report_path(self, through_date: date) -> Path:
        return self.run_root(through_date) / "reconstruction_report.json"

    def session_summary_path(self, through_date: date) -> Path:
        return self.run_root(through_date) / "session_summary.parquet"

    def population_path(self, through_date: date) -> Path:
        return self.run_root(through_date) / "warm_hot_directional_population.parquet"

    def _gate5_evidence(self, through_date: date) -> tuple[Path, dict[str, object], Path, dict[str, object]]:
        report_path = Phase25Gate5BulkAcquisition(self.settings).report_path(through_date)
        report = _read_json(report_path)
        if report.get("contract_version") != PHASE25_GATE5_REPORT_CONTRACT_VERSION:
            raise Phase25Gate6Error("Gate5 report contract mismatch")
        if report.get("phase25_gate5_policy_fingerprint") != phase25_gate5_policy_fingerprint():
            raise Phase25Gate6Error("Gate5 policy fingerprint mismatch")
        if report.get("through_date") != through_date.isoformat() or report.get("pass") is not True:
            raise Phase25Gate6Error("Gate5 report is not accepted for the requested through-date")
        if int(report.get("remaining_frozen_bulk_sessions", -1)) != 0:
            raise Phase25Gate6Error("Gate5 reference lineage is incomplete")
        if int(report.get("probe_refetch_sessions", -1)) != 0:
            raise Phase25Gate6Error("Gate5 unexpectedly re-fetched the entitlement probe")

        validation_path = Phase25Gate5IndependentValidator(self.settings).report_path(through_date)
        validation = _read_json(validation_path)
        if validation.get("contract_version") != PHASE25_GATE5_VALIDATION_CONTRACT_VERSION:
            raise Phase25Gate6Error("Gate5 independent-validation contract mismatch")
        if validation.get("pass") is not True:
            raise Phase25Gate6Error("Gate5 independent validation is not passing")
        return report_path, report, validation_path, validation

    def _sessions(self, through_date: date) -> tuple[date, ...]:
        if through_date < PHASE25_ROUTE_REPLAY_ORIGIN:
            raise Phase25Gate6Error("through-date predates the accepted route-replay origin")
        if not self.calendar.is_session(through_date):
            raise Phase25Gate6Error(f"through-date is not an XNYS session: {through_date}")
        sessions = tuple(self.calendar.sessions_in_range(PHASE25_ROUTE_REPLAY_ORIGIN, through_date))
        if not sessions or sessions[0] != PHASE25_ROUTE_REPLAY_ORIGIN or sessions[-1] != through_date:
            raise Phase25Gate6Error("exchange-session reconstruction scope mismatch")
        return sessions

    def _assert_reference_pair(self, session: date) -> None:
        snapshot = self.paths.reference_snapshot_file(session)
        manifest_path = self.paths.reference_snapshot_manifest(session)
        if not _pair_state((snapshot, manifest_path), label="reference", session=session):
            raise Phase25Gate6Error(f"exact PIT reference pair is missing for {session}")
        manifest = _read_json(manifest_path)
        if manifest.get("as_of_date") != session.isoformat():
            raise Phase25Gate6Error(f"reference manifest date mismatch for {session}")
        if int(manifest.get("row_count", 0)) <= 0 or int(manifest.get("instrument_count", 0)) <= 0:
            raise Phase25Gate6Error(f"reference pair has nonpositive counts for {session}")

    def _materialize_stateless_session(self, session: date) -> dict[str, object]:
        self._assert_reference_pair(session)

        universe_paths = (
            self.paths.universe_snapshot_file(session),
            self.paths.universe_exclusion_file(session),
            self.paths.universe_snapshot_manifest(session),
        )
        universe_existing = _pair_state(universe_paths, label="Phase7 universe", session=session)
        universe = UniverseManager(self.settings).build(session, force=False)
        if universe_existing and not universe.skipped:
            raise Phase25Gate6Error(
                f"existing Phase7 universe would require overwrite for {session}; Gate6 refuses"
            )
        if not universe_existing and universe.skipped:
            raise Phase25Gate6Error(f"new Phase7 universe unexpectedly reported skipped for {session}")

        foundation_paths = (
            self.paths.discovery_snapshot_file(session),
            self.paths.discovery_snapshot_manifest(session),
        )
        foundation_existing = _pair_state(
            foundation_paths, label="discovery foundation", session=session
        )
        foundation = DiscoveryFoundationScanner(self.settings).build(session)
        if foundation_existing and not foundation.skipped:
            raise Phase25Gate6Error(
                f"existing discovery foundation would require overwrite for {session}; Gate6 refuses"
            )
        if not foundation_existing and foundation.skipped:
            raise Phase25Gate6Error(
                f"new discovery foundation unexpectedly reported skipped for {session}"
            )

        score_paths = (
            self.paths.discovery_score_file(session),
            self.paths.discovery_score_manifest(session),
        )
        score_existing = _pair_state(score_paths, label="discovery score", session=session)
        score = DiscoverySetupScanner(self.settings).build(session)
        if score_existing and not score.skipped:
            raise Phase25Gate6Error(
                f"existing discovery score would require overwrite for {session}; Gate6 refuses"
            )
        if not score_existing and score.skipped:
            raise Phase25Gate6Error(f"new discovery score unexpectedly reported skipped for {session}")

        return {
            "universe_existing": universe_existing,
            "foundation_existing": foundation_existing,
            "score_existing": score_existing,
            "universe_routed": universe.routed_instrument_count,
            "universe_discovery": universe.discovery_count,
            "foundation_broad_ready": foundation.broad_discovery_ready_count,
            "foundation_consideration": foundation.consideration_required_count,
            "scored": score.scored_count,
            "universe_sha256": sha256_file(self.paths.universe_snapshot_file(session)),
            "foundation_sha256": sha256_file(self.paths.discovery_snapshot_file(session)),
            "score_sha256": sha256_file(self.paths.discovery_score_file(session)),
        }

    def _score_frame(self, session: date) -> pd.DataFrame:
        path = self.paths.discovery_score_file(session)
        con = connect_utc(":memory:")
        try:
            return con.execute(
                f"""
                SELECT instrument_id, ticker, raw_state, scored_timeframes,
                       priority_score, bull_evidence, bear_evidence, direction, top_setup
                FROM read_parquet({sql_string(path)})
                ORDER BY instrument_id
                """
            ).fetch_df()
        finally:
            con.close()

    def _write_parquet(self, frame: pd.DataFrame, target: Path, *, order_by: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(target)
        temp.unlink(missing_ok=True)
        con = connect_utc(":memory:")
        try:
            con.register("phase25_gate6_frame", frame)
            compression = self.settings.data.parquet.compression.upper()
            row_group_size = int(self.settings.data.parquet.row_group_size)
            con.execute(
                f"COPY (SELECT * FROM phase25_gate6_frame ORDER BY {order_by}) "
                f"TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION {compression}, "
                f"ROW_GROUP_SIZE {row_group_size})"
            )
            promote(temp, target)
        finally:
            con.close()

    def run(
        self,
        *,
        through_date: date,
        progress_callback: Callable[..., None] | None = None,
    ) -> dict[str, object]:
        if PHASE25_GATE6_PROVIDER_READS != 0 or PHASE25_GATE6_PROVIDER_WRITES != 0:
            raise Phase25Gate6Error("Gate6 must remain provider-free")
        if PHASE25_GATE6_OVERWRITE_EXISTING_ARTIFACTS_ALLOWED:
            raise Phase25Gate6Error("Gate6 overwrite authority must remain disabled")
        if PHASE25_GATE6_OPERATIONAL_DISCOVERY_STATE_WRITES_ALLOWED:
            raise Phase25Gate6Error("Gate6 may not write operational discovery state")

        gate5_path, gate5, gate5_validation_path, _ = self._gate5_evidence(through_date)
        sessions = self._sessions(through_date)
        previous_map: dict[str, dict[str, object]] = {}
        summaries: list[dict[str, object]] = []
        population: list[dict[str, object]] = []
        overall_effective: Counter[str] = Counter()
        overall_directional: Counter[str] = Counter()
        existing_counts: Counter[str] = Counter()
        new_counts: Counter[str] = Counter()
        lineage_entries: list[str] = []

        for index, session in enumerate(sessions, start=1):
            materialized = self._materialize_stateless_session(session)
            for key, label in (
                ("universe_existing", "universe"),
                ("foundation_existing", "foundation"),
                ("score_existing", "score"),
            ):
                (existing_counts if bool(materialized[key]) else new_counts).update([label])

            score = self._score_frame(session)
            current_map: dict[str, dict[str, object]] = {}
            state_counts: Counter[str] = Counter()
            directional_counts: Counter[str] = Counter()
            warm_hot_directional = 0

            for row in score.itertuples(index=False):
                instrument_id = str(row.instrument_id)
                raw_state = DiscoveryState(str(row.raw_state))
                scored_timeframes = int(row.scored_timeframes)
                prior = previous_map.get(instrument_id)
                if prior is None:
                    effective, warm_streak, demotion_streak, transition = (
                        ACTIVE_DISCOVERY_PERSISTENCE_POLICY.bootstrap(
                            raw_state=raw_state,
                            scored_timeframes=scored_timeframes,
                        )
                    )
                else:
                    effective, warm_streak, demotion_streak, transition = (
                        ACTIVE_DISCOVERY_PERSISTENCE_POLICY.transition(
                            previous_effective_state=str(prior["effective_state"]),
                            previous_warm_confirmation_streak=int(prior["warm_streak"]),
                            previous_demotion_streak=int(prior["demotion_streak"]),
                            raw_state=raw_state,
                            scored_timeframes=scored_timeframes,
                        )
                    )
                current_map[instrument_id] = {
                    "effective_state": effective.value,
                    "warm_streak": warm_streak,
                    "demotion_streak": demotion_streak,
                }
                state_counts.update([effective.value])
                overall_effective.update([effective.value])

                direction = DiscoveryDirection(str(row.direction))
                if effective in {DiscoveryState.WARM, DiscoveryState.HOT}:
                    directional_counts.update([direction.value])
                    overall_directional.update([direction.value])
                    if direction in {DiscoveryDirection.BULLISH, DiscoveryDirection.BEARISH}:
                        warm_hot_directional += 1
                        population.append(
                            {
                                "contract_version": PHASE25_GATE6_POPULATION_CONTRACT_VERSION,
                                "as_of_date": session,
                                "instrument_id": instrument_id,
                                "ticker": str(row.ticker),
                                "raw_state": raw_state.value,
                                "effective_state": effective.value,
                                "direction": direction.value,
                                "top_setup": str(row.top_setup),
                                "scored_timeframes": scored_timeframes,
                                "priority_score": float(row.priority_score),
                                "bull_evidence": float(row.bull_evidence),
                                "bear_evidence": float(row.bear_evidence),
                                "transition": transition,
                            }
                        )

            previous_map = current_map
            summary = {
                "contract_version": PHASE25_GATE6_SESSION_SUMMARY_CONTRACT_VERSION,
                "as_of_date": session,
                "universe_routed": int(materialized["universe_routed"]),
                "universe_discovery": int(materialized["universe_discovery"]),
                "foundation_broad_ready": int(materialized["foundation_broad_ready"]),
                "foundation_consideration": int(materialized["foundation_consideration"]),
                "scored": int(materialized["scored"]),
                "effective_normal": int(state_counts.get("normal", 0)),
                "effective_watch": int(state_counts.get("watch", 0)),
                "effective_warm": int(state_counts.get("warm", 0)),
                "effective_hot": int(state_counts.get("hot", 0)),
                "warm_hot_bullish": int(directional_counts.get("bullish", 0)),
                "warm_hot_bearish": int(directional_counts.get("bearish", 0)),
                "warm_hot_neutral": int(directional_counts.get("neutral", 0)),
                "warm_hot_directional": warm_hot_directional,
            }
            summaries.append(summary)
            lineage_entries.append(
                ":".join(
                    (
                        session.isoformat(),
                        str(materialized["universe_sha256"]),
                        str(materialized["foundation_sha256"]),
                        str(materialized["score_sha256"]),
                    )
                )
            )
            if progress_callback is not None:
                progress_callback(index=index, total=len(sessions), session=session, summary=summary)

        summary_frame = pd.DataFrame.from_records(summaries)
        population_columns = (
            "contract_version",
            "as_of_date",
            "instrument_id",
            "ticker",
            "raw_state",
            "effective_state",
            "direction",
            "top_setup",
            "scored_timeframes",
            "priority_score",
            "bull_evidence",
            "bear_evidence",
            "transition",
        )
        population_frame = pd.DataFrame.from_records(population, columns=population_columns)
        summary_path = self.session_summary_path(through_date)
        population_path = self.population_path(through_date)
        self._write_parquet(summary_frame, summary_path, order_by="as_of_date")
        self._write_parquet(
            population_frame,
            population_path,
            order_by="as_of_date, instrument_id",
        )

        lineage_sha = hashlib.sha256("\n".join(lineage_entries).encode("utf-8")).hexdigest()
        report_path = self.report_path(through_date)
        report: dict[str, object] = {
            "contract_version": PHASE25_GATE6_REPORT_CONTRACT_VERSION,
            "gate6_policy_contract_version": PHASE25_GATE6_CONTRACT_VERSION,
            "phase25_gate6_policy_fingerprint": phase25_gate6_policy_fingerprint(),
            "phase25_gate5_policy_fingerprint": phase25_gate5_policy_fingerprint(),
            "through_date": through_date.isoformat(),
            "replay_origin": PHASE25_ROUTE_REPLAY_ORIGIN.isoformat(),
            "replay_session_count": len(sessions),
            "gate5_report_path": str(gate5_path.resolve()),
            "gate5_report_sha256": sha256_file(gate5_path),
            "gate5_validation_path": str(gate5_validation_path.resolve()),
            "gate5_validation_sha256": sha256_file(gate5_validation_path),
            "gate5_provider_page_reads": int(gate5.get("successful_provider_page_reads_this_run", 0)),
            "stateless_lineage_sha256": lineage_sha,
            "existing_artifact_counts": dict(sorted(existing_counts.items())),
            "newly_materialized_artifact_counts": dict(sorted(new_counts.items())),
            "effective_state_row_counts": dict(sorted(overall_effective.items())),
            "warm_hot_direction_counts": dict(sorted(overall_directional.items())),
            "warm_hot_directional_population_rows": len(population_frame),
            "session_summary_path": str(summary_path.resolve()),
            "session_summary_sha256": sha256_file(summary_path),
            "population_path": str(population_path.resolve()),
            "population_sha256": sha256_file(population_path),
            "operational_discovery_state_writes": 0,
            "provider_reads": PHASE25_GATE6_PROVIDER_READS,
            "provider_writes": PHASE25_GATE6_PROVIDER_WRITES,
            "broker_reads": PHASE25_BROKER_READS,
            "broker_writes": PHASE25_BROKER_WRITES,
            "order_writes": PHASE25_ORDER_WRITES,
            "paper_submits": PHASE25_PAPER_SUBMITS,
            "live_writes": PHASE25_LIVE_WRITES,
            "phase11_support_writes": PHASE25_PHASE11_SUPPORT_WRITES,
            "protected_strategy_evidence_reads": PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
            "strategy_returns_read": PHASE25_GATE6_STRATEGY_RETURNS_READ_ALLOWED,
            "regime_routing_performed": PHASE25_GATE6_REGIME_ROUTING_ALLOWED,
            "strategy_rule_evaluation_performed": PHASE25_GATE6_STRATEGY_RULE_EVALUATION_ALLOWED,
            "support_replacement_authority": PHASE25_GATE6_SUPPORT_REPLACEMENT_ALLOWED,
            "discovery_overrides_used": PHASE25_GATE6_DISCOVERY_OVERRIDES_ALLOWED,
            "recommendation": "GATE7_RECONSTRUCT_MARKET_TICKER_ROUTE_CONTEXT_ON_ACCEPTED_DISCOVERY_POPULATION",
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": (
                len(sessions) > 0
                and len(summary_frame) == len(sessions)
                and PHASE25_GATE6_PROVIDER_READS == PHASE25_GATE6_PROVIDER_WRITES == 0
                and PHASE25_GATE6_OPERATIONAL_DISCOVERY_STATE_WRITES_ALLOWED is False
                and PHASE25_GATE6_STRATEGY_RETURNS_READ_ALLOWED is False
                and PHASE25_GATE6_REGIME_ROUTING_ALLOWED is False
                and PHASE25_GATE6_STRATEGY_RULE_EVALUATION_ALLOWED is False
                and PHASE25_GATE6_SUPPORT_REPLACEMENT_ALLOWED is False
                and PHASE25_BROKER_READS == PHASE25_BROKER_WRITES == 0
                and PHASE25_ORDER_WRITES == PHASE25_PAPER_SUBMITS == PHASE25_LIVE_WRITES == 0
                and PHASE25_PHASE11_SUPPORT_WRITES == 0
                and PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS == 0
            ),
        }
        if report["pass"] is not True:
            raise Phase25Gate6Error("Gate6 reconstruction acceptance checks failed")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
