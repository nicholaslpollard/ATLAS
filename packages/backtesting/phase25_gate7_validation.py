from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY

from .phase25_gate6 import Phase25Gate6DiscoveryReconstruction
from .phase25_gate6_validation import Phase25Gate6IndependentValidator
from .phase25_gate7 import (
    PHASE25_GATE7_CONTEXT_CONTRACT_VERSION,
    PHASE25_GATE7_REPORT_CONTRACT_VERSION,
    PHASE25_GATE7_ROUTE_CONTRACT_VERSION,
    Phase25Gate7RouteContextReplay,
)
from .phase25_gate7_policy import phase25_gate7_policy_fingerprint
from .phase25_policy import (
    PHASE25_BROKER_READS,
    PHASE25_BROKER_WRITES,
    PHASE25_LIVE_WRITES,
    PHASE25_ORDER_WRITES,
    PHASE25_PAPER_SUBMITS,
    PHASE25_PHASE11_SUPPORT_WRITES,
    PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
)


PHASE25_GATE7_VALIDATION_CONTRACT_VERSION = (
    "phase25-gate7-validation-v1-route-cardinality-lineage-authority"
)


class Phase25Gate7IndependentValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate7IndependentValidationError(f"missing JSON evidence: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate7IndependentValidationError(f"invalid JSON evidence: {path}") from exc
    if not isinstance(value, dict):
        raise Phase25Gate7IndependentValidationError(f"JSON evidence must be an object: {path}")
    return value


class Phase25Gate7IndependentValidator:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate7"

    def report_path(self, through_date: date) -> Path:
        return self.root / f"through={through_date}" / "independent_validation.json"

    def run(self, *, through_date: date) -> dict[str, object]:
        gate = Phase25Gate7RouteContextReplay(self.settings)
        gate7_path = gate.report_path(through_date)
        gate7 = _read_json(gate7_path)
        if gate7.get("contract_version") != PHASE25_GATE7_REPORT_CONTRACT_VERSION:
            raise Phase25Gate7IndependentValidationError("Gate7 report contract mismatch")
        if gate7.get("phase25_gate7_policy_fingerprint") != phase25_gate7_policy_fingerprint():
            raise Phase25Gate7IndependentValidationError("Gate7 policy fingerprint mismatch")
        if gate7.get("through_date") != through_date.isoformat() or gate7.get("pass") is not True:
            raise Phase25Gate7IndependentValidationError("Gate7 report is not passing for through-date")

        gate6 = Phase25Gate6DiscoveryReconstruction(self.settings)
        gate6_report = gate6.report_path(through_date)
        gate6_validation = Phase25Gate6IndependentValidator(self.settings).report_path(through_date)
        gate6_population = gate6.population_path(through_date)
        if gate7.get("gate6_report_sha256") != sha256_file(gate6_report):
            raise Phase25Gate7IndependentValidationError("Gate7 is not bound to exact Gate6 report")
        if gate7.get("gate6_validation_sha256") != sha256_file(gate6_validation):
            raise Phase25Gate7IndependentValidationError("Gate7 is not bound to exact Gate6 validation")
        if gate7.get("gate6_population_sha256") != sha256_file(gate6_population):
            raise Phase25Gate7IndependentValidationError("Gate7 is not bound to exact Gate6 population")

        context_path = gate.context_path(through_date)
        routes_path = gate.routes_path(through_date)
        if not context_path.is_file() or not routes_path.is_file():
            raise Phase25Gate7IndependentValidationError("Gate7 route artifacts are missing")
        if gate7.get("context_sha256") != sha256_file(context_path):
            raise Phase25Gate7IndependentValidationError("Gate7 context SHA mismatch")
        if gate7.get("routes_sha256") != sha256_file(routes_path):
            raise Phase25Gate7IndependentValidationError("Gate7 routes SHA mismatch")

        con = connect_utc(":memory:")
        try:
            context = con.execute(
                f"""
                SELECT
                    count(*) AS rows,
                    count(DISTINCT CAST(as_of_date AS VARCHAR) || ':' || instrument_id) AS unique_keys,
                    count(*) FILTER (WHERE contract_version <> ?) AS bad_contract,
                    count(*) FILTER (WHERE effective_state NOT IN ('warm', 'hot')) AS bad_state,
                    count(*) FILTER (WHERE direction NOT IN ('bullish', 'bearish')) AS bad_direction,
                    count(*) FILTER (WHERE market_state IS NULL) AS missing_market,
                    count(*) FILTER (WHERE sector_state IS NOT NULL) AS fabricated_sector
                FROM read_parquet({sql_string(context_path)})
                """,
                [PHASE25_GATE7_CONTEXT_CONTRACT_VERSION],
            ).fetchone()
            routes = con.execute(
                f"""
                SELECT
                    count(*) AS rows,
                    count(DISTINCT CAST(as_of_date AS VARCHAR) || ':' || instrument_id || ':' || strategy_id) AS unique_keys,
                    count(*) FILTER (WHERE contract_version <> ?) AS bad_contract,
                    count(*) FILTER (WHERE sector_state IS NOT NULL) AS fabricated_sector,
                    count(*) FILTER (WHERE sector_fit <> 'unavailable') AS bad_sector_fit,
                    count(*) FILTER (WHERE eligible AND NOT direction_match) AS eligible_direction_mismatch,
                    count(*) FILTER (WHERE eligible AND market_fit = 'blocked') AS eligible_market_blocked,
                    count(*) FILTER (WHERE eligible AND ticker_fit = 'blocked') AS eligible_ticker_blocked,
                    count(*) FILTER (WHERE direction_match) AS direction_match_rows,
                    count(*) FILTER (WHERE eligible) AS eligible_rows,
                    count(DISTINCT CAST(as_of_date AS VARCHAR) || ':' || instrument_id)
                        FILTER (WHERE direction_match AND market_fit <> 'blocked') AS market_ok_candidates,
                    count(DISTINCT CAST(as_of_date AS VARCHAR) || ':' || instrument_id)
                        FILTER (WHERE direction_match AND market_fit <> 'blocked' AND ticker_fit <> 'blocked') AS ticker_ok_candidates,
                    count(DISTINCT CAST(as_of_date AS VARCHAR) || ':' || instrument_id)
                        FILTER (WHERE eligible) AS eligible_candidates
                FROM read_parquet({sql_string(routes_path)})
                """,
                [PHASE25_GATE7_ROUTE_CONTRACT_VERSION],
            ).fetchone()
        finally:
            con.close()

        context_rows = int(context[0])
        strategy_count = len(DEFAULT_STRATEGY_REGISTRY.all())
        checks = {
            "gate7_exact_policy": gate7.get("phase25_gate7_policy_fingerprint") == phase25_gate7_policy_fingerprint(),
            "context_matches_gate6_population": context_rows == int(gate7.get("gate6_population_rows", -1)) == int(gate7.get("context_rows", -1)),
            "context_unique_keys": int(context[1]) == context_rows,
            "context_contract_exact": int(context[2]) == 0,
            "context_warm_hot_exact": int(context[3]) == 0,
            "context_directional_exact": int(context[4]) == 0,
            "market_state_complete": int(context[5]) == 0,
            "sector_unavailable": int(context[6]) == 0 and gate7.get("sector_mapping_status") == "UNAVAILABLE_NONBLOCKING",
            "route_cardinality_exact": int(routes[0]) == context_rows * strategy_count == int(gate7.get("route_decision_rows", -1)),
            "route_unique_keys": int(routes[1]) == int(routes[0]),
            "route_contract_exact": int(routes[2]) == 0,
            "route_sector_unavailable": int(routes[3]) == 0 and int(routes[4]) == 0,
            "eligible_requires_direction_match": int(routes[5]) == 0,
            "eligible_not_market_blocked": int(routes[6]) == 0,
            "eligible_not_ticker_blocked": int(routes[7]) == 0,
            "direction_match_count_exact": int(routes[8]) == context_rows * (strategy_count // 2) == int(gate7.get("direction_match_route_rows", -1)),
            "eligible_route_count_exact": int(routes[9]) == int(gate7.get("eligible_route_decisions", -1)),
            "market_candidate_count_exact": int(routes[10]) == int(gate7.get("market_route_compatible_candidates", -1)),
            "ticker_candidate_count_exact": int(routes[11]) == int(gate7.get("ticker_route_compatible_candidates", -1)),
            "fully_eligible_candidate_count_exact": int(routes[12]) == int(gate7.get("fully_route_eligible_candidates", -1)),
            "provider_activity_zero": int(gate7.get("provider_reads", -1)) == 0 and int(gate7.get("provider_writes", -1)) == 0,
            "operational_regime_writes_zero": int(gate7.get("operational_regime_writes", -1)) == 0,
            "routing_only": gate7.get("strategy_routing_performed") is True and gate7.get("strategy_rule_evaluation_performed") is False and gate7.get("strategy_returns_read") is False,
            "support_authority_false": gate7.get("support_replacement_authority") is False,
            "broker_order_paper_live_zero": PHASE25_BROKER_READS == PHASE25_BROKER_WRITES == PHASE25_ORDER_WRITES == PHASE25_PAPER_SUBMITS == PHASE25_LIVE_WRITES == 0,
            "support_writes_zero": PHASE25_PHASE11_SUPPORT_WRITES == 0,
            "protected_evidence_zero": PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS == 0,
        }
        if not all(checks.values()):
            failed = [name for name, passed in checks.items() if not passed]
            raise Phase25Gate7IndependentValidationError(
                "Gate7 independent validation failed: " + ", ".join(failed)
            )

        path = self.report_path(through_date)
        report: dict[str, object] = {
            "contract_version": PHASE25_GATE7_VALIDATION_CONTRACT_VERSION,
            "through_date": through_date.isoformat(),
            "gate7_report_sha256": sha256_file(gate7_path),
            "context_sha256": sha256_file(context_path),
            "routes_sha256": sha256_file(routes_path),
            "context_rows": context_rows,
            "route_decision_rows": int(routes[0]),
            "fully_route_eligible_candidates": int(routes[12]),
            "checks": checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(path.resolve()),
            "pass": True,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
