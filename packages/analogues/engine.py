from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from packages.analogues.outcomes import attach_direction_adjusted_returns, extract_directional_paths
from packages.analogues.policy import (
    PHASE12_BROKER_WRITES,
    PHASE12_PRODUCTION_ML_WRITES,
    PHASE12_RESEARCH_POLICY_CONTRACT_VERSION,
    PHASE12_SECTOR_POLICY,
    PHASE12_SIMILARITY_FEATURES,
    PHASE12_TICKER_REGIME_HISTORY_POLICY,
    PHASE12_TRADE_GEOMETRY_PRESENT,
    phase12_policy_payload,
)
from packages.analogues.scenarios import build_empirical_path_scenarios
from packages.analogues.similarity import select_analogues
from packages.analogues.source import Phase12ResearchInput, Phase12ResearchInputResolver
from packages.analogues.statistics import classify_quality, summarize_distribution
from packages.backtesting.historical_source import HistoricalStrategyResearchSourceResolver
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.schemas.candidate_promotion import CandidatePromotionRecord
from packages.schemas.deep_research import DeepResearchCase


PHASE12_RESEARCH_MANIFEST_CONTRACT_VERSION = (
    "phase12-research-manifest-v1-promoted-only-analogue-distribution-path-scenarios"
)
PHASE12_NO_CANDIDATE_DISPOSITION = "NO_PHASE11_PROMOTED_CANDIDATES"


class DeepResearchError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _record_sha(record: CandidatePromotionRecord) -> str:
    return hashlib.sha256(record.model_dump_json().encode("utf-8")).hexdigest()


class DeepCandidateResearchEngine:
    """Run expensive analogue/path research only for accepted Phase 11 promotions."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.input_resolver = Phase12ResearchInputResolver(settings)
        self.history_resolver = HistoricalStrategyResearchSourceResolver(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "deep_research" / "phase12" / "v1"

    def manifest_path(self, as_of_date: date) -> Path:
        return self.root / "manifests" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

    def candidate_dir(self, as_of_date: date, instrument_id: str) -> Path:
        safe = hashlib.sha256(instrument_id.encode("utf-8")).hexdigest()[:20]
        return self.root / "cases" / f"year={as_of_date.year:04d}" / f"date={as_of_date}" / safe

    def _write_parquet(self, frame: pd.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(path)
        con = connect_utc(":memory:")
        try:
            con.register("phase12_output", frame)
            compression = self.settings.data.parquet.compression.upper()
            row_group_size = int(self.settings.data.parquet.row_group_size)
            con.execute(
                f"""
                COPY (SELECT * FROM phase12_output)
                TO {sql_string(temp)}
                (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
                """
            )
            promote(temp, path)
        finally:
            con.close()

    def _current_feature_vectors(
        self,
        research_input: Phase12ResearchInput,
    ) -> dict[str, dict[str, float]]:
        if not research_input.promoted_candidates:
            return {}
        symbols = [item.ticker for item in research_input.promoted_candidates]
        con = connect_utc(":memory:")
        try:
            con.register("phase12_symbols", pd.DataFrame({"symbol": symbols}))
            feature_select = ", ".join(f'f."{name}"' for name in PHASE12_SIMILARITY_FEATURES)
            frame = con.execute(
                f"""
                SELECT f.symbol, {feature_select}
                FROM read_parquet({sql_string(research_input.feature_path)}) AS f
                INNER JOIN phase12_symbols AS s ON s.symbol = f.symbol
                ORDER BY f.symbol
                """
            ).fetch_df()
        finally:
            con.close()
        if frame["symbol"].duplicated().any():
            raise DeepResearchError("current Phase 12 feature vectors contain duplicate symbols")
        by_symbol = frame.set_index("symbol", drop=False)
        result: dict[str, dict[str, float]] = {}
        for candidate in research_input.promoted_candidates:
            if candidate.ticker not in by_symbol.index:
                raise DeepResearchError(f"promoted candidate is missing current features: {candidate.ticker}")
            row = by_symbol.loc[candidate.ticker]
            values = {name: float(row[name]) for name in PHASE12_SIMILARITY_FEATURES}
            if not all(math.isfinite(value) for value in values.values()):
                raise DeepResearchError(f"promoted candidate has non-finite Phase 12 features: {candidate.ticker}")
            result[candidate.instrument_id] = values
        return result

    def _run_candidate(
        self,
        *,
        candidate: CandidatePromotionRecord,
        research_input: Phase12ResearchInput,
        research_source: object,
        current_features: dict[str, float],
    ) -> tuple[DeepResearchCase, Path]:
        con = connect_utc(":memory:")
        try:
            analogues, eligible_pool_rows = select_analogues(
                con,
                source_sql=research_source.source_sql,  # type: ignore[attr-defined]
                as_of_date=research_input.as_of_date,
                market_state=candidate.market_state,
                current_features=current_features,
            )
            analogues = attach_direction_adjusted_returns(
                analogues,
                direction=candidate.discovery_direction,
            )
            paths = extract_directional_paths(
                con,
                source_sql=research_source.source_sql,  # type: ignore[attr-defined]
                analogue_frame=analogues,
                direction=candidate.discovery_direction,
            )
        finally:
            con.close()

        case_dir = self.candidate_dir(research_input.as_of_date, candidate.instrument_id)
        analogue_path = case_dir / "analogues.parquet"
        path_path = case_dir / "paths.parquet"
        self._write_parquet(analogues, analogue_path)
        self._write_parquet(paths, path_path)
        distribution = summarize_distribution(analogues)
        quality = classify_quality(analogues, paths)
        scenarios = build_empirical_path_scenarios(
            paths,
            instrument_id=candidate.instrument_id,
            as_of_date=research_input.as_of_date.isoformat(),
            direction=candidate.discovery_direction.value,
        )
        research_complete = quality.status != "INSUFFICIENT" and scenarios.available
        reasons = [
            "PHASE11_PROMOTED_RESEARCH_CASE",
            "ACCEPTED_GATE11C_C_COMPOSITE_ANALOGUE_SOURCE",
            "MARKET_REGIME_MATCHED_WHEN_AVAILABLE",
            "TICKER_REGIME_NOT_RETROJECTED_INTO_PRE2021_HISTORY",
            "EMPIRICAL_THREE_SESSION_DIRECTION_ADJUSTED_OUTCOMES",
        ]
        reasons.append("DEEP_RESEARCH_COMPLETE" if research_complete else "DEEP_RESEARCH_EVIDENCE_LIMITED")
        case = DeepResearchCase(
            instrument_id=candidate.instrument_id,
            ticker=candidate.ticker,
            as_of_date=research_input.as_of_date,
            direction=candidate.discovery_direction,
            market_state=candidate.market_state,
            ticker_state=candidate.ticker_state,
            phase11_candidate_sha256=_record_sha(candidate),
            research_source_fingerprint=research_source.source_fingerprint,  # type: ignore[attr-defined]
            similarity_feature_names=PHASE12_SIMILARITY_FEATURES,
            current_feature_values=current_features,
            eligible_pool_rows=eligible_pool_rows,
            analogue_distribution=distribution,
            analogue_quality=quality,
            scenarios=scenarios,
            analogue_artifact_path=str(analogue_path.resolve()),
            analogue_artifact_sha256=sha256_file(analogue_path),
            path_artifact_path=str(path_path.resolve()),
            path_artifact_sha256=sha256_file(path_path),
            research_complete=research_complete,
            reason_codes=tuple(reasons),
        )
        case_path = case_dir / "research.json"
        atomic_write_text(case_path, case.model_dump_json(indent=2) + "\n")
        return case, case_path

    def run(
        self,
        *,
        as_of_date: date | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> dict[str, object]:
        research_input = self.input_resolver.resolve(as_of_date)
        policy = phase12_policy_payload()
        policy_fingerprint = _stable_hash(policy)

        if research_input.promoted_count == 0:
            cases: list[DeepResearchCase] = []
            case_records: list[dict[str, object]] = []
            research_source_public: dict[str, object] | None = None
            historical_source_accessed = False
            if progress is not None:
                progress("no Phase 11 promoted candidates; expensive historical research skipped")
        else:
            if progress is not None:
                progress(
                    f"resolving accepted Gate 11-C research history for {research_input.promoted_count} promoted candidates"
                )
            research_source = self.history_resolver.resolve()
            research_source_public = research_source.public_dict()
            historical_source_accessed = True
            vectors = self._current_feature_vectors(research_input)
            cases = []
            case_records = []
            for index, candidate in enumerate(research_input.promoted_candidates, start=1):
                if progress is not None:
                    progress(
                        f"deep research {index}/{research_input.promoted_count}: {candidate.ticker} ({candidate.discovery_direction.value})"
                    )
                case, case_path = self._run_candidate(
                    candidate=candidate,
                    research_input=research_input,
                    research_source=research_source,
                    current_features=vectors[candidate.instrument_id],
                )
                cases.append(case)
                case_records.append(
                    {
                        "instrument_id": case.instrument_id,
                        "ticker": case.ticker,
                        "research_complete": case.research_complete,
                        "quality_status": case.analogue_quality.status,
                        "analogue_count": case.analogue_quality.analogue_count,
                        "case_path": str(case_path.resolve()),
                        "case_sha256": sha256_file(case_path),
                        "analogue_sha256": case.analogue_artifact_sha256,
                        "path_sha256": case.path_artifact_sha256,
                    }
                )

        manifest_payload = {
            "contract_version": PHASE12_RESEARCH_MANIFEST_CONTRACT_VERSION,
            "as_of_date": research_input.as_of_date.isoformat(),
            "phase12_input_fingerprint": research_input.source_fingerprint,
            "policy_fingerprint": policy_fingerprint,
            "historical_source_accessed": historical_source_accessed,
            "research_source_fingerprint": None
            if research_source_public is None
            else research_source_public["source_fingerprint"],
            "case_hashes": [item["case_sha256"] for item in case_records],
        }
        manifest: dict[str, object] = {
            "contract_version": PHASE12_RESEARCH_MANIFEST_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(manifest_payload),
            "as_of_date": research_input.as_of_date.isoformat(),
            "phase12_input": research_input.public_dict(),
            "policy": policy,
            "policy_fingerprint": policy_fingerprint,
            "promoted_input_count": research_input.promoted_count,
            "historical_source_accessed": historical_source_accessed,
            "historical_research_source": research_source_public,
            "research_case_count": len(cases),
            "research_complete_count": sum(1 for case in cases if case.research_complete),
            "research_limited_count": sum(1 for case in cases if not case.research_complete),
            "cases": case_records,
            "no_candidate_disposition": (
                PHASE12_NO_CANDIDATE_DISPOSITION if research_input.promoted_count == 0 else None
            ),
            "sector_context_policy": PHASE12_SECTOR_POLICY,
            "ticker_regime_history_policy": PHASE12_TICKER_REGIME_HISTORY_POLICY,
            "research_only_not_trade_signal": True,
            "trade_geometry_present": PHASE12_TRADE_GEOMETRY_PRESENT,
            "production_ml_writes": PHASE12_PRODUCTION_ML_WRITES,
            "broker_writes": PHASE12_BROKER_WRITES,
            "pass": True,
        }
        path = self.manifest_path(research_input.as_of_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n")
        manifest["manifest_path"] = str(path.resolve())
        return manifest
