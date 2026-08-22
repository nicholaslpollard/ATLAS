from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from packages.analogues.engine import (
    PHASE12_NO_CANDIDATE_DISPOSITION,
    PHASE12_RESEARCH_MANIFEST_CONTRACT_VERSION,
    DeepCandidateResearchEngine,
)
from packages.analogues.policy import (
    PHASE12_ANALOGUE_TOP_K,
    PHASE12_BOOTSTRAP_DRAWS,
    PHASE12_MIN_ANALOGUES_FOR_DISTRIBUTION,
    PHASE12_PER_INSTRUMENT_CAP,
    PHASE12_RESEARCH_POLICY_CONTRACT_VERSION,
    PHASE12_SIMILARITY_FEATURES,
    phase12_policy_payload,
)
from packages.analogues.scenarios import deterministic_seed
from packages.analogues.source import Phase12ResearchInputResolver
from packages.analogues.statistics import classify_quality, summarize_distribution
from packages.backtesting.historical_source import HistoricalStrategyResearchSourceResolver
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.schemas.deep_research import DeepResearchCase, EmpiricalPathScenarios, ScenarioQuantiles


PHASE12_VALIDATION_CONTRACT_VERSION = (
    "phase12-validation-v1-independent-input-selection-statistics-scenario-recompute"
)
PHASE12_FORBIDDEN_KEYS = {
    "entry",
    "entry_price",
    "stop",
    "stop_loss",
    "target",
    "take_profit",
    "quantity",
    "position_size",
    "broker",
    "order",
    "order_id",
    "option_contract",
    "strike",
    "expiration",
}


class Phase12ValidationError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase12ValidationError(f"missing {label}: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase12ValidationError(f"invalid JSON for {label}: {path}") from exc


def _forbidden_keys(payload: object, found: set[str] | None = None) -> set[str]:
    result = set() if found is None else found
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized = str(key).lower()
            if normalized in PHASE12_FORBIDDEN_KEYS:
                result.add(normalized)
            _forbidden_keys(value, result)
    elif isinstance(payload, list):
        for value in payload:
            _forbidden_keys(value, result)
    return result


def _scenario_quantiles(values: np.ndarray) -> ScenarioQuantiles:
    q = np.quantile(values, [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95])
    return ScenarioQuantiles(
        p05=float(q[0]),
        p10=float(q[1]),
        p25=float(q[2]),
        median=float(q[3]),
        p75=float(q[4]),
        p90=float(q[5]),
        p95=float(q[6]),
        mean=float(np.mean(values)),
    )


def _independent_scenarios(
    paths: pd.DataFrame,
    *,
    instrument_id: str,
    as_of_date: str,
    direction: str,
) -> EmpiricalPathScenarios:
    seed = deterministic_seed(instrument_id=instrument_id, as_of_date=as_of_date, direction=direction)
    if len(paths) < PHASE12_MIN_ANALOGUES_FOR_DISTRIBUTION:
        return EmpiricalPathScenarios(
            available=False,
            draw_count=0,
            seed=seed,
            source_path_rows=int(len(paths)),
            reason_codes=("PATH_ROWS_BELOW_PREREGISTERED_MINIMUM",),
        )
    matrix = paths[["direction_return_1", "direction_return_2", "direction_return_3"]].to_numpy(
        dtype="float64"
    )
    if not np.isfinite(matrix).all():
        raise Phase12ValidationError("persisted path evidence contains non-finite values")
    rng = np.random.default_rng(seed)
    sampled = matrix[
        rng.integers(0, len(matrix), size=PHASE12_BOOTSTRAP_DRAWS, endpoint=False)
    ]
    terminal = sampled[:, 2]
    mae = np.minimum(0.0, np.min(sampled, axis=1))
    mfe = np.maximum(0.0, np.max(sampled, axis=1))
    return EmpiricalPathScenarios(
        available=True,
        draw_count=PHASE12_BOOTSTRAP_DRAWS,
        seed=seed,
        source_path_rows=int(len(paths)),
        session_1=_scenario_quantiles(sampled[:, 0]),
        session_2=_scenario_quantiles(sampled[:, 1]),
        session_3=_scenario_quantiles(terminal),
        max_adverse_excursion=_scenario_quantiles(mae),
        max_favorable_excursion=_scenario_quantiles(mfe),
        terminal_positive_rate=float(np.mean(terminal > 0.0)),
        reason_codes=("DETERMINISTIC_EMPIRICAL_PATH_BOOTSTRAP_AVAILABLE",),
    )


def _independent_selection_sql(
    *,
    source_sql: str,
    as_of_date: date,
    market_state: str | None,
    current_features: dict[str, float],
) -> str:
    filters = [
        f'isfinite(CAST(h."{name}" AS DOUBLE))' for name in PHASE12_SIMILARITY_FEATURES
    ]
    stats: list[str] = []
    terms: list[str] = []
    for name in PHASE12_SIMILARITY_FEATURES:
        value = float(current_features[name])
        if not math.isfinite(value):
            raise Phase12ValidationError("non-finite current feature in persisted research case")
        stats.extend(
            (
                f'AVG(CAST("{name}" AS DOUBLE)) AS "m__{name}"',
                f'STDDEV_POP(CAST("{name}" AS DOUBLE)) AS "s__{name}"',
            )
        )
        terms.append(
            "CASE WHEN s.\"s__{0}\" IS NULL OR s.\"s__{0}\" = 0.0 THEN 0.0 "
            "ELSE POW((CAST(h.\"{0}\" AS DOUBLE) - {1}) / s.\"s__{0}\", 2) END".format(
                name, repr(value)
            )
        )
    market_clause = ""
    if market_state is not None and str(market_state).strip():
        market_clause = (
            " AND h.market_regime_available = TRUE"
            f" AND h.market_regime_composite = {sql_string(str(market_state).strip())}"
        )
    return f"""
        WITH eligible AS (
            SELECT * FROM {source_sql} AS h
            WHERE h.session_date < CAST({sql_string(as_of_date.isoformat())} AS DATE)
              AND h.future_date < CAST({sql_string(as_of_date.isoformat())} AS DATE)
              AND isfinite(CAST(h.forward_return AS DOUBLE))
              AND {' AND '.join(filters)}
              {market_clause}
        ),
        stats AS (SELECT {', '.join(stats)} FROM eligible),
        scored AS (
            SELECT
                h.observation_key,
                h.instrument_id,
                h.session_date,
                SQRT(({' + '.join(terms)}) / {len(PHASE12_SIMILARITY_FEATURES)}) AS distance
            FROM eligible AS h CROSS JOIN stats AS s
        ),
        capped AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY instrument_id
                ORDER BY distance ASC, session_date DESC, observation_key ASC
            ) AS irank
            FROM scored
        )
        SELECT observation_key, distance
        FROM capped
        WHERE irank <= {PHASE12_PER_INSTRUMENT_CAP}
        ORDER BY distance ASC, session_date DESC, observation_key ASC
        LIMIT {PHASE12_ANALOGUE_TOP_K}
    """


class Phase12IndependentValidator:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.engine = DeepCandidateResearchEngine(settings)
        self.input_resolver = Phase12ResearchInputResolver(settings)
        self.history_resolver = HistoricalStrategyResearchSourceResolver(settings)
        self.report_path = self.engine.root / "phase12_validation.json"

    def run(self, *, as_of_date: date) -> dict[str, object]:
        manifest_path = self.engine.manifest_path(as_of_date)
        manifest = _read_json(manifest_path, "Phase 12 research manifest")
        if manifest.get("contract_version") != PHASE12_RESEARCH_MANIFEST_CONTRACT_VERSION:
            raise Phase12ValidationError("Phase 12 research manifest contract changed")
        if manifest.get("pass") is not True:
            raise Phase12ValidationError("Phase 12 research manifest is not passing")
        research_input = self.input_resolver.resolve(as_of_date)
        if (
            dict(manifest.get("phase12_input") or {}).get("source_fingerprint")
            != research_input.source_fingerprint
        ):
            raise Phase12ValidationError("Phase 12 research input fingerprint changed")
        expected_policy = phase12_policy_payload()
        if manifest.get("policy") != expected_policy:
            raise Phase12ValidationError("Phase 12 preregistered policy changed")
        if manifest.get("policy_fingerprint") != _stable_hash(expected_policy):
            raise Phase12ValidationError("Phase 12 policy fingerprint changed")
        if (
            expected_policy["research_policy_contract_version"]
            != PHASE12_RESEARCH_POLICY_CONTRACT_VERSION
        ):
            raise Phase12ValidationError("Phase 12 policy contract mismatch")

        case_proofs: list[dict[str, object]] = []
        all_payloads: list[dict[str, Any]] = []
        if research_input.promoted_count == 0:
            if manifest.get("historical_source_accessed") is not False:
                raise Phase12ValidationError("zero-candidate Phase 12 run accessed expensive history")
            if int(manifest.get("research_case_count", -1)) != 0 or manifest.get("cases") != []:
                raise Phase12ValidationError("zero-candidate Phase 12 run produced research cases")
            if manifest.get("no_candidate_disposition") != PHASE12_NO_CANDIDATE_DISPOSITION:
                raise Phase12ValidationError("zero-candidate Phase 12 disposition changed")
            history_reverified = True
        else:
            history = self.history_resolver.resolve()
            historical = dict(manifest.get("historical_research_source") or {})
            if historical.get("source_fingerprint") != history.source_fingerprint:
                raise Phase12ValidationError("Phase 12 historical source fingerprint changed")
            history_reverified = True
            by_id = {item.instrument_id: item for item in research_input.promoted_candidates}
            records = manifest.get("cases")
            if not isinstance(records, list) or len(records) != research_input.promoted_count:
                raise Phase12ValidationError("Phase 12 case count differs from Phase 11 promotions")

            con = connect_utc(":memory:")
            try:
                feature_projection = ", ".join(
                    f'"{name}"' for name in PHASE12_SIMILARITY_FEATURES
                )
                for record in records:
                    if not isinstance(record, dict):
                        raise Phase12ValidationError("malformed Phase 12 case manifest record")
                    case_path = Path(str(record["case_path"]))
                    if sha256_file(case_path) != str(record["case_sha256"]):
                        raise Phase12ValidationError("Phase 12 case artifact hash changed")
                    payload = _read_json(case_path, "Phase 12 research case")
                    case = DeepResearchCase.model_validate(payload)
                    all_payloads.append(payload)
                    candidate = by_id.get(case.instrument_id)
                    if candidate is None or candidate.ticker != case.ticker:
                        raise Phase12ValidationError("Phase 12 case is not an exact Phase 11 promotion")
                    expected_candidate_sha = hashlib.sha256(
                        candidate.model_dump_json().encode("utf-8")
                    ).hexdigest()
                    if case.phase11_candidate_sha256 != expected_candidate_sha:
                        raise Phase12ValidationError("Phase 12 case candidate binding changed")
                    if case.research_source_fingerprint != history.source_fingerprint:
                        raise Phase12ValidationError("Phase 12 case uses a different historical source")

                    analogue_path = Path(case.analogue_artifact_path)
                    path_path = Path(case.path_artifact_path)
                    if sha256_file(analogue_path) != case.analogue_artifact_sha256:
                        raise Phase12ValidationError("Phase 12 analogue artifact hash changed")
                    if sha256_file(path_path) != case.path_artifact_sha256:
                        raise Phase12ValidationError("Phase 12 path artifact hash changed")
                    analogues = con.execute(
                        f"SELECT * FROM read_parquet({sql_string(analogue_path)}) "
                        "ORDER BY distance, session_date DESC, observation_key"
                    ).fetch_df()
                    paths = con.execute(
                        f"SELECT * FROM read_parquet({sql_string(path_path)}) ORDER BY observation_key"
                    ).fetch_df()
                    recomputed_distribution = summarize_distribution(analogues)
                    recomputed_quality = classify_quality(analogues, paths)
                    if recomputed_distribution != case.analogue_distribution:
                        raise Phase12ValidationError(
                            "Phase 12 analogue distribution did not independently recompute"
                        )
                    if recomputed_quality != case.analogue_quality:
                        raise Phase12ValidationError(
                            "Phase 12 analogue quality did not independently recompute"
                        )
                    recomputed_scenarios = _independent_scenarios(
                        paths,
                        instrument_id=case.instrument_id,
                        as_of_date=case.as_of_date.isoformat(),
                        direction=case.direction.value,
                    )
                    if recomputed_scenarios != case.scenarios:
                        raise Phase12ValidationError(
                            "Phase 12 scenarios did not independently recompute"
                        )

                    current = con.execute(
                        f"SELECT {feature_projection} "
                        f"FROM read_parquet({sql_string(research_input.feature_path)}) "
                        f"WHERE symbol = {sql_string(case.ticker)}"
                    ).fetchone()
                    if current is None:
                        raise Phase12ValidationError("Phase 12 current feature vector disappeared")
                    for name, value in zip(PHASE12_SIMILARITY_FEATURES, current, strict=True):
                        if abs(float(value) - float(case.current_feature_values[name])) > 1e-12:
                            raise Phase12ValidationError("Phase 12 current feature evidence changed")

                    selection = con.execute(
                        _independent_selection_sql(
                            source_sql=history.source_sql,
                            as_of_date=as_of_date,
                            market_state=case.market_state,
                            current_features=case.current_feature_values,
                        )
                    ).fetch_df()
                    if selection["observation_key"].astype(str).tolist() != analogues[
                        "observation_key"
                    ].astype(str).tolist():
                        raise Phase12ValidationError(
                            "Phase 12 top analogue selection did not independently recompute"
                        )
                    if len(selection) and not np.allclose(
                        selection["distance"].to_numpy(dtype="float64"),
                        analogues["distance"].to_numpy(dtype="float64"),
                        rtol=0.0,
                        atol=1e-12,
                    ):
                        raise Phase12ValidationError("Phase 12 analogue distances changed")
                    case_proofs.append(
                        {
                            "instrument_id": case.instrument_id,
                            "ticker": case.ticker,
                            "analogue_count": len(analogues),
                            "path_count": len(paths),
                            "selection_recomputed_exact": True,
                            "distribution_recomputed_exact": True,
                            "scenario_recomputed_exact": True,
                        }
                    )
            finally:
                con.close()

        checks = {
            "accepted_phase11_input_reverified": True,
            "preregistered_policy_exact": True,
            "promoted_only_scope_exact": int(manifest.get("promoted_input_count", -1))
            == research_input.promoted_count,
            "accepted_gate11c_history_reverified_or_not_needed": history_reverified,
            "zero_candidate_path_skips_expensive_history": (
                research_input.promoted_count != 0
                or manifest.get("historical_source_accessed") is False
            ),
            "case_evidence_independently_recomputed": len(case_proofs)
            == research_input.promoted_count,
            "research_only_not_trade_signal": manifest.get("research_only_not_trade_signal") is True,
            "no_trade_or_order_geometry": not _forbidden_keys(manifest)
            and all(not _forbidden_keys(payload) for payload in all_payloads),
            "production_ml_writes_zero": int(manifest.get("production_ml_writes", -1)) == 0,
            "broker_writes_zero": int(manifest.get("broker_writes", -1)) == 0,
        }
        source_payload = {
            "contract_version": PHASE12_VALIDATION_CONTRACT_VERSION,
            "as_of_date": as_of_date.isoformat(),
            "research_manifest_sha256": sha256_file(manifest_path),
            "phase12_input_fingerprint": research_input.source_fingerprint,
            "policy_fingerprint": manifest["policy_fingerprint"],
            "case_proofs": case_proofs,
            "checks": checks,
        }
        report: dict[str, object] = {
            "contract_version": PHASE12_VALIDATION_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(source_payload),
            "as_of_date": as_of_date.isoformat(),
            "research_manifest_sha256": sha256_file(manifest_path),
            "phase12_input_fingerprint": research_input.source_fingerprint,
            "case_proofs": case_proofs,
            "checks": checks,
            "production_ml_writes": 0,
            "broker_writes": 0,
            "pass": all(bool(value) for value in checks.values()),
        }
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.report_path,
            json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        )
        report["report_path"] = str(self.report_path.resolve())
        return report
