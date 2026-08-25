from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterable

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.features.partition_store import FeaturePartitionManifest
from packages.instruments.identity import IDENTITY_CONTRACT_VERSION
from packages.instruments.registry import REFERENCE_CONTRACT_VERSION
from packages.universe.manager import UNIVERSE_MANIFEST_VERSION

from .phase25_policy import (
    PHASE25_BROKER_READS,
    PHASE25_BROKER_WRITES,
    PHASE25_GATE0_CONTRACT_VERSION,
    PHASE25_LIVE_WRITES,
    PHASE25_MARKET_DAILY_ORIGIN,
    PHASE25_ORDER_WRITES,
    PHASE25_PAPER_SUBMITS,
    PHASE25_PHASE11_SUPPORT_WRITES,
    PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
    PHASE25_PROVIDER_READS,
    PHASE25_PROVIDER_WRITES,
    PHASE25_ROUTE_REPLAY_ORIGIN,
    phase25_gate0_policy_fingerprint,
)


PHASE25_GATE0_REPORT_CONTRACT_VERSION = (
    "phase25-gate0-report-v1-local-artifact-coverage-route-fidelity-feasibility"
)


class Phase25Gate0Error(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _missing_preview(sessions: Iterable[date], limit: int = 20) -> list[str]:
    values = [item.isoformat() for item in sessions]
    return values[:limit]


@dataclass(frozen=True, slots=True)
class ArtifactCoverage:
    total_sessions: int
    present_sessions: int
    missing_sessions: int
    missing_preview: tuple[str, ...]

    @classmethod
    def from_presence(cls, sessions: tuple[date, ...], present: dict[date, bool]) -> "ArtifactCoverage":
        missing = tuple(item for item in sessions if not present[item])
        return cls(
            total_sessions=len(sessions),
            present_sessions=len(sessions) - len(missing),
            missing_sessions=len(missing),
            missing_preview=tuple(_missing_preview(missing)),
        )


@dataclass(frozen=True, slots=True)
class SessionFeasibility:
    session_date: str
    canonical_1d: bool
    derived_4h: bool
    derived_1h: bool
    features_1d: bool
    features_4h: bool
    features_1h: bool
    feature_manifests_1d_4h_1h: bool
    universe_materialized: bool
    universe_reference_backed: bool
    discovery_materialized: bool
    market_regime_materialized: bool
    ticker_regime_materialized: bool
    base_inputs_complete: bool
    base_inputs_prefix_complete: bool
    market_daily_manifest_prefix_complete: bool
    ticker_feature_prefix_complete: bool
    discovery_available_or_replayable: bool
    market_regime_available_or_replayable: bool
    ticker_regime_available_or_replayable: bool
    route_fidelity_available_or_replayable: bool


class Phase25Gate0Inventory:
    """Provider-free inventory for exact historical production-path replay feasibility.

    This class never computes strategy returns, never calls a provider or broker, and
    never mutates production analytical/support state. It only inspects local path and
    manifest availability so later replay work can be scoped without fabrication.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate0"

    def report_path(self, through_date: date) -> Path:
        return self.root / f"through={through_date}" / "feasibility_inventory.json"

    @staticmethod
    def _feature_manifest_valid(path: Path, timeframe: Timeframe, session: date) -> bool:
        payload = _read_json(path)
        if payload is None:
            return False
        try:
            manifest = FeaturePartitionManifest.from_dict(payload)
            manifest.validate_contract(timeframe, session)
        except (KeyError, TypeError, ValueError):
            return False
        return True

    def _reference_pair_valid(self, session: date) -> bool:
        snapshot = self.paths.reference_snapshot_file(session)
        manifest = _read_json(self.paths.reference_snapshot_manifest(session))
        if not snapshot.is_file() or manifest is None:
            return False
        return bool(
            manifest.get("contract_version") == REFERENCE_CONTRACT_VERSION
            and manifest.get("identity_contract_version") == IDENTITY_CONTRACT_VERSION
        )

    def _universe_pair_valid(self, session: date) -> bool:
        snapshot = self.paths.universe_snapshot_file(session)
        manifest = _read_json(self.paths.universe_snapshot_manifest(session))
        if not snapshot.is_file() or manifest is None:
            return False
        return manifest.get("manifest_version") == UNIVERSE_MANIFEST_VERSION

    def _discovery_materialized(self, session: date) -> bool:
        required = (
            self.paths.discovery_snapshot_file(session),
            self.paths.discovery_snapshot_manifest(session),
            self.paths.discovery_score_file(session),
            self.paths.discovery_score_manifest(session),
            self.paths.discovery_state_file(session),
            self.paths.discovery_state_manifest(session),
        )
        return all(path.is_file() for path in required)

    def _ticker_state_paths(self, session: date) -> tuple[Path, Path]:
        derived = self.settings.resolved_path(self.settings.data.paths.derived)
        manifests = self.settings.resolved_path(self.settings.data.paths.manifests)
        return (
            derived
            / "regimes"
            / "ticker_states"
            / f"year={session.year:04d}"
            / f"date={session}"
            / "part-000.parquet",
            manifests / "regimes" / "ticker_states" / f"{session.year:04d}" / f"{session}.json",
        )

    def _identity_inputs(self) -> dict[str, bool]:
        return {
            "ticker_observations": self.paths.ticker_observations_file().is_file(),
            "authoritative_ticker_intervals": self.paths.authoritative_ticker_intervals_file().is_file(),
            "instrument_registry": self.paths.instrument_registry_file().is_file(),
        }

    def run(self, *, through_date: date) -> dict[str, object]:
        if through_date < PHASE25_ROUTE_REPLAY_ORIGIN:
            raise Phase25Gate0Error(
                f"through_date predates Phase25 replay origin {PHASE25_ROUTE_REPLAY_ORIGIN}: {through_date}"
            )
        if not self.calendar.is_session(through_date):
            raise Phase25Gate0Error(f"through_date is not an exchange session: {through_date}")

        sessions = tuple(
            self.calendar.sessions_in_range(PHASE25_ROUTE_REPLAY_ORIGIN, through_date)
        )
        if not sessions or sessions[0] != PHASE25_ROUTE_REPLAY_ORIGIN:
            raise Phase25Gate0Error("Phase25 replay session enumeration does not begin at locked origin")

        market_daily_sessions = tuple(
            self.calendar.sessions_in_range(PHASE25_MARKET_DAILY_ORIGIN, through_date)
        )
        identity = self._identity_inputs()
        identity_complete = all(identity.values())

        presence: dict[str, dict[date, bool]] = {
            key: {} for key in (
                "canonical_1d",
                "derived_4h",
                "derived_1h",
                "features_1d",
                "features_4h",
                "features_1h",
                "feature_manifests_triplet",
                "reference_pair",
                "universe_pair",
                "discovery_materialized",
                "market_regime_pair",
                "ticker_regime_pair",
                "base_inputs_complete",
                "route_fidelity_available_or_replayable",
            )
        }

        # Market/sector state reconstruction has a daily-history origin in 2016.
        market_daily_manifest_valid: dict[date, bool] = {}
        market_prefix_complete = True
        market_prefix_by_session: dict[date, bool] = {}
        for session in market_daily_sessions:
            valid = self._feature_manifest_valid(
                self.paths.feature_manifest_file(Timeframe.DAY_1, session),
                Timeframe.DAY_1,
                session,
            ) and self.paths.feature_file(Timeframe.DAY_1, session).is_file()
            market_daily_manifest_valid[session] = valid
            market_prefix_complete = market_prefix_complete and valid
            if session >= PHASE25_ROUTE_REPLAY_ORIGIN:
                market_prefix_by_session[session] = market_prefix_complete

        base_prefix_complete = True
        ticker_feature_prefix_complete = True
        records: list[SessionFeasibility] = []
        for session in sessions:
            canonical_1d = self.paths.canonical_file(Timeframe.DAY_1, session).is_file()
            derived_4h = self.paths.derived_file(Timeframe.HOUR_4, session).is_file()
            derived_1h = self.paths.derived_file(Timeframe.HOUR_1, session).is_file()
            features_1d = self.paths.feature_file(Timeframe.DAY_1, session).is_file()
            features_4h = self.paths.feature_file(Timeframe.HOUR_4, session).is_file()
            features_1h = self.paths.feature_file(Timeframe.HOUR_1, session).is_file()
            manifests = all(
                self._feature_manifest_valid(
                    self.paths.feature_manifest_file(timeframe, session), timeframe, session
                )
                for timeframe in (Timeframe.DAY_1, Timeframe.HOUR_4, Timeframe.HOUR_1)
            )
            universe_pair = self._universe_pair_valid(session)
            reference_pair = self._reference_pair_valid(session)
            discovery_materialized = self._discovery_materialized(session)
            market_regime_pair = bool(
                self.paths.regime_state_snapshot(session).is_file()
                and self.paths.regime_state_manifest(session).is_file()
            )
            ticker_snapshot, ticker_manifest = self._ticker_state_paths(session)
            ticker_regime_pair = ticker_snapshot.is_file() and ticker_manifest.is_file()

            base_complete = bool(
                canonical_1d
                and derived_4h
                and derived_1h
                and features_1d
                and features_4h
                and features_1h
                and manifests
                and (universe_pair or reference_pair)
            )
            base_prefix_complete = base_prefix_complete and base_complete
            ticker_feature_prefix_complete = bool(
                ticker_feature_prefix_complete
                and canonical_1d
                and derived_4h
                and derived_1h
                and features_1d
                and features_4h
                and features_1h
                and manifests
            )
            market_prefix = market_prefix_by_session.get(session, False)

            discovery_available = discovery_materialized or base_prefix_complete
            market_available = market_regime_pair or market_prefix
            ticker_available = bool(
                ticker_regime_pair
                or (
                    identity_complete
                    and ticker_feature_prefix_complete
                    and discovery_available
                    and (universe_pair or reference_pair)
                )
            )
            route_ready = bool(
                base_complete
                and discovery_available
                and market_available
                and ticker_available
            )

            values = {
                "canonical_1d": canonical_1d,
                "derived_4h": derived_4h,
                "derived_1h": derived_1h,
                "features_1d": features_1d,
                "features_4h": features_4h,
                "features_1h": features_1h,
                "feature_manifests_triplet": manifests,
                "reference_pair": reference_pair,
                "universe_pair": universe_pair,
                "discovery_materialized": discovery_materialized,
                "market_regime_pair": market_regime_pair,
                "ticker_regime_pair": ticker_regime_pair,
                "base_inputs_complete": base_complete,
                "route_fidelity_available_or_replayable": route_ready,
            }
            for key, value in values.items():
                presence[key][session] = bool(value)

            records.append(
                SessionFeasibility(
                    session_date=session.isoformat(),
                    canonical_1d=canonical_1d,
                    derived_4h=derived_4h,
                    derived_1h=derived_1h,
                    features_1d=features_1d,
                    features_4h=features_4h,
                    features_1h=features_1h,
                    feature_manifests_1d_4h_1h=manifests,
                    universe_materialized=universe_pair,
                    universe_reference_backed=reference_pair,
                    discovery_materialized=discovery_materialized,
                    market_regime_materialized=market_regime_pair,
                    ticker_regime_materialized=ticker_regime_pair,
                    base_inputs_complete=base_complete,
                    base_inputs_prefix_complete=base_prefix_complete,
                    market_daily_manifest_prefix_complete=market_prefix,
                    ticker_feature_prefix_complete=ticker_feature_prefix_complete,
                    discovery_available_or_replayable=discovery_available,
                    market_regime_available_or_replayable=market_available,
                    ticker_regime_available_or_replayable=ticker_available,
                    route_fidelity_available_or_replayable=route_ready,
                )
            )

        coverage = {
            key: asdict(ArtifactCoverage.from_presence(sessions, values))
            for key, values in presence.items()
        }
        market_missing = tuple(
            item for item in market_daily_sessions if not market_daily_manifest_valid[item]
        )
        reference_reconstructable = sum(
            1
            for item in records
            if not item.universe_materialized and item.universe_reference_backed
        )
        blocked_universe = sum(
            1
            for item in records
            if not item.universe_materialized and not item.universe_reference_backed
        )
        route_ready_dates = tuple(
            date.fromisoformat(item.session_date)
            for item in records
            if item.route_fidelity_available_or_replayable
        )

        # Report maximal contiguous ready ranges; gaps are preserved instead of skipped.
        ordinal = {session: index for index, session in enumerate(sessions)}
        ranges: list[dict[str, object]] = []
        start: date | None = None
        previous: date | None = None
        for session in route_ready_dates:
            if start is None:
                start = previous = session
                continue
            assert previous is not None
            if ordinal[session] != ordinal[previous] + 1:
                ranges.append(
                    {
                        "start": start.isoformat(),
                        "end": previous.isoformat(),
                        "sessions": ordinal[previous] - ordinal[start] + 1,
                    }
                )
                start = session
            previous = session
        if start is not None and previous is not None:
            ranges.append(
                {
                    "start": start.isoformat(),
                    "end": previous.isoformat(),
                    "sessions": ordinal[previous] - ordinal[start] + 1,
                }
            )

        blockers: list[str] = []
        if blocked_universe:
            blockers.append(
                f"{blocked_universe} replay sessions have neither a materialized PIT universe nor an exact local PIT reference snapshot"
            )
        if market_missing:
            blockers.append(
                f"split-origin market regime replay lacks {len(market_missing)} required 1d feature partitions/manifests from {PHASE25_MARKET_DAILY_ORIGIN} through {through_date}"
            )
        if not identity_complete:
            missing_identity = [key for key, value in identity.items() if not value]
            blockers.append("ticker identity replay inputs missing: " + ", ".join(missing_identity))
        route_missing = len(sessions) - len(route_ready_dates)
        if route_missing:
            blockers.append(
                f"{route_missing} sessions are not yet locally route-fidelity ready under the conservative Gate0 inventory"
            )

        recommendation = (
            "GATE1_REPLAY_IMPLEMENTATION_FEASIBLE"
            if not blockers and len(route_ready_dates) == len(sessions)
            else "GATE1_BLOCKED_PENDING_LOCAL_LINEAGE_RECONSTRUCTION_OR_SCOPE_PROOF"
        )

        core: dict[str, object] = {
            "contract_version": PHASE25_GATE0_REPORT_CONTRACT_VERSION,
            "gate_contract_version": PHASE25_GATE0_CONTRACT_VERSION,
            "policy_fingerprint": phase25_gate0_policy_fingerprint(),
            "replay_origin": PHASE25_ROUTE_REPLAY_ORIGIN.isoformat(),
            "market_daily_origin": PHASE25_MARKET_DAILY_ORIGIN.isoformat(),
            "through_date": through_date.isoformat(),
            "replay_session_count": len(sessions),
            "market_daily_session_count": len(market_daily_sessions),
            "identity_inputs": identity,
            "identity_inputs_complete": identity_complete,
            "coverage": coverage,
            "market_daily_feature_manifest_coverage": {
                "total_sessions": len(market_daily_sessions),
                "present_sessions": len(market_daily_sessions) - len(market_missing),
                "missing_sessions": len(market_missing),
                "missing_preview": _missing_preview(market_missing),
            },
            "universe_reference_reconstructable_sessions": reference_reconstructable,
            "universe_source_blocked_sessions": blocked_universe,
            "route_fidelity_ready_sessions": len(route_ready_dates),
            "route_fidelity_ready_ranges": ranges,
            "blockers": blockers,
            "recommendation": recommendation,
            "session_feasibility": [asdict(item) for item in records],
            "protected_strategy_evidence_reads": PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
            "provider_reads": PHASE25_PROVIDER_READS,
            "provider_writes": PHASE25_PROVIDER_WRITES,
            "broker_reads": PHASE25_BROKER_READS,
            "broker_writes": PHASE25_BROKER_WRITES,
            "order_writes": PHASE25_ORDER_WRITES,
            "paper_submits": PHASE25_PAPER_SUBMITS,
            "live_writes": PHASE25_LIVE_WRITES,
            "phase11_support_writes": PHASE25_PHASE11_SUPPORT_WRITES,
        }
        checks = {
            "origin_locked_2021_08_16": sessions[0] == PHASE25_ROUTE_REPLAY_ORIGIN,
            "market_daily_origin_locked_2016_01_04": PHASE25_MARKET_DAILY_ORIGIN == date(2016, 1, 4),
            "provider_reads_zero": PHASE25_PROVIDER_READS == 0,
            "provider_writes_zero": PHASE25_PROVIDER_WRITES == 0,
            "broker_reads_zero": PHASE25_BROKER_READS == 0,
            "broker_writes_zero": PHASE25_BROKER_WRITES == 0,
            "order_paper_live_writes_zero": PHASE25_ORDER_WRITES == PHASE25_PAPER_SUBMITS == PHASE25_LIVE_WRITES == 0,
            "support_writes_zero": PHASE25_PHASE11_SUPPORT_WRITES == 0,
            "protected_strategy_evidence_reads_zero": PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS == 0,
        }
        report = {
            **core,
            "checks": checks,
            "pass": all(checks.values()),
        }
        report["source_fingerprint"] = _stable_hash(report)
        report["generated_at_utc"] = datetime.now(UTC).isoformat()

        target = self.report_path(through_date)
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(target, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(target.resolve())
        return report
