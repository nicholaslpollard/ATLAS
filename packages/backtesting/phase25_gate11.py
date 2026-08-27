from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY

from .phase25_gate8 import Phase25Gate8DevelopmentAttribution
from .phase25_gate8_validation import Phase25Gate8IndependentValidator
from .phase25_gate9 import Phase25Gate9Robustness
from .phase25_gate9_validation import Phase25Gate9IndependentValidator
from .phase25_gate10 import Phase25Gate10ProtectedConfirmation
from .phase25_gate10_validation import Phase25Gate10IndependentValidator
from .phase25_gate8_policy import (
    PHASE25_GATE11_FUTURE_PROSPECTIVE_REQUIRED_FOR_AUTHORITY,
    PHASE25_GATE11_SUPPORT_REPLACEMENT_ALLOWED,
    phase25_gate11_policy_fingerprint,
)


PHASE25_GATE11_REPORT_CONTRACT_VERSION = (
    "phase25-gate11-report-v1-cumulative-diagnostic-closeout"
)


class Phase25Gate11Error(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate11Error(f"missing closeout prerequisite: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate11Error(f"invalid closeout prerequisite: {path}") from exc
    if not isinstance(value, dict):
        raise Phase25Gate11Error("closeout prerequisite must be an object")
    return value


def _metric(summary: dict[str, object], cost: str = "10") -> dict[str, object]:
    return dict(dict(summary["aggregate_by_cost_bps"])[cost])


def _failed(checks: dict[str, object] | None) -> list[str]:
    if not checks:
        return []
    return sorted(str(name) for name, passed in checks.items() if not bool(passed))


class Phase25Gate11Closeout:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate11"

    def run_root(self, through_date: date) -> Path:
        return self.root / f"through={through_date}"

    def report_path(self, through_date: date) -> Path:
        return self.run_root(through_date) / "cumulative_closeout.json"

    def run(self, *, through_date: date) -> dict[str, object]:
        if PHASE25_GATE11_SUPPORT_REPLACEMENT_ALLOWED:
            raise Phase25Gate11Error("Gate11 may not mutate Phase11 support")
        if not PHASE25_GATE11_FUTURE_PROSPECTIVE_REQUIRED_FOR_AUTHORITY:
            raise Phase25Gate11Error("Gate11 future-prospective authority lock changed")

        gate8 = Phase25Gate8DevelopmentAttribution(self.settings)
        gate9 = Phase25Gate9Robustness(self.settings)
        gate10 = Phase25Gate10ProtectedConfirmation(self.settings)
        paths = {
            "gate8_report": gate8.report_path(through_date),
            "gate8_validation": Phase25Gate8IndependentValidator(self.settings).report_path(through_date),
            "gate9_report": gate9.report_path(through_date),
            "gate9_validation": Phase25Gate9IndependentValidator(self.settings).report_path(through_date),
            "gate10_report": gate10.report_path(through_date),
            "gate10_validation": Phase25Gate10IndependentValidator(self.settings).report_path(through_date),
        }
        evidence = {name: _read_json(path) for name, path in paths.items()}
        if any(item.get("pass") is not True for item in evidence.values()):
            raise Phase25Gate11Error("Gate11 requires passing Gates8-10 and independent validations")

        gate8_report = evidence["gate8_report"]
        gate9_report = evidence["gate9_report"]
        gate10_report = evidence["gate10_report"]
        selection = {str(item["strategy_id"]): dict(item) for item in gate9_report.get("selection_results", [])}
        internal = {str(item["strategy_id"]): dict(item) for item in gate9_report.get("internal_results", [])}
        protected = {str(item["strategy_id"]): dict(item) for item in gate10_report.get("protected_results", [])}
        selected_ids = set(str(item) for item in gate9_report.get("selected_strategy_ids", []))
        finalist_ids = set(str(item) for item in gate9_report.get("finalist_strategy_ids", []))
        confirmed_ids = set(str(item) for item in gate10_report.get("confirmed_strategy_ids", []))
        attribution = {str(item["strategy_id"]): dict(item) for item in gate8_report.get("strategy_results", [])}

        failure_counts: Counter[str] = Counter()
        rows: list[dict[str, object]] = []
        for strategy in DEFAULT_STRATEGY_REGISTRY.all():
            sid = strategy.metadata.strategy_id
            item = attribution[sid]
            production = dict(item["production_path"])
            broad = dict(item["broad_comparator"])
            prod10 = _metric(production)
            broad10 = _metric(broad)
            prod_mean = prod10.get("mean_return")
            broad_mean = broad10.get("mean_return")
            if prod_mean is None or broad_mean is None:
                effect = "UNAVAILABLE"
            elif float(prod_mean) > 0 >= float(broad_mean):
                effect = "SIGN_FLIP_TO_POSITIVE"
            elif float(prod_mean) <= 0 < float(broad_mean):
                effect = "SIGN_FLIP_TO_NONPOSITIVE"
            elif float(prod_mean) > float(broad_mean):
                effect = "IMPROVED"
            elif float(prod_mean) < float(broad_mean):
                effect = "WORSENED"
            else:
                effect = "UNCHANGED"
            sel = selection.get(sid)
            intr = internal.get(sid)
            prot = protected.get(sid)
            sel_failed = _failed(None if sel is None else dict(sel.get("checks", {})))
            intr_failed = _failed(None if intr is None else dict(intr.get("checks", {})))
            prot_failed = _failed(None if prot is None else dict(prot.get("checks", {})))
            failure_counts.update(f"selection:{name}" for name in sel_failed)
            failure_counts.update(f"internal:{name}" for name in intr_failed)
            failure_counts.update(f"protected:{name}" for name in prot_failed)
            rows.append(
                {
                    "strategy_id": sid,
                    "family": strategy.metadata.family.value,
                    "direction": strategy.metadata.direction.value,
                    "broad_primary_10bps_rows": int(broad10.get("rows", 0)),
                    "broad_primary_10bps_mean": broad_mean,
                    "production_primary_10bps_rows": int(prod10.get("rows", 0)),
                    "production_primary_10bps_mean": prod_mean,
                    "primary_10bps_mean_delta": item.get("primary_10bps_mean_delta"),
                    "population_effect": effect,
                    "selection_basic_pass": False if sel is None else bool(sel.get("basic_pass")),
                    "multiplicity_rejected_null": False if sel is None else bool(dict(sel.get("multiplicity", {})).get("rejected_null", False)),
                    "selected": sid in selected_ids,
                    "selection_failed_checks": sel_failed,
                    "internal_evaluated": intr is not None,
                    "internal_pass": False if intr is None else bool(intr.get("basic_pass")),
                    "internal_failed_checks": intr_failed,
                    "finalist": sid in finalist_ids,
                    "protected_evaluated": prot is not None,
                    "protected_confirmed": sid in confirmed_ids,
                    "protected_failed_checks": prot_failed,
                }
            )

        if not finalist_ids:
            verdict = "NO_SUPPORT_REPLACEMENT_DEVELOPMENT_ROBUSTNESS_FAILED"
            next_boundary = "TARGET_DEVELOPMENT_FAILURE_MODES_OR_NEW_STRATEGY_ARCHITECTURES"
        elif not confirmed_ids:
            verdict = "NO_SUPPORT_REPLACEMENT_PROTECTED_CONFIRMATION_FAILED"
            next_boundary = "TARGET_PROTECTED_FAILURE_MODES_OR_NEW_STRATEGY_ARCHITECTURES"
        else:
            verdict = "RESEARCH_CANDIDATES_REQUIRE_FUTURE_PROSPECTIVE_CONFIRMATION"
            next_boundary = "FUTURE_PROSPECTIVE_CONFIRMATION_BEFORE_ANY_SUPPORT_AUTHORITY"

        report_path = self.report_path(through_date)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report: dict[str, object] = {
            "contract_version": PHASE25_GATE11_REPORT_CONTRACT_VERSION,
            "phase25_gate11_policy_fingerprint": phase25_gate11_policy_fingerprint(),
            "through_date": through_date.isoformat(),
            "upstream_sha256": {name: sha256_file(path) for name, path in paths.items()},
            "route_fidelity_attribution": {
                "gate6_directional_candidates": int(gate8_report["gate7_population_rows"]),
                "market_compatible_candidates": int(gate8_report["gate7_market_compatible_candidates"]),
                "ticker_compatible_candidates": int(gate8_report["gate7_ticker_compatible_candidates"]),
                "fully_route_eligible_candidates": int(gate8_report["gate7_fully_route_eligible_candidates"]),
                "eligible_route_decisions_all_dates": int(gate8_report["gate7_eligible_route_decisions"]),
                "development_route_eligible_rows": int(gate8_report["route_eligible_rows"]),
                "development_source_matched_route_rows": int(gate8_report["research_source_matched_route_rows"]),
                "development_source_missing_route_rows": int(gate8_report["research_source_missing_route_rows"]),
                "development_source_coverage_fraction": float(gate8_report["research_source_route_coverage_fraction"]),
                "development_rule_fired_signal_rows": int(gate8_report["development_rule_fired_signal_rows"]),
                "development_candidates_with_any_rule_fire": int(gate8_report["development_candidates_with_any_rule_fire"]),
            },
            "strategy_diagnostics": rows,
            "failure_counts": dict(sorted(failure_counts.items())),
            "selected_strategy_ids": sorted(selected_ids),
            "finalist_strategy_ids": sorted(finalist_ids),
            "confirmed_strategy_ids": sorted(confirmed_ids),
            "protected_evidence_fresh": gate10_report.get("protected_evidence_fresh"),
            "verdict": verdict,
            "next_boundary": next_boundary,
            "phase11_support_map_unchanged": True,
            "support_replacement_authority": False,
            "phase11_support_writes": 0,
            "future_prospective_required_for_authority": True,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        return report
