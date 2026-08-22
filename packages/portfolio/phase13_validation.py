from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.instruments.engine import build_instrument_selection
from packages.news.sentiment import summarize_massive_news
from packages.portfolio.phase13_engine import (
    PHASE13_MANIFEST_CONTRACT_VERSION,
    PHASE13_NO_CASE_DISPOSITION,
    Phase13CaseEngine,
)
from packages.portfolio.phase13_policy import (
    PHASE13_BROKER_WRITES,
    PHASE13_NEWS_LOOKBACK_CALENDAR_DAYS,
    PHASE13_ORDER_WRITES,
    PHASE13_PRODUCTION_ML_WRITES,
    phase13_policy_fingerprint,
    phase13_policy_payload,
)
from packages.portfolio.phase13_source import Phase13PlanningInputResolver
from packages.portfolio.thesis import build_trade_geometry
from packages.risk.engine import evaluate_portfolio_risk
from packages.schemas.case_file import (
    EvidenceAvailability,
    Phase13CaseFile,
    PortfolioSnapshot,
)


PHASE13_VALIDATION_CONTRACT_VERSION = (
    "phase13-validation-v1-independent-input-context-instrument-geometry-risk-recompute"
)
PHASE13_FORBIDDEN_EXECUTION_KEYS = {
    "broker",
    "broker_id",
    "order_id",
    "client_order_id",
    "fill_id",
    "execution_id",
    "submitted_at",
    "filled_at",
}


class Phase13ValidationError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase13ValidationError(f"missing {label}: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase13ValidationError(f"invalid JSON for {label}: {path}") from exc


def _forbidden_execution_keys(payload: object, found: set[str] | None = None) -> set[str]:
    result = set() if found is None else found
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized = str(key).lower()
            if normalized in PHASE13_FORBIDDEN_EXECUTION_KEYS:
                result.add(normalized)
            _forbidden_execution_keys(value, result)
    elif isinstance(payload, list):
        for value in payload:
            _forbidden_execution_keys(value, result)
    return result


def _portfolio_snapshot(path: Path | None) -> PortfolioSnapshot | None:
    if path is None:
        return None
    if not path.is_file():
        raise Phase13ValidationError(f"portfolio snapshot is missing: {path}")
    return PortfolioSnapshot.model_validate_json(path.read_text(encoding="utf-8"))


class Phase13IndependentValidator:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.engine = Phase13CaseEngine(settings)
        self.input_resolver = Phase13PlanningInputResolver(settings)
        self.report_path = self.engine.root / "phase13_validation.json"

    @staticmethod
    def _current_rows(planning_input: object) -> dict[str, dict[str, float]]:
        cases = planning_input.research_cases  # type: ignore[attr-defined]
        if not cases:
            return {}
        tickers = [item.ticker for item in cases]
        con = connect_utc(":memory:")
        try:
            con.register("phase13_validation_symbols", pd.DataFrame({"symbol": tickers}))
            frame = con.execute(
                f"""
                SELECT f.symbol, CAST(f.natr_14 AS DOUBLE) AS natr_14,
                       CAST(b.close AS DOUBLE) AS reference_close
                FROM read_parquet({sql_string(planning_input.feature_path)}) AS f
                INNER JOIN read_parquet({sql_string(planning_input.canonical_path)}) AS b
                  ON f.symbol = b.symbol AND f.timestamp_utc = b.timestamp_utc
                INNER JOIN phase13_validation_symbols AS s ON s.symbol = f.symbol
                ORDER BY f.symbol
                """
            ).fetch_df()
        finally:
            con.close()
        if frame["symbol"].duplicated().any():
            raise Phase13ValidationError("independent current evidence contains duplicate symbols")
        by_symbol = frame.set_index("symbol", drop=False)
        return {
            item.instrument_id: {
                "natr_14": float(by_symbol.loc[item.ticker]["natr_14"]),
                "reference_close": float(by_symbol.loc[item.ticker]["reference_close"]),
            }
            for item in cases
        }

    def run(
        self,
        *,
        as_of_date: date,
        portfolio_snapshot_path: Path | None = None,
        correlation_evidence: dict[str, float] | None = None,
    ) -> dict[str, object]:
        manifest_path = self.engine.manifest_path(as_of_date)
        manifest = _read_json(manifest_path, "Phase 13 manifest")
        if manifest.get("contract_version") != PHASE13_MANIFEST_CONTRACT_VERSION:
            raise Phase13ValidationError("Phase 13 manifest contract changed")
        if manifest.get("pass") is not True:
            raise Phase13ValidationError("Phase 13 manifest is not passing")
        planning_input = self.input_resolver.resolve(as_of_date)
        if dict(manifest.get("phase13_input") or {}).get("source_fingerprint") != planning_input.source_fingerprint:
            raise Phase13ValidationError("Phase 13 accepted input fingerprint changed")
        if manifest.get("policy") != phase13_policy_payload():
            raise Phase13ValidationError("Phase 13 preregistered policy changed")
        if manifest.get("policy_fingerprint") != phase13_policy_fingerprint():
            raise Phase13ValidationError("Phase 13 policy fingerprint changed")

        snapshot = _portfolio_snapshot(portfolio_snapshot_path)
        if portfolio_snapshot_path is None:
            if manifest.get("portfolio_snapshot_sha256") is not None:
                raise Phase13ValidationError("manifest claims a portfolio snapshot not supplied to validation")
        else:
            if manifest.get("portfolio_snapshot_sha256") != sha256_file(portfolio_snapshot_path):
                raise Phase13ValidationError("portfolio snapshot hash changed")
        if bool(manifest.get("correlation_evidence_supplied")) != (correlation_evidence is not None):
            raise Phase13ValidationError("correlation evidence presence changed")

        case_proofs: list[dict[str, object]] = []
        payloads: list[dict[str, Any]] = []
        if planning_input.case_count == 0:
            if int(manifest.get("case_file_count", -1)) != 0 or manifest.get("cases") != []:
                raise Phase13ValidationError("zero-input Phase 13 run produced case files")
            if manifest.get("no_case_disposition") != PHASE13_NO_CASE_DISPOSITION:
                raise Phase13ValidationError("zero-input Phase 13 disposition changed")
            if manifest.get("provider_initialized") is not False:
                raise Phase13ValidationError("zero-input Phase 13 initialized an external provider")
            if any(int(manifest.get(name, -1)) != 0 for name in (
                "news_provider_calls",
                "option_chain_provider_calls",
                "portfolio_snapshot_reads",
            )):
                raise Phase13ValidationError("zero-input Phase 13 performed external/account reads")
        else:
            current_rows = self._current_rows(planning_input)
            research_by_id = {item.instrument_id: item for item in planning_input.research_cases}
            sha_by_id = {
                item.instrument_id: digest
                for item, digest in zip(
                    planning_input.research_cases,
                    planning_input.research_case_sha256,
                    strict=True,
                )
            }
            records = manifest.get("cases")
            if not isinstance(records, list) or len(records) != planning_input.case_count:
                raise Phase13ValidationError("Phase 13 case records do not match accepted Phase 12 cases")
            for record in records:
                if not isinstance(record, dict):
                    raise Phase13ValidationError("malformed Phase 13 case record")
                case_path = Path(str(record["case_path"]))
                if sha256_file(case_path) != str(record["case_sha256"]):
                    raise Phase13ValidationError("Phase 13 case-file hash changed")
                payload = _read_json(case_path, "Phase 13 case file")
                payloads.append(payload)
                case = Phase13CaseFile.model_validate(payload)
                research = research_by_id.get(case.instrument_id)
                if research is None or research.ticker != case.ticker:
                    raise Phase13ValidationError("Phase 13 case is not an exact Phase 12 research case")
                if case.phase12_case_sha256 != sha_by_id[case.instrument_id]:
                    raise Phase13ValidationError("Phase 13 case lost Phase 12 artifact binding")

                current = current_rows[case.instrument_id]
                geometry = build_trade_geometry(
                    research,
                    reference_close=current["reference_close"],
                    feature_values={"natr_14": current["natr_14"]},
                )
                if geometry != case.geometry:
                    raise Phase13ValidationError("Phase 13 geometry did not independently recompute")

                news = case.news_context
                if news.availability == EvidenceAvailability.AVAILABLE and news.provider_snapshot_path:
                    news_path = Path(news.provider_snapshot_path)
                    if sha256_file(news_path) != news.provider_snapshot_sha256:
                        raise Phase13ValidationError("Phase 13 news snapshot hash changed")
                    raw = _read_json(news_path, "Phase 13 news snapshot")
                    recomputed_news = summarize_massive_news(
                        list(raw.get("results") or []),
                        ticker=case.ticker,
                        cutoff_utc=news.cutoff_utc,
                        lookback_calendar_days=PHASE13_NEWS_LOOKBACK_CALENDAR_DAYS,
                        snapshot_path=str(news_path.resolve()),
                        snapshot_sha256=sha256_file(news_path),
                    )
                    if recomputed_news != news:
                        raise Phase13ValidationError("Phase 13 news context did not independently recompute")

                instrument = case.instrument_selection
                if instrument.option_chain_availability == EvidenceAvailability.AVAILABLE:
                    if not instrument.option_chain_snapshot_path:
                        raise Phase13ValidationError("available option chain has no persisted snapshot")
                    option_path = Path(instrument.option_chain_snapshot_path)
                    if sha256_file(option_path) != instrument.option_chain_snapshot_sha256:
                        raise Phase13ValidationError("Phase 13 option snapshot hash changed")
                    raw_options = _read_json(option_path, "Phase 13 option snapshot")
                    recomputed_instrument = build_instrument_selection(
                        ticker=case.ticker,
                        as_of_date=case.as_of_date,
                        direction=case.direction,
                        option_snapshot_items=list(raw_options.get("results") or []),
                        option_snapshot_path=str(option_path.resolve()),
                        option_snapshot_sha256=sha256_file(option_path),
                    )
                else:
                    recomputed_instrument = build_instrument_selection(
                        ticker=case.ticker,
                        as_of_date=case.as_of_date,
                        direction=case.direction,
                        option_snapshot_items=None,
                    )
                if recomputed_instrument != instrument:
                    raise Phase13ValidationError("Phase 13 instrument selection did not independently recompute")

                correlation = None if correlation_evidence is None else correlation_evidence.get(case.instrument_id)
                risk = evaluate_portfolio_risk(
                    geometry,
                    instrument_id=case.instrument_id,
                    ticker=case.ticker,
                    snapshot=snapshot,
                    max_abs_correlation=correlation,
                )
                if risk != case.portfolio_risk:
                    raise Phase13ValidationError("Phase 13 portfolio risk did not independently recompute")
                case_proofs.append(
                    {
                        "instrument_id": case.instrument_id,
                        "ticker": case.ticker,
                        "geometry_recomputed_exact": True,
                        "instrument_recomputed_exact": True,
                        "portfolio_risk_recomputed_exact": True,
                        "phase14_review_ready": case.phase14_review_ready,
                    }
                )

        checks = {
            "accepted_phase12_input_reverified": True,
            "preregistered_policy_exact": True,
            "phase12_case_count_exact": int(manifest.get("phase12_case_count", -1)) == planning_input.case_count,
            "case_file_count_exact": int(manifest.get("case_file_count", -1)) == planning_input.case_count,
            "zero_case_path_skips_external_reads": (
                planning_input.case_count != 0
                or (
                    manifest.get("provider_initialized") is False
                    and int(manifest.get("news_provider_calls", -1)) == 0
                    and int(manifest.get("option_chain_provider_calls", -1)) == 0
                    and int(manifest.get("portfolio_snapshot_reads", -1)) == 0
                )
            ),
            "case_plans_independently_recomputed": len(case_proofs) == planning_input.case_count,
            "no_execution_artifacts": not _forbidden_execution_keys(manifest)
            and all(not _forbidden_execution_keys(payload) for payload in payloads),
            "production_ml_writes_zero": int(manifest.get("production_ml_writes", -1)) == 0
            and PHASE13_PRODUCTION_ML_WRITES == 0,
            "broker_writes_zero": int(manifest.get("broker_writes", -1)) == 0
            and PHASE13_BROKER_WRITES == 0,
            "order_writes_zero": int(manifest.get("order_writes", -1)) == 0
            and PHASE13_ORDER_WRITES == 0,
            "execution_absent": manifest.get("execution_present") is False,
        }
        report_payload = {
            "contract_version": PHASE13_VALIDATION_CONTRACT_VERSION,
            "as_of_date": as_of_date.isoformat(),
            "manifest_sha256": sha256_file(manifest_path),
            "phase13_input_fingerprint": planning_input.source_fingerprint,
            "case_proofs": case_proofs,
            "checks": checks,
        }
        report: dict[str, object] = {
            "contract_version": PHASE13_VALIDATION_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(report_payload),
            "as_of_date": as_of_date.isoformat(),
            "manifest_sha256": sha256_file(manifest_path),
            "phase13_input_fingerprint": planning_input.source_fingerprint,
            "case_proofs": case_proofs,
            "checks": checks,
            "production_ml_writes": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "pass": all(bool(value) for value in checks.values()),
        }
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        return report
