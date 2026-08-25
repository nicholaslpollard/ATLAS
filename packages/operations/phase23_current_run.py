from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from apps.data_maintenance.historical_build_service import HistoricalBuildService
from packages.ai.phase14_closeout import Phase14Closeout
from packages.analogues.phase12_closeout import Phase12Closeout
from packages.backtesting.historical_study import StrategyHistoricalStudy
from packages.core.atomic_io import atomic_write_text
from packages.core.enums import DatasetType, Timeframe
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.discovery.current_candidates import CurrentCandidateMaterializer
from packages.discovery.persistence import DiscoveryStateManager
from packages.discovery.scanner import DiscoveryFoundationScanner
from packages.discovery.scoring import DiscoverySetupScanner
from packages.execution.phase15_foundation import (
    PHASE15_ACCEPTED_CUMULATIVE_HISTORY_END,
    Phase15CumulativeFoundationResolver,
)
from packages.execution.phase15_source import Phase15ExecutionInputResolver
from packages.features.historical_materializer import HistoricalFeatureMaterializer
from packages.features.partition_store import sha256_file
from packages.instruments.registry import InstrumentRegistryStore
from packages.operations.phase23_handoff import (
    Phase23AnalysisHandoffStore,
    Phase23HandoffError,
)
from packages.operations.phase23_policy import (
    MASSIVE_MARKET_REFERENCE_READS,
    PHASE23_DEFAULT_BROKER,
    Phase23ReadAuthority,
    Phase23ReadChallenge,
    build_phase23_read_challenge,
    phase23_policy_fingerprint,
    require_phase23_read_authority,
)
from packages.operations.phase23_strategy import Phase23CurrentStrategyHandoffStore
from packages.portfolio.phase13_closeout import Phase13Closeout
from packages.regimes.split_origin_state_engine import SplitOriginRegimeStateEngine
from packages.regimes.ticker_state_engine import TickerStateEngine
from packages.schemas.execution import BrokerName
from packages.universe.manager import UniverseManager


PHASE23_RUN_MANIFEST_CONTRACT_VERSION = (
    "phase23-run-manifest-v1-finalized-session-current-analysis-no-execution"
)


class Phase23CurrentRunError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise Phase23CurrentRunError(f"missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase23CurrentRunError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise Phase23CurrentRunError(f"{label} must be a JSON object")
    return value


@dataclass(frozen=True, slots=True)
class Phase23Preparation:
    as_of_date: date
    broker: BrokerName
    baseline_discovery_date: date
    sessions_to_advance: tuple[date, ...]
    missing_reference_sessions: tuple[date, ...]
    missing_daily_sessions: tuple[date, ...]
    missing_minute_sessions: tuple[date, ...]
    external_read_classes: tuple[str, ...]
    run_scope_fingerprint: str
    challenge: Phase23ReadChallenge | None

    @property
    def authority_required(self) -> bool:
        return self.challenge is not None

    def scope_payload(self) -> dict[str, object]:
        return {
            "as_of_date": self.as_of_date.isoformat(),
            "broker": self.broker.value,
            "baseline_discovery_date": self.baseline_discovery_date.isoformat(),
            "sessions_to_advance": [item.isoformat() for item in self.sessions_to_advance],
            "missing_reference_sessions": [item.isoformat() for item in self.missing_reference_sessions],
            "missing_daily_sessions": [item.isoformat() for item in self.missing_daily_sessions],
            "missing_minute_sessions": [item.isoformat() for item in self.missing_minute_sessions],
            "external_read_classes": list(self.external_read_classes),
            "run_scope_fingerprint": self.run_scope_fingerprint,
        }

    def public_dict(self) -> dict[str, object]:
        return {
            **self.scope_payload(),
            "phase23_policy_fingerprint": phase23_policy_fingerprint(),
            "authority_required": self.authority_required,
            "challenge": None if self.challenge is None else self.challenge.public_dict(),
        }


class Phase23CurrentAnalysisCycle:
    """Routine finalized-session analytical coordinator.

    Preparation is intentionally provider-free. Execution may acquire only the exact
    read authority described by the preparation, advances every missing exchange session
    in order, reuses the frozen historical strategy support, and stops before any Phase 22
    PAPER execution action.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "operations" / "phase23" / "v1"

    def run_dir(self, as_of_date: date, broker: BrokerName) -> Path:
        return self.root / "runs" / f"year={as_of_date.year:04d}" / f"date={as_of_date}" / f"broker={broker.value}"

    def manifest_path(self, as_of_date: date, broker: BrokerName) -> Path:
        return self.run_dir(as_of_date, broker) / "manifest.json"

    def journal_path(self, as_of_date: date, broker: BrokerName) -> Path:
        return self.run_dir(as_of_date, broker) / "journal.jsonl"

    def _market_today(self) -> date:
        return datetime.now(ZoneInfo(self.settings.data.calendar.market_timezone)).date()

    def _validate_as_of(self, as_of_date: date) -> None:
        if not self.calendar.is_session(as_of_date):
            raise Phase23CurrentRunError(f"Phase 23 as-of is not an exchange session: {as_of_date}")
        if as_of_date >= self._market_today():
            raise Phase23CurrentRunError(
                "Phase 23 requires a prior finalized exchange session; same-day provisional data is not accepted"
            )

    def _accepted_phase23_dates(self, as_of_date: date) -> list[date]:
        store = Phase23AnalysisHandoffStore(self.settings)
        if not store.root.exists():
            return []
        cumulative = Phase15CumulativeFoundationResolver(self.settings).resolve()
        accepted: list[date] = []
        for path in sorted(store.root.glob("year=*/*.json")):
            try:
                candidate = date.fromisoformat(path.stem)
            except ValueError:
                continue
            if candidate > as_of_date:
                continue
            payload = _read_json(path, f"Phase 23 handoff candidate {candidate}")
            expected_phase14_sha = str(payload.get("phase14_acceptance_sha256") or "")
            if len(expected_phase14_sha) != 64:
                continue
            try:
                store.resolve(
                    as_of_date=candidate,
                    cumulative=cumulative,
                    expected_phase14_acceptance_sha256=expected_phase14_sha,
                )
            except Phase23HandoffError:
                continue
            if not self.paths.discovery_state_file(candidate).is_file():
                continue
            if not self.paths.discovery_state_manifest(candidate).is_file():
                continue
            accepted.append(candidate)
        return sorted(set(accepted))

    def _baseline_discovery_date(self, as_of_date: date) -> date:
        candidates: list[date] = []
        frozen = PHASE15_ACCEPTED_CUMULATIVE_HISTORY_END
        if frozen <= as_of_date:
            if not self.paths.discovery_state_file(frozen).is_file() or not self.paths.discovery_state_manifest(frozen).is_file():
                raise Phase23CurrentRunError(
                    "Phase 23 frozen cumulative discovery baseline is missing; silent operational rebootstrap is forbidden"
                )
            candidates.append(frozen)
        candidates.extend(self._accepted_phase23_dates(as_of_date))
        if not candidates:
            raise Phase23CurrentRunError(
                "Phase 23 requires an accepted operational discovery-state baseline; silent operational rebootstrap is forbidden"
            )
        return max(candidates)

    def prepare(
        self,
        *,
        as_of_date: date,
        broker: BrokerName | str = PHASE23_DEFAULT_BROKER,
    ) -> Phase23Preparation:
        self._validate_as_of(as_of_date)
        selected = BrokerName(broker)
        if selected not in {BrokerName.WEBULL, BrokerName.ALPACA}:
            raise Phase23CurrentRunError("Phase 23 supports only Webull or Alpaca PAPER read context")
        baseline = self._baseline_discovery_date(as_of_date)
        if baseline > as_of_date:
            raise Phase23CurrentRunError("Phase 23 baseline is newer than requested as-of")
        sessions = tuple(
            self.calendar.sessions_in_range(baseline + timedelta(days=1), as_of_date)
            if baseline < as_of_date
            else ()
        )
        missing_reference = tuple(
            item
            for item in sessions
            if not self.paths.reference_snapshot_file(item).is_file()
            or not self.paths.reference_snapshot_manifest(item).is_file()
        )
        missing_daily = tuple(
            item
            for item in sessions
            if not self.paths.provider_file(DatasetType.STOCK_DAILY_AGGREGATES, item).is_file()
        )
        missing_minute = tuple(
            item
            for item in sessions
            if not self.paths.provider_file(DatasetType.STOCK_MINUTE_AGGREGATES, item).is_file()
        )
        external_classes = (
            (MASSIVE_MARKET_REFERENCE_READS,)
            if missing_reference or missing_daily or missing_minute
            else ()
        )
        scope_basis = {
            "phase23_policy_fingerprint": phase23_policy_fingerprint(),
            "as_of_date": as_of_date.isoformat(),
            "broker": selected.value,
            "baseline_discovery_date": baseline.isoformat(),
            "sessions_to_advance": [item.isoformat() for item in sessions],
            "missing_reference_sessions": [item.isoformat() for item in missing_reference],
            "missing_daily_sessions": [item.isoformat() for item in missing_daily],
            "missing_minute_sessions": [item.isoformat() for item in missing_minute],
            "external_read_classes": list(external_classes),
        }
        run_fp = _stable_hash(scope_basis)
        challenge = None
        if external_classes:
            challenge = build_phase23_read_challenge(
                as_of_date=as_of_date,
                broker=selected,
                run_scope_payload={**scope_basis, "run_scope_fingerprint": run_fp},
                external_read_classes=external_classes,
            )
        return Phase23Preparation(
            as_of_date=as_of_date,
            broker=selected,
            baseline_discovery_date=baseline,
            sessions_to_advance=sessions,
            missing_reference_sessions=missing_reference,
            missing_daily_sessions=missing_daily,
            missing_minute_sessions=missing_minute,
            external_read_classes=external_classes,
            run_scope_fingerprint=run_fp,
            challenge=challenge,
        )

    def _journal(self, preparation: Phase23Preparation, stage: str, status: str, **details: object) -> None:
        path = self.journal_path(preparation.as_of_date, preparation.broker)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "at_utc": datetime.now(UTC).isoformat(),
            "run_scope_fingerprint": preparation.run_scope_fingerprint,
            "stage": stage,
            "status": status,
            "details": details,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")

    def _archive(self, preparation: Phase23Preparation, label: str, source: Path) -> str:
        if not source.is_file():
            raise Phase23CurrentRunError(f"cannot archive missing {label}: {source}")
        target = self.run_dir(preparation.as_of_date, preparation.broker) / "evidence" / f"{label}{source.suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return sha256_file(target)

    def _refresh_reference(self, preparation: Phase23Preparation) -> int:
        if not preparation.missing_reference_sessions:
            return 0
        store = InstrumentRegistryStore(self.settings)
        fetched = 0
        missing = set(preparation.missing_reference_sessions)
        for trading_date in preparation.sessions_to_advance:
            if trading_date not in missing:
                continue
            result = store.sync_snapshot(trading_date)
            if not result.skipped:
                fetched += 1
        return fetched

    def _market_data_paths(self, trading_date: date) -> dict[str, Path]:
        return {
            "provider_daily": self.paths.provider_file(DatasetType.STOCK_DAILY_AGGREGATES, trading_date),
            "provider_minute": self.paths.provider_file(DatasetType.STOCK_MINUTE_AGGREGATES, trading_date),
            "canonical_1d": self.paths.canonical_file(Timeframe.DAY_1, trading_date),
            "canonical_1m": self.paths.canonical_file(Timeframe.MINUTE_1, trading_date),
            "bars_1h": self.paths.derived_file(Timeframe.HOUR_1, trading_date),
            "bars_4h": self.paths.derived_file(Timeframe.HOUR_4, trading_date),
        }

    def _verify_market_data_completion(self, preparation: Phase23Preparation, result: object) -> None:
        expected = len(preparation.sessions_to_advance)
        if int(getattr(result, "inaccessible_sessions_skipped")) != 0:
            raise Phase23CurrentRunError("Phase 23 provider entitlement skipped requested finalized sessions")
        if int(getattr(result, "sessions_requested")) != expected:
            raise Phase23CurrentRunError("Phase 23 market-data requested-session count changed")
        if int(getattr(result, "sessions_processed")) != expected:
            raise Phase23CurrentRunError("Phase 23 market-data did not process every requested session")
        if preparation.sessions_to_advance:
            if getattr(result, "effective_start_date") != preparation.sessions_to_advance[0]:
                raise Phase23CurrentRunError("Phase 23 market-data effective start changed")
            if getattr(result, "effective_end_date") != preparation.sessions_to_advance[-1]:
                raise Phase23CurrentRunError("Phase 23 market-data effective end changed")
        missing: list[str] = []
        for trading_date in preparation.sessions_to_advance:
            for label, path in self._market_data_paths(trading_date).items():
                if not path.is_file():
                    missing.append(f"{trading_date}:{label}")
        if missing:
            raise Phase23CurrentRunError(
                "Phase 23 market-data advancement is incomplete: " + ", ".join(missing[:20])
            )

    def _advance_market_data(self, preparation: Phase23Preparation) -> dict[str, object]:
        if not preparation.sessions_to_advance:
            return {"sessions_processed": 0, "downloads_planned": 0, "materialization_failures": 0}
        start = preparation.sessions_to_advance[0]
        end = preparation.sessions_to_advance[-1]
        download_missing = bool(preparation.missing_daily_sessions or preparation.missing_minute_sessions)
        result = HistoricalBuildService(self.settings).run(
            start,
            end,
            download_missing=download_missing,
            materialize=True,
            continue_on_error=False,
        )
        if result.failures:
            raise Phase23CurrentRunError("Phase 23 market-data materialization reported failures")
        self._verify_market_data_completion(preparation, result)
        return {
            "sessions_requested": result.sessions_requested,
            "sessions_processed": result.sessions_processed,
            "inaccessible_sessions_skipped": result.inaccessible_sessions_skipped,
            "downloads_planned": result.daily_downloads_planned + result.minute_downloads_planned,
            "materialized_sessions": result.materialized_sessions,
            "skipped_materializations": result.skipped_materializations,
            "materialization_failures": len(result.failures),
        }

    def _verify_feature_completion(
        self,
        preparation: Phase23Preparation,
        *,
        materializer: HistoricalFeatureMaterializer,
        timeframe: Timeframe,
        checkpoint_as_of: date | None,
    ) -> None:
        if checkpoint_as_of != preparation.as_of_date:
            raise Phase23CurrentRunError(
                f"Phase 23 {timeframe.value} feature checkpoint did not finish at {preparation.as_of_date}"
            )
        missing: list[str] = []
        for trading_date in preparation.sessions_to_advance:
            if not self.paths.feature_file(timeframe, trading_date).is_file():
                missing.append(f"{trading_date}:feature")
            if not self.paths.feature_manifest_file(timeframe, trading_date).is_file():
                missing.append(f"{trading_date}:manifest")
        if missing:
            raise Phase23CurrentRunError(
                f"Phase 23 {timeframe.value} feature persistence is incomplete: " + ", ".join(missing[:20])
            )
        stale = materializer.stale_source_sessions(
            timeframe=timeframe,
            start=preparation.sessions_to_advance[0],
            end=preparation.as_of_date,
        )
        if stale:
            raise Phase23CurrentRunError(
                f"Phase 23 {timeframe.value} feature/source lineage is stale for: "
                + ", ".join(item.isoformat() for item in stale[:20])
            )

    def _advance_features(self, preparation: Phase23Preparation) -> dict[str, object]:
        if not preparation.sessions_to_advance:
            return {"sessions_processed": 0, "rows_processed": 0}
        start = preparation.sessions_to_advance[0]
        materializer = HistoricalFeatureMaterializer(self.settings)
        total_sessions = 0
        total_rows = 0
        per_timeframe: dict[str, object] = {}
        for timeframe in (Timeframe.DAY_1, Timeframe.HOUR_4, Timeframe.HOUR_1):
            result = materializer.materialize_range(
                timeframe=timeframe,
                start=start,
                end=preparation.as_of_date,
                bootstrap_from_empty=False,
            )
            self._verify_feature_completion(
                preparation,
                materializer=materializer,
                timeframe=timeframe,
                checkpoint_as_of=result.checkpoint_as_of,
            )
            total_sessions += result.sessions_processed
            total_rows += result.rows_processed
            per_timeframe[timeframe.value] = {
                "sessions_processed": result.sessions_processed,
                "rows_processed": result.rows_processed,
                "checkpoint_as_of": None if result.checkpoint_as_of is None else result.checkpoint_as_of.isoformat(),
            }
        return {"sessions_processed": total_sessions, "rows_processed": total_rows, "timeframes": per_timeframe}

    def _advance_discovery(self, preparation: Phase23Preparation) -> None:
        for trading_date in preparation.sessions_to_advance:
            UniverseManager(self.settings).build(trading_date)
            DiscoveryFoundationScanner(self.settings).build(trading_date)
            DiscoverySetupScanner(self.settings).build(trading_date)
            DiscoveryStateManager(self.settings).build(trading_date)

    def _stage_hashes(
        self,
        preparation: Phase23Preparation,
        *,
        market_regime_path: Path,
        ticker_regime_path: Path,
        current_candidate_manifest: Path,
        strategy_handoff: Path,
        phase12_acceptance: Path,
        phase13_acceptance: Path,
        phase14_acceptance: Path,
    ) -> dict[str, str]:
        as_of = preparation.as_of_date
        paths = {
            "reference": self.paths.reference_snapshot_file(as_of),
            "canonical_1d": self.paths.canonical_file(Timeframe.DAY_1, as_of),
            "bars_1h": self.paths.derived_file(Timeframe.HOUR_1, as_of),
            "bars_4h": self.paths.derived_file(Timeframe.HOUR_4, as_of),
            "features_1d": self.paths.feature_file(Timeframe.DAY_1, as_of),
            "features_1h": self.paths.feature_file(Timeframe.HOUR_1, as_of),
            "features_4h": self.paths.feature_file(Timeframe.HOUR_4, as_of),
            "universe": self.paths.universe_snapshot_file(as_of),
            "discovery": self.paths.discovery_state_file(as_of),
            "market_regime": market_regime_path,
            "ticker_regime": ticker_regime_path,
            "current_candidates": current_candidate_manifest,
            "strategy_handoff": strategy_handoff,
            "phase12_acceptance": phase12_acceptance,
            "phase13_acceptance": phase13_acceptance,
            "phase14_acceptance": phase14_acceptance,
        }
        missing = sorted(name for name, path in paths.items() if not path.is_file())
        if missing:
            raise Phase23CurrentRunError("Phase 23 final lineage is missing: " + ", ".join(missing))
        return {name: sha256_file(path) for name, path in paths.items()}

    def execute(
        self,
        preparation: Phase23Preparation,
        *,
        read_authority: Phase23ReadAuthority | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> dict[str, object]:
        fresh = self.prepare(as_of_date=preparation.as_of_date, broker=preparation.broker)
        if fresh.scope_payload() != preparation.scope_payload():
            raise Phase23CurrentRunError("Phase 23 preparation became stale before execution")
        if preparation.challenge is not None:
            require_phase23_read_authority(read_authority, challenge=preparation.challenge)
        elif read_authority is not None:
            raise Phase23CurrentRunError("Phase 23 local-only run does not accept unnecessary external-read authority")

        self._journal(preparation, "cycle", "STARTED")
        if progress is not None:
            progress(f"Phase 23 finalized analysis cycle: {preparation.as_of_date}")

        reference_fetches = self._refresh_reference(preparation)
        market_data = self._advance_market_data(preparation)
        features = self._advance_features(preparation)
        self._advance_discovery(preparation)

        market_regime = SplitOriginRegimeStateEngine(self.settings).build(preparation.as_of_date)
        ticker_regime = TickerStateEngine(self.settings).build(preparation.as_of_date)

        study = StrategyHistoricalStudy(self.settings)
        strategy_store = Phase23CurrentStrategyHandoffStore(self.settings)
        strategy_store.verify_frozen_study(study.report_path)
        candidates = CurrentCandidateMaterializer(self.settings)
        current = candidates.materialize(
            preparation.as_of_date,
            historical_study_path=study.report_path,
        )
        strategy_handoff = strategy_store.write(
            as_of_date=preparation.as_of_date,
            historical_study_path=study.report_path,
            current_manifest_path=candidates.manifest_path(preparation.as_of_date),
        )
        if strategy_handoff.promoted_count != 0:
            raise Phase23CurrentRunError(
                "Phase 23 v1 frozen support unexpectedly produced promotions; policy replacement is required"
            )

        phase12 = Phase12Closeout(self.settings).run(as_of_date=preparation.as_of_date)
        if phase12.get("pass") is not True or int(phase12.get("research_case_count", -1)) != 0:
            raise Phase23CurrentRunError("Phase 23 frozen zero-promotion path did not remain a Phase 12 no-op")
        phase13 = Phase13Closeout(self.settings).run(as_of_date=preparation.as_of_date)
        if phase13.get("pass") is not True or int(phase13.get("case_file_count", -1)) != 0:
            raise Phase23CurrentRunError("Phase 23 zero-research path did not remain a Phase 13 no-op")
        phase14 = Phase14Closeout(self.settings).run(as_of_date=preparation.as_of_date)
        if phase14.get("pass") is not True or int(phase14.get("ai_review_count", -1)) != 0:
            raise Phase23CurrentRunError("Phase 23 zero-case path did not remain a Phase 14 no-op")
        if bool(phase14.get("provider_initialized")) or int(phase14.get("provider_calls", -1)) != 0:
            raise Phase23CurrentRunError("Phase 23 zero-case path unexpectedly initialized/called AI provider")

        phase12_path = Path(str(phase12["report_path"]))
        phase13_path = Path(str(phase13["report_path"]))
        phase14_path = Path(str(phase14["report_path"]))
        stage_hashes = self._stage_hashes(
            preparation,
            market_regime_path=market_regime.snapshot_path,
            ticker_regime_path=ticker_regime.snapshot_path,
            current_candidate_manifest=candidates.manifest_path(preparation.as_of_date),
            strategy_handoff=strategy_handoff.path,
            phase12_acceptance=phase12_path,
            phase13_acceptance=phase13_path,
            phase14_acceptance=phase14_path,
        )
        analysis_handoff = Phase23AnalysisHandoffStore(self.settings).write(
            as_of_date=preparation.as_of_date,
            phase14_acceptance_path=phase14_path,
            stage_hashes=stage_hashes,
            sessions_advanced=preparation.sessions_to_advance,
            external_read_classes_used=preparation.external_read_classes,
        )
        phase15_input = Phase15ExecutionInputResolver(self.settings).resolve(preparation.as_of_date)
        if phase15_input.phase23_handoff is None:
            raise Phase23CurrentRunError("Phase 15 did not consume the Phase 23 current-analysis handoff")

        archive_hashes = {
            "strategy_handoff": self._archive(preparation, "phase23_strategy_handoff", strategy_handoff.path),
            "phase12": self._archive(preparation, "phase12_final_acceptance", phase12_path),
            "phase13": self._archive(preparation, "phase13_final_acceptance", phase13_path),
            "phase14": self._archive(preparation, "phase14_final_acceptance", phase14_path),
            "analysis_handoff": self._archive(preparation, "phase23_analysis_handoff", analysis_handoff.path),
        }
        source_payload = {
            "contract_version": PHASE23_RUN_MANIFEST_CONTRACT_VERSION,
            "phase23_policy_fingerprint": phase23_policy_fingerprint(),
            "run_scope_fingerprint": preparation.run_scope_fingerprint,
            "as_of_date": preparation.as_of_date.isoformat(),
            "broker": preparation.broker.value,
            "stage_hashes": stage_hashes,
            "archive_hashes": archive_hashes,
            "phase15_input_fingerprint": phase15_input.source_fingerprint,
        }
        manifest: dict[str, object] = {
            **source_payload,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(source_payload),
            "baseline_discovery_date": preparation.baseline_discovery_date.isoformat(),
            "sessions_advanced": [item.isoformat() for item in preparation.sessions_to_advance],
            "external_read_classes_used": list(preparation.external_read_classes),
            "reference_snapshots_fetched": reference_fetches,
            "market_data": market_data,
            "features": features,
            "current_considered_warm_hot_directional": int(current["considered_warm_hot_directional"]),
            "promoted_count": int(current["promoted_count"]),
            "phase12_research_case_count": int(phase12["research_case_count"]),
            "phase13_case_file_count": int(phase13["case_file_count"]),
            "phase13_review_ready_count": int(phase13["phase14_review_ready_count"]),
            "phase14_ai_review_count": int(phase14["ai_review_count"]),
            "phase14_provider_calls": int(phase14["provider_calls"]),
            "phase22_ready_execution_case_count": phase15_input.execution_case_count,
            "historical_strategy_study_rerun": False,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automatic_broker_failover": False,
            "pass": True,
        }
        path = self.manifest_path(preparation.as_of_date, preparation.broker)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n")
        manifest["manifest_path"] = str(path.resolve())
        self._journal(preparation, "cycle", "COMPLETE", phase22_ready_execution_case_count=phase15_input.execution_case_count)
        return manifest
