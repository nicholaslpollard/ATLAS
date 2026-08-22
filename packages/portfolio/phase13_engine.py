from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.exceptions import ProviderError, SecretNotFoundError
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.instruments.engine import build_instrument_selection
from packages.news.sentiment import summarize_massive_news, unavailable_news_context
from packages.portfolio.phase13_policy import (
    PHASE13_BROKER_WRITES,
    PHASE13_NEWS_LOOKBACK_CALENDAR_DAYS,
    PHASE13_ORDER_WRITES,
    PHASE13_PRODUCTION_ML_WRITES,
    phase13_policy_fingerprint,
    phase13_policy_payload,
)
from packages.portfolio.phase13_source import Phase13PlanningInput, Phase13PlanningInputResolver
from packages.portfolio.thesis import build_trade_geometry
from packages.providers.massive.phase13 import MassivePhase13ResearchClient
from packages.providers.massive.rest import MassiveRESTClient
from packages.risk.engine import evaluate_portfolio_risk
from packages.schemas.case_file import (
    Phase13CaseFile,
    PortfolioRiskStatus,
    PortfolioSnapshot,
)
from packages.schemas.deep_research import DeepResearchCase


PHASE13_MANIFEST_CONTRACT_VERSION = (
    "phase13-manifest-v1-accepted-phase12-context-equity-geometry-portfolio-risk"
)
PHASE13_NO_CASE_DISPOSITION = "NO_ACCEPTED_PHASE12_RESEARCH_CASES"


class Phase13EngineError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_portfolio_snapshot(path: Path) -> PortfolioSnapshot:
    if not path.is_file():
        raise Phase13EngineError(f"portfolio snapshot does not exist: {path}")
    try:
        return PortfolioSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise Phase13EngineError(f"portfolio snapshot is invalid: {path}") from exc


class Phase13CaseEngine:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.input_resolver = Phase13PlanningInputResolver(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "case_files" / "phase13" / "v1"

    def manifest_path(self, as_of_date: date) -> Path:
        return self.root / "manifests" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

    def case_dir(self, as_of_date: date, instrument_id: str) -> Path:
        safe = hashlib.sha256(instrument_id.encode("utf-8")).hexdigest()[:20]
        return self.root / "cases" / f"year={as_of_date.year:04d}" / f"date={as_of_date}" / safe

    @staticmethod
    def _latest_exchange_session_on_or_before(today: date) -> date:
        calendar = get_market_calendar()
        sessions = calendar.sessions_in_range(today - timedelta(days=10), today)
        if not sessions:
            raise Phase13EngineError("unable to resolve latest exchange session")
        return sessions[-1]

    @staticmethod
    def _news_window(as_of_date: date) -> tuple[datetime, datetime]:
        _, cutoff = get_market_calendar().regular_open_close(as_of_date)
        return cutoff - timedelta(days=PHASE13_NEWS_LOOKBACK_CALENDAR_DAYS), cutoff

    def _current_rows(self, planning_input: Phase13PlanningInput) -> dict[str, dict[str, float]]:
        if not planning_input.research_cases:
            return {}
        tickers = [item.ticker for item in planning_input.research_cases]
        con = connect_utc(":memory:")
        try:
            con.register("phase13_symbols", pd.DataFrame({"symbol": tickers}))
            frame = con.execute(
                f"""
                SELECT f.symbol,
                       CAST(f.natr_14 AS DOUBLE) AS natr_14,
                       CAST(b.close AS DOUBLE) AS reference_close
                FROM read_parquet({sql_string(planning_input.feature_path)}) AS f
                INNER JOIN read_parquet({sql_string(planning_input.canonical_path)}) AS b
                  ON f.symbol = b.symbol AND f.timestamp_utc = b.timestamp_utc
                INNER JOIN phase13_symbols AS s ON s.symbol = f.symbol
                ORDER BY f.symbol
                """
            ).fetch_df()
        finally:
            con.close()
        if frame["symbol"].duplicated().any():
            raise Phase13EngineError("Phase 13 current feature/canonical rows are duplicated")
        by_symbol = frame.set_index("symbol", drop=False)
        result: dict[str, dict[str, float]] = {}
        for case in planning_input.research_cases:
            if case.ticker not in by_symbol.index:
                raise Phase13EngineError(f"Phase 13 case is missing current evidence: {case.ticker}")
            row = by_symbol.loc[case.ticker]
            result[case.instrument_id] = {
                "natr_14": float(row["natr_14"]),
                "reference_close": float(row["reference_close"]),
            }
        return result

    def _provider(self) -> tuple[MassivePhase13ResearchClient | None, str | None]:
        try:
            return MassivePhase13ResearchClient(MassiveRESTClient(self.settings)), None
        except (SecretNotFoundError, ProviderError) as exc:
            return None, type(exc).__name__

    def _write_snapshot(self, path: Path, payload: object) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
        return sha256_file(path)

    def _case(
        self,
        *,
        research: DeepResearchCase,
        phase12_case_sha: str,
        current: dict[str, float],
        provider: MassivePhase13ResearchClient | None,
        provider_error: str | None,
        snapshot: PortfolioSnapshot | None,
        correlation_evidence: dict[str, float] | None,
        options_current_session_allowed: bool,
        provider_counts: dict[str, int],
    ) -> tuple[Phase13CaseFile, Path]:
        case_dir = self.case_dir(research.as_of_date, research.instrument_id)
        start_utc, cutoff_utc = self._news_window(research.as_of_date)

        if provider is None:
            news = unavailable_news_context(
                cutoff_utc=cutoff_utc,
                lookback_calendar_days=PHASE13_NEWS_LOOKBACK_CALENDAR_DAYS,
                reason=f"MASSIVE_PROVIDER_UNAVAILABLE_{provider_error or 'UNKNOWN'}",
            )
            option_items: list[dict[str, Any]] | None = None
            option_path = None
            option_sha = None
        else:
            provider_counts["news"] += 1
            try:
                news_items = provider.news(research.ticker, start_utc=start_utc, end_utc=cutoff_utc)
                news_path = case_dir / "news_snapshot.json"
                news_sha = self._write_snapshot(
                    news_path,
                    {
                        "ticker": research.ticker,
                        "start_utc": start_utc,
                        "cutoff_utc": cutoff_utc,
                        "results": news_items,
                    },
                )
                news = summarize_massive_news(
                    news_items,
                    ticker=research.ticker,
                    cutoff_utc=cutoff_utc,
                    lookback_calendar_days=PHASE13_NEWS_LOOKBACK_CALENDAR_DAYS,
                    snapshot_path=str(news_path.resolve()),
                    snapshot_sha256=news_sha,
                )
            except (ProviderError, ValueError) as exc:
                news = unavailable_news_context(
                    cutoff_utc=cutoff_utc,
                    lookback_calendar_days=PHASE13_NEWS_LOOKBACK_CALENDAR_DAYS,
                    reason=f"NEWS_PROVIDER_EVIDENCE_UNAVAILABLE_{type(exc).__name__}",
                )

            if options_current_session_allowed:
                provider_counts["options"] += 1
                try:
                    option_items = list(provider.option_chain(research.ticker, as_of_date=research.as_of_date))
                    option_snapshot = case_dir / "option_chain_snapshot.json"
                    option_sha = self._write_snapshot(
                        option_snapshot,
                        {"ticker": research.ticker, "as_of_date": research.as_of_date, "results": option_items},
                    )
                    option_path = str(option_snapshot.resolve())
                except (ProviderError, ValueError):
                    option_items = None
                    option_path = None
                    option_sha = None
            else:
                option_items = None
                option_path = None
                option_sha = None

        instrument = build_instrument_selection(
            ticker=research.ticker,
            as_of_date=research.as_of_date,
            direction=research.direction,
            option_snapshot_items=option_items,
            option_snapshot_path=option_path,
            option_snapshot_sha256=option_sha,
        )
        geometry = build_trade_geometry(
            research,
            reference_close=current["reference_close"],
            feature_values={"natr_14": current["natr_14"]},
        )
        correlation = None if correlation_evidence is None else correlation_evidence.get(research.instrument_id)
        risk = evaluate_portfolio_risk(
            geometry,
            instrument_id=research.instrument_id,
            ticker=research.ticker,
            snapshot=snapshot,
            max_abs_correlation=correlation,
        )
        ready = (
            research.research_complete
            and geometry.status.value == "AVAILABLE"
            and risk.status == PortfolioRiskStatus.ADMISSIBLE
        )
        reasons = [
            "ACCEPTED_PHASE12_RESEARCH_CASE",
            "NEWS_CONTEXT_CANNOT_MANUFACTURE_OR_VETO_CANDIDATE",
            "EQUITY_PRIMARY_OPTION_ALTERNATIVES_SUPPORTING_ONLY",
            "REFERENCE_GEOMETRY_NOT_ASSUMED_FILL",
            "BROKER_NEUTRAL_PORTFOLIO_RISK",
        ]
        if not options_current_session_allowed:
            reasons.append("OPTION_CHAIN_SKIPPED_AS_OF_NOT_LATEST_EXCHANGE_SESSION")
        reasons.append("PHASE14_REVIEW_READY" if ready else "PHASE14_REVIEW_NOT_READY")
        case = Phase13CaseFile(
            instrument_id=research.instrument_id,
            ticker=research.ticker,
            as_of_date=research.as_of_date,
            direction=research.direction,
            phase12_case_sha256=phase12_case_sha,
            phase12_research_complete=research.research_complete,
            market_state=research.market_state,
            ticker_state=research.ticker_state,
            news_context=news,
            instrument_selection=instrument,
            geometry=geometry,
            portfolio_risk=risk,
            phase14_review_ready=ready,
            reason_codes=tuple(reasons),
        )
        case_path = case_dir / "case_file.json"
        case_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(case_path, case.model_dump_json(indent=2) + "\n")
        return case, case_path

    def run(
        self,
        *,
        as_of_date: date | None = None,
        portfolio_snapshot_path: Path | None = None,
        correlation_evidence: dict[str, float] | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> dict[str, object]:
        planning_input = self.input_resolver.resolve(as_of_date)
        policy = phase13_policy_payload()
        policy_fp = phase13_policy_fingerprint()
        provider_counts = {"news": 0, "options": 0}
        portfolio_reads = 0

        if planning_input.case_count == 0:
            provider_initialized = False
            portfolio_snapshot = None
            provider_error = None
            case_records: list[dict[str, object]] = []
            cases: list[Phase13CaseFile] = []
            if progress is not None:
                progress("no accepted Phase 12 research cases; context/options/portfolio reads skipped")
        else:
            if portfolio_snapshot_path is not None:
                portfolio_snapshot = _read_portfolio_snapshot(portfolio_snapshot_path)
                portfolio_reads = 1
            else:
                portfolio_snapshot = None
            provider, provider_error = self._provider()
            provider_initialized = provider is not None
            current_rows = self._current_rows(planning_input)
            latest_session = self._latest_exchange_session_on_or_before(datetime.now(UTC).date())
            options_allowed = planning_input.as_of_date == latest_session
            cases = []
            case_records = []
            for index, (research, case_sha) in enumerate(
                zip(planning_input.research_cases, planning_input.research_case_sha256, strict=True),
                start=1,
            ):
                if progress is not None:
                    progress(f"Phase 13 case {index}/{planning_input.case_count}: {research.ticker}")
                case, path = self._case(
                    research=research,
                    phase12_case_sha=case_sha,
                    current=current_rows[research.instrument_id],
                    provider=provider,
                    provider_error=provider_error,
                    snapshot=portfolio_snapshot,
                    correlation_evidence=correlation_evidence,
                    options_current_session_allowed=options_allowed,
                    provider_counts=provider_counts,
                )
                cases.append(case)
                case_records.append(
                    {
                        "instrument_id": case.instrument_id,
                        "ticker": case.ticker,
                        "phase14_review_ready": case.phase14_review_ready,
                        "geometry_status": case.geometry.status.value,
                        "portfolio_risk_status": case.portfolio_risk.status.value,
                        "case_path": str(path.resolve()),
                        "case_sha256": sha256_file(path),
                    }
                )

        snapshot_sha = None
        if planning_input.case_count and portfolio_snapshot_path is not None:
            snapshot_sha = sha256_file(portfolio_snapshot_path)
        source_payload = {
            "contract_version": PHASE13_MANIFEST_CONTRACT_VERSION,
            "as_of_date": planning_input.as_of_date.isoformat(),
            "phase13_input_fingerprint": planning_input.source_fingerprint,
            "policy_fingerprint": policy_fp,
            "case_hashes": [item["case_sha256"] for item in case_records],
            "portfolio_snapshot_sha256": snapshot_sha,
        }
        manifest: dict[str, object] = {
            "contract_version": PHASE13_MANIFEST_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(source_payload),
            "as_of_date": planning_input.as_of_date.isoformat(),
            "phase13_input": planning_input.public_dict(),
            "policy": policy,
            "policy_fingerprint": policy_fp,
            "phase12_case_count": planning_input.case_count,
            "case_file_count": len(cases),
            "phase14_review_ready_count": sum(1 for item in cases if item.phase14_review_ready),
            "cases": case_records,
            "no_case_disposition": PHASE13_NO_CASE_DISPOSITION if planning_input.case_count == 0 else None,
            "provider_initialized": provider_initialized,
            "news_provider_calls": provider_counts["news"],
            "option_chain_provider_calls": provider_counts["options"],
            "portfolio_snapshot_reads": portfolio_reads,
            "portfolio_snapshot_sha256": snapshot_sha,
            "correlation_evidence_supplied": correlation_evidence is not None,
            "production_ml_writes": PHASE13_PRODUCTION_ML_WRITES,
            "broker_writes": PHASE13_BROKER_WRITES,
            "order_writes": PHASE13_ORDER_WRITES,
            "execution_present": False,
            "pass": True,
        }
        path = self.manifest_path(planning_input.as_of_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n")
        manifest["manifest_path"] = str(path.resolve())
        return manifest
