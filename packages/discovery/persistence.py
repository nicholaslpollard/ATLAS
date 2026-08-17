from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.schemas.discovery_score import DiscoveryState
from packages.schemas.discovery_state import (
    DISCOVERY_STATE_SNAPSHOT_CONTRACT_VERSION,
    DiscoveryStateRecord,
)

from .scoring import DISCOVERY_SCORE_MANIFEST_VERSION
from .state_machine import DISCOVERY_STATE_POLICY_VERSION


DISCOVERY_PERSISTENCE_POLICY_VERSION = (
    "discovery-persistence-v1-immediate-hot-confirmed-warm-two-scan-demotion"
)
DISCOVERY_STATE_MANIFEST_VERSION = "discovery-state-manifest-v1-score-and-prior-state-lineage"

_STATE_RANK = {
    DiscoveryState.NORMAL: 0,
    DiscoveryState.WATCH: 1,
    DiscoveryState.WARM: 2,
    DiscoveryState.HOT: 3,
}
_RANK_STATE = {value: key for key, value in _STATE_RANK.items()}


@dataclass(frozen=True, slots=True)
class DiscoveryPersistencePolicy:
    warm_confirmation_observations: int = 2
    demotion_confirmation_observations: int = 2

    @staticmethod
    def coverage_cap(scored_timeframes: int) -> DiscoveryState:
        coverage = int(scored_timeframes)
        if coverage < 0 or coverage > 3:
            raise ValueError("scored_timeframes must be between 0 and 3")
        if coverage == 0:
            return DiscoveryState.NORMAL
        if coverage == 1:
            return DiscoveryState.WATCH
        if coverage == 2:
            return DiscoveryState.WARM
        return DiscoveryState.HOT

    def bootstrap(
        self,
        *,
        raw_state: DiscoveryState | str,
        scored_timeframes: int,
    ) -> tuple[DiscoveryState, int, int, str]:
        raw = DiscoveryState(raw_state)
        cap = self.coverage_cap(scored_timeframes)
        if raw == DiscoveryState.HOT:
            effective = DiscoveryState.HOT
            transition = "bootstrap_hot"
            warm_streak = 0
        elif raw == DiscoveryState.WARM:
            effective = DiscoveryState.WATCH
            transition = "bootstrap_warm_pending"
            warm_streak = 1
        elif raw == DiscoveryState.WATCH:
            effective = DiscoveryState.WATCH
            transition = "bootstrap_watch"
            warm_streak = 0
        else:
            effective = DiscoveryState.NORMAL
            transition = "bootstrap_normal"
            warm_streak = 0
        if _STATE_RANK[effective] > _STATE_RANK[cap]:
            effective = cap
            transition = "bootstrap_coverage_cap"
            warm_streak = 0
        return effective, warm_streak, 0, transition

    def transition(
        self,
        *,
        previous_effective_state: DiscoveryState | str,
        previous_warm_confirmation_streak: int,
        previous_demotion_streak: int,
        raw_state: DiscoveryState | str,
        scored_timeframes: int,
    ) -> tuple[DiscoveryState, int, int, str]:
        previous = DiscoveryState(previous_effective_state)
        raw = DiscoveryState(raw_state)
        cap = self.coverage_cap(scored_timeframes)

        # Coverage loss is a safety/data-quality constraint, not a soft score change.
        if _STATE_RANK[previous] > _STATE_RANK[cap]:
            return cap, 0, 0, "coverage_cap"

        if raw == DiscoveryState.HOT:
            transition = "hold_hot" if previous == DiscoveryState.HOT else "promote_hot"
            return DiscoveryState.HOT, 0, 0, transition

        previous_rank = _STATE_RANK[previous]
        raw_rank = _STATE_RANK[raw]

        if raw_rank > previous_rank:
            if raw_rank >= _STATE_RANK[DiscoveryState.WARM] and previous_rank < _STATE_RANK[DiscoveryState.WARM]:
                warm_streak = int(previous_warm_confirmation_streak) + 1
                if warm_streak >= self.warm_confirmation_observations:
                    effective = DiscoveryState.WARM
                    transition = "promote_warm"
                    warm_streak = 0
                else:
                    effective = DiscoveryState.WATCH
                    transition = "warm_confirmation_pending"
                if _STATE_RANK[effective] > _STATE_RANK[cap]:
                    return cap, 0, 0, "coverage_cap"
                return effective, warm_streak, 0, transition
            return raw, 0, 0, f"promote_{raw.value}"

        if raw_rank == previous_rank:
            return previous, 0, 0, f"hold_{previous.value}"

        demotion_streak = int(previous_demotion_streak) + 1
        if demotion_streak < self.demotion_confirmation_observations:
            return previous, 0, demotion_streak, "demotion_pending"

        demoted_rank = max(0, previous_rank - 1)
        effective = _RANK_STATE[demoted_rank]
        if _STATE_RANK[effective] > _STATE_RANK[cap]:
            effective = cap
            transition = "coverage_cap"
        else:
            transition = f"demote_{previous.value}_to_{effective.value}"
        return effective, 0, 0, transition


ACTIVE_DISCOVERY_PERSISTENCE_POLICY = DiscoveryPersistencePolicy()


@dataclass(frozen=True, slots=True)
class DiscoveryStateBuildResult:
    as_of_date: date
    record_count: int
    effective_state_counts: dict[str, int]
    raw_state_counts: dict[str, int]
    transition_counts: dict[str, int]
    previous_session_date: date | None
    continuity_used: bool
    dependency_fingerprint: str
    snapshot_sha256: str
    snapshot_path: Path
    manifest_path: Path
    wall_seconds: float
    skipped: bool


class DiscoveryStateManager:
    """Persist deterministic discovery state with bounded promotion/demotion hysteresis."""

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        policy: DiscoveryPersistencePolicy = ACTIVE_DISCOVERY_PERSISTENCE_POLICY,
    ) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.policy = policy
        self.calendar = get_market_calendar()

    @staticmethod
    def _json(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON manifest: {path}") from exc

    @staticmethod
    def _fingerprint(payload: dict[str, object]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _previous_session(self, as_of_date: date) -> date | None:
        sessions = self.calendar.sessions_in_range(as_of_date - timedelta(days=10), as_of_date)
        earlier = [session for session in sessions if session < as_of_date]
        return earlier[-1] if earlier else None

    def _score_lineage(self, as_of_date: date) -> tuple[Path, dict[str, Any]]:
        score_path = self.paths.discovery_score_file(as_of_date)
        score_manifest_path = self.paths.discovery_score_manifest(as_of_date)
        if not score_path.is_file() or not score_manifest_path.is_file():
            raise FileNotFoundError(f"Discovery score snapshot is missing for {as_of_date}")
        manifest = self._json(score_manifest_path)
        if manifest.get("manifest_version") != DISCOVERY_SCORE_MANIFEST_VERSION:
            raise ValueError("Discovery score manifest contract is stale")
        if manifest.get("state_policy_version") != DISCOVERY_STATE_POLICY_VERSION:
            raise ValueError(
                "Discovery score snapshot was not built with the active locked state policy; "
                "rerun score_discovery.py first"
            )
        actual_sha = sha256_file(score_path)
        if manifest.get("snapshot_sha256") != actual_sha:
            raise ValueError("Discovery score snapshot hash does not match its manifest")
        return score_path, manifest

    def _prior_lineage(
        self,
        as_of_date: date,
    ) -> tuple[date | None, Path | None, dict[str, Any] | None]:
        previous_date = self._previous_session(as_of_date)
        if previous_date is None:
            return None, None, None
        state_path = self.paths.discovery_state_file(previous_date)
        manifest_path = self.paths.discovery_state_manifest(previous_date)
        state_exists = state_path.is_file()
        manifest_exists = manifest_path.is_file()
        if state_exists != manifest_exists:
            raise ValueError(
                f"Incomplete previous discovery state for {previous_date}; expected both snapshot and manifest"
            )
        if not state_exists:
            return previous_date, None, None
        manifest = self._json(manifest_path)
        if manifest.get("manifest_version") != DISCOVERY_STATE_MANIFEST_VERSION:
            raise ValueError("Previous discovery state manifest contract is stale")
        if manifest.get("snapshot_contract_version") != DISCOVERY_STATE_SNAPSHOT_CONTRACT_VERSION:
            raise ValueError("Previous discovery state snapshot contract is stale")
        actual_sha = sha256_file(state_path)
        if manifest.get("snapshot_sha256") != actual_sha:
            raise ValueError("Previous discovery state snapshot hash does not match its manifest")
        return previous_date, state_path, manifest

    def _dependency(
        self,
        *,
        as_of_date: date,
        score_manifest: dict[str, Any],
        previous_date: date | None,
        previous_manifest: dict[str, Any] | None,
    ) -> str:
        return self._fingerprint(
            {
                "manifest_version": DISCOVERY_STATE_MANIFEST_VERSION,
                "snapshot_contract": DISCOVERY_STATE_SNAPSHOT_CONTRACT_VERSION,
                "persistence_policy": DISCOVERY_PERSISTENCE_POLICY_VERSION,
                "persistence_parameters": {
                    "warm_confirmation_observations": self.policy.warm_confirmation_observations,
                    "demotion_confirmation_observations": self.policy.demotion_confirmation_observations,
                },
                "state_policy": DISCOVERY_STATE_POLICY_VERSION,
                "as_of_date": as_of_date.isoformat(),
                "score_snapshot_sha256": score_manifest["snapshot_sha256"],
                "score_dependency_fingerprint": score_manifest["dependency_fingerprint"],
                "previous_session_date": None if previous_date is None else previous_date.isoformat(),
                "previous_state_sha256": (
                    None if previous_manifest is None else previous_manifest["snapshot_sha256"]
                ),
            }
        )

    def _existing(
        self,
        *,
        dependency: str,
        snapshot_path: Path,
        manifest_path: Path,
    ) -> dict[str, Any] | None:
        if not snapshot_path.is_file() or not manifest_path.is_file():
            return None
        try:
            manifest = self._json(manifest_path)
        except ValueError:
            return None
        if manifest.get("manifest_version") != DISCOVERY_STATE_MANIFEST_VERSION:
            return None
        if manifest.get("dependency_fingerprint") != dependency:
            return None
        return manifest if manifest.get("snapshot_sha256") == sha256_file(snapshot_path) else None

    @staticmethod
    def _result(
        *,
        manifest: dict[str, Any],
        snapshot_path: Path,
        manifest_path: Path,
        wall_seconds: float,
        skipped: bool,
    ) -> DiscoveryStateBuildResult:
        previous = manifest.get("previous_session_date")
        return DiscoveryStateBuildResult(
            as_of_date=date.fromisoformat(str(manifest["as_of_date"])),
            record_count=int(manifest["record_count"]),
            effective_state_counts={
                str(key): int(value) for key, value in manifest["effective_state_counts"].items()
            },
            raw_state_counts={
                str(key): int(value) for key, value in manifest["raw_state_counts"].items()
            },
            transition_counts={
                str(key): int(value) for key, value in manifest["transition_counts"].items()
            },
            previous_session_date=None if previous is None else date.fromisoformat(str(previous)),
            continuity_used=bool(manifest["continuity_used"]),
            dependency_fingerprint=str(manifest["dependency_fingerprint"]),
            snapshot_sha256=str(manifest["snapshot_sha256"]),
            snapshot_path=snapshot_path,
            manifest_path=manifest_path,
            wall_seconds=wall_seconds,
            skipped=skipped,
        )

    def build(self, as_of_date: date) -> DiscoveryStateBuildResult:
        started = perf_counter()
        if not self.calendar.is_session(as_of_date):
            raise ValueError(f"{as_of_date} is not a trading session")

        score_path, score_manifest = self._score_lineage(as_of_date)
        previous_date, previous_path, previous_manifest = self._prior_lineage(as_of_date)
        dependency = self._dependency(
            as_of_date=as_of_date,
            score_manifest=score_manifest,
            previous_date=previous_date,
            previous_manifest=previous_manifest,
        )
        snapshot_path = self.paths.discovery_state_file(as_of_date)
        manifest_path = self.paths.discovery_state_manifest(as_of_date)
        existing = self._existing(
            dependency=dependency,
            snapshot_path=snapshot_path,
            manifest_path=manifest_path,
        )
        if existing is not None:
            return self._result(
                manifest=existing,
                snapshot_path=snapshot_path,
                manifest_path=manifest_path,
                wall_seconds=perf_counter() - started,
                skipped=True,
            )

        con = connect_utc(":memory:")
        try:
            current = con.execute(
                f"SELECT * FROM read_parquet({sql_string(score_path)}) ORDER BY instrument_id"
            ).fetch_df()
            if previous_path is None:
                previous = pd.DataFrame()
            else:
                previous = con.execute(
                    f"SELECT instrument_id, effective_state, warm_confirmation_streak, demotion_streak "
                    f"FROM read_parquet({sql_string(previous_path)})"
                ).fetch_df()
        finally:
            con.close()

        previous_map = (
            previous.set_index("instrument_id").to_dict(orient="index") if not previous.empty else {}
        )

        records: list[DiscoveryStateRecord] = []
        effective_counts: Counter[str] = Counter()
        raw_counts: Counter[str] = Counter()
        transition_counts: Counter[str] = Counter()
        continuity_used = previous_path is not None

        for _, row in current.iterrows():
            instrument_id = str(row["instrument_id"])
            raw_state = DiscoveryState(str(row["raw_state"]))
            scored_timeframes = int(row["scored_timeframes"])
            prior = previous_map.get(instrument_id)
            if prior is None:
                effective, warm_streak, demotion_streak, transition = self.policy.bootstrap(
                    raw_state=raw_state,
                    scored_timeframes=scored_timeframes,
                )
                previous_effective = None
            else:
                previous_effective = DiscoveryState(str(prior["effective_state"]))
                effective, warm_streak, demotion_streak, transition = self.policy.transition(
                    previous_effective_state=previous_effective,
                    previous_warm_confirmation_streak=int(prior["warm_confirmation_streak"]),
                    previous_demotion_streak=int(prior["demotion_streak"]),
                    raw_state=raw_state,
                    scored_timeframes=scored_timeframes,
                )

            record = DiscoveryStateRecord(
                instrument_id=instrument_id,
                ticker=str(row["ticker"]),
                as_of_date=as_of_date,
                raw_state=raw_state,
                effective_state=effective,
                previous_effective_state=previous_effective,
                warm_confirmation_streak=warm_streak,
                demotion_streak=demotion_streak,
                transition=transition,
                priority_score=float(row["priority_score"]),
                bull_evidence=float(row["bull_evidence"]),
                bear_evidence=float(row["bear_evidence"]),
                direction=str(row["direction"]),
                scored_timeframes=scored_timeframes,
                top_setup=str(row["top_setup"]),
            )
            records.append(record)
            effective_counts.update([record.effective_state.value])
            raw_counts.update([record.raw_state.value])
            transition_counts.update([record.transition])

        output = pd.DataFrame.from_records(
            [
                {
                    **record.model_dump(mode="python"),
                    "raw_state": record.raw_state.value,
                    "effective_state": record.effective_state.value,
                    "previous_effective_state": (
                        None
                        if record.previous_effective_state is None
                        else record.previous_effective_state.value
                    ),
                    "direction": record.direction.value,
                }
                for record in records
            ]
        )

        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(snapshot_path)
        con = connect_utc(":memory:")
        try:
            con.register("atlas_discovery_states", output)
            compression = self.settings.data.parquet.compression.upper()
            row_group_size = int(self.settings.data.parquet.row_group_size)
            con.execute(
                f"""
                COPY (SELECT * FROM atlas_discovery_states ORDER BY instrument_id)
                TO {sql_string(temp)}
                (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
                """
            )
            promote(temp, snapshot_path)
        finally:
            con.close()

        snapshot_sha = sha256_file(snapshot_path)
        manifest = {
            "manifest_version": DISCOVERY_STATE_MANIFEST_VERSION,
            "snapshot_contract_version": DISCOVERY_STATE_SNAPSHOT_CONTRACT_VERSION,
            "persistence_policy_version": DISCOVERY_PERSISTENCE_POLICY_VERSION,
            "state_policy_version": DISCOVERY_STATE_POLICY_VERSION,
            "as_of_date": as_of_date.isoformat(),
            "previous_session_date": None if previous_date is None else previous_date.isoformat(),
            "continuity_used": continuity_used,
            "dependency_fingerprint": dependency,
            "score_snapshot_sha256": score_manifest["snapshot_sha256"],
            "previous_state_sha256": (
                None if previous_manifest is None else previous_manifest["snapshot_sha256"]
            ),
            "record_count": len(records),
            "raw_state_counts": dict(sorted(raw_counts.items())),
            "effective_state_counts": dict(sorted(effective_counts.items())),
            "transition_counts": dict(sorted(transition_counts.items())),
            "snapshot_path": str(snapshot_path.resolve()),
            "snapshot_sha256": snapshot_sha,
            "generated_at_utc": datetime.now(UTC).isoformat(),
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        return self._result(
            manifest=manifest,
            snapshot_path=snapshot_path,
            manifest_path=manifest_path,
            wall_seconds=perf_counter() - started,
            skipped=False,
        )
