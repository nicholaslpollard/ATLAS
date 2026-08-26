from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY

from .phase24_gate2 import (
    SessionSignal,
    chronological_boundaries,
    holm_bonferroni,
    internal_checks,
    selection_checks,
    tranche_metrics,
)
from .phase25_gate8 import Phase25Gate8DevelopmentAttribution
from .phase25_gate8_policy import (
    PHASE25_GATE8_DEVELOPMENT_END,
    PHASE25_GATE8_DEVELOPMENT_START,
    PHASE25_GATE9_INTERNAL_CONFIDENCE,
    PHASE25_GATE9_INTERNAL_FOLDS,
    PHASE25_GATE9_MULTIPLE_TESTING_ALPHA,
    PHASE25_GATE9_MULTIPLE_TESTING_METHOD,
    PHASE25_GATE9_PROTECTED_EVIDENCE_ALLOWED,
    PHASE25_GATE9_SELECTION_CONFIDENCE,
    PHASE25_GATE9_SELECTION_FOLDS,
    PHASE25_GATE9_SUPPORT_REPLACEMENT_ALLOWED,
    phase25_gate9_policy_fingerprint,
)
from .phase25_gate8_validation import Phase25Gate8IndependentValidator


PHASE25_GATE9_REPORT_CONTRACT_VERSION = (
    "phase25-gate9-report-v1-global-holm-selection-internal-finalist-lock"
)
PHASE25_GATE9_SELECTION_LOCK_CONTRACT_VERSION = (
    "phase25-gate9-selection-lock-v1-before-internal-validation"
)
PHASE25_GATE9_FINALIST_LOCK_CONTRACT_VERSION = (
    "phase25-gate9-finalist-lock-v1-before-protected-confirmation"
)


class Phase25Gate9Error(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate9Error(f"missing JSON evidence: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate9Error(f"invalid JSON evidence: {path}") from exc
    if not isinstance(value, dict):
        raise Phase25Gate9Error("Gate9 JSON evidence must be an object")
    return value


class Phase25Gate9Robustness:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate9"

    def run_root(self, through_date: date) -> Path:
        return self.root / f"through={through_date}"

    def report_path(self, through_date: date) -> Path:
        return self.run_root(through_date) / "robustness_report.json"

    def selection_lock_path(self, through_date: date) -> Path:
        return self.run_root(through_date) / "selection_lock.json"

    def finalist_lock_path(self, through_date: date) -> Path:
        return self.run_root(through_date) / "finalist_lock.json"

    @staticmethod
    def _signals(con, path: Path, strategy_id: str, start_date: date, end_date: date) -> tuple[SessionSignal, ...]:
        rows = con.execute(
            f"""
            SELECT
                CAST(session_date AS DATE),
                min(CAST(market_state AS VARCHAR)),
                max(CAST(market_state AS VARCHAR)),
                count(*),
                avg(CAST(directional_return AS DOUBLE))
            FROM read_parquet({sql_string(path)})
            WHERE strategy_id={sql_string(strategy_id)}
              AND session_date >= DATE {sql_string(start_date.isoformat())}
              AND session_date <= DATE {sql_string(end_date.isoformat())}
            GROUP BY 1 ORDER BY 1
            """
        ).fetchall()
        output: list[SessionSignal] = []
        for session_date, min_regime, max_regime, raw_rows, gross_mean in rows:
            if str(min_regime) != str(max_regime):
                raise Phase25Gate9Error(f"market state inconsistent within session: {session_date}")
            output.append(SessionSignal(session_date, str(min_regime), int(raw_rows), float(gross_mean)))
        return tuple(output)

    @staticmethod
    def _payload(strategy, metrics, checks, role: str) -> dict[str, object]:
        return {
            "strategy_id": strategy.metadata.strategy_id,
            "family": strategy.metadata.family.value,
            "direction": strategy.metadata.direction.value,
            "role": role,
            "metrics": metrics.to_dict(),
            "checks": dict(checks),
            "basic_pass": all(checks.values()),
        }

    def run(self, *, through_date: date) -> dict[str, object]:
        if PHASE25_GATE9_PROTECTED_EVIDENCE_ALLOWED:
            raise Phase25Gate9Error("Gate9 may not read protected evidence")
        if PHASE25_GATE9_SUPPORT_REPLACEMENT_ALLOWED:
            raise Phase25Gate9Error("Gate9 may not replace Phase11 support")
        if PHASE25_GATE9_MULTIPLE_TESTING_METHOD != "HOLM_BONFERRONI_GLOBAL_8_INCUMBENTS":
            raise Phase25Gate9Error("Gate9 multiplicity contract changed")

        gate8 = Phase25Gate8DevelopmentAttribution(self.settings)
        gate8_report_path = gate8.report_path(through_date)
        gate8_validation_path = Phase25Gate8IndependentValidator(self.settings).report_path(through_date)
        gate8_report = _read_json(gate8_report_path)
        gate8_validation = _read_json(gate8_validation_path)
        if gate8_report.get("pass") is not True or gate8_validation.get("pass") is not True:
            raise Phase25Gate9Error("Gate9 requires accepted Gate8 evidence")
        signals_path = gate8.signals_path(through_date)
        if gate8_report.get("signals_sha256") != sha256_file(signals_path):
            raise Phase25Gate9Error("Gate8 signal SHA changed")

        sessions = tuple(self.calendar.sessions_in_range(PHASE25_GATE8_DEVELOPMENT_START, PHASE25_GATE8_DEVELOPMENT_END))
        boundaries = chronological_boundaries(sessions)
        con = connect_utc(":memory:")
        try:
            selection_results: list[dict[str, object]] = []
            p_values: dict[str, float] = {}
            for strategy in DEFAULT_STRATEGY_REGISTRY.all():
                metrics = tranche_metrics(
                    self._signals(
                        con,
                        signals_path,
                        strategy.metadata.strategy_id,
                        boundaries.selection_start,
                        boundaries.selection_end,
                    ),
                    confidence=PHASE25_GATE9_SELECTION_CONFIDENCE,
                    folds=PHASE25_GATE9_SELECTION_FOLDS,
                    label=f"phase25-selection:{strategy.metadata.strategy_id}",
                )
                payload = self._payload(strategy, metrics, selection_checks(metrics), "PRODUCTION_PATH_SELECTION")
                selection_results.append(payload)
                p = metrics.primary_bootstrap_p_value
                if p is not None:
                    p_values[strategy.metadata.strategy_id] = float(p)

            holm = holm_bonferroni(p_values, alpha=PHASE25_GATE9_MULTIPLE_TESTING_ALPHA)
            selected_ids: list[str] = []
            for payload in selection_results:
                sid = str(payload["strategy_id"])
                payload["multiplicity"] = holm.get(
                    sid,
                    {"p_value": None, "threshold": None, "rejected_null": False},
                )
                payload["selection_pass"] = bool(
                    payload["basic_pass"] and payload["multiplicity"]["rejected_null"]
                )
                if payload["selection_pass"]:
                    selected_ids.append(sid)

            root = self.run_root(through_date)
            root.mkdir(parents=True, exist_ok=True)
            selection_lock = {
                "contract_version": PHASE25_GATE9_SELECTION_LOCK_CONTRACT_VERSION,
                "phase25_gate9_policy_fingerprint": phase25_gate9_policy_fingerprint(),
                "gate8_report_sha256": sha256_file(gate8_report_path),
                "gate8_validation_sha256": sha256_file(gate8_validation_path),
                "gate8_signals_sha256": sha256_file(signals_path),
                "development_boundaries": boundaries.to_dict(),
                "selected_strategy_ids": sorted(selected_ids),
                "internal_validation_has_not_influenced_selection": True,
                "protected_evidence_reads": 0,
                "support_writes": 0,
            }
            atomic_write_text(
                self.selection_lock_path(through_date),
                json.dumps(selection_lock, indent=2, sort_keys=True) + "\n",
            )
            selection_lock_sha = sha256_file(self.selection_lock_path(through_date))

            internal_results: list[dict[str, object]] = []
            selected = set(selected_ids)
            for strategy in DEFAULT_STRATEGY_REGISTRY.all():
                if strategy.metadata.strategy_id not in selected:
                    continue
                metrics = tranche_metrics(
                    self._signals(
                        con,
                        signals_path,
                        strategy.metadata.strategy_id,
                        boundaries.internal_start,
                        boundaries.internal_end,
                    ),
                    confidence=PHASE25_GATE9_INTERNAL_CONFIDENCE,
                    folds=PHASE25_GATE9_INTERNAL_FOLDS,
                    label=f"phase25-internal:{strategy.metadata.strategy_id}",
                )
                internal_results.append(
                    self._payload(strategy, metrics, internal_checks(metrics), "FROZEN_SELECTION_INTERNAL_VALIDATION")
                )
        finally:
            con.close()

        finalist_ids = sorted(
            str(item["strategy_id"]) for item in internal_results if item["basic_pass"]
        )
        finalist_lock = {
            "contract_version": PHASE25_GATE9_FINALIST_LOCK_CONTRACT_VERSION,
            "phase25_gate9_policy_fingerprint": phase25_gate9_policy_fingerprint(),
            "selection_lock_sha256": selection_lock_sha,
            "selected_strategy_ids": sorted(selected_ids),
            "finalist_strategy_ids": finalist_ids,
            "fallback_after_internal_failure": False,
            "protected_confirmation_has_not_influenced_finalists": True,
            "protected_evidence_reads": 0,
            "support_writes": 0,
        }
        atomic_write_text(
            self.finalist_lock_path(through_date),
            json.dumps(finalist_lock, indent=2, sort_keys=True) + "\n",
        )

        report_path = self.report_path(through_date)
        report: dict[str, object] = {
            "contract_version": PHASE25_GATE9_REPORT_CONTRACT_VERSION,
            "phase25_gate9_policy_fingerprint": phase25_gate9_policy_fingerprint(),
            "through_date": through_date.isoformat(),
            "gate8_report_sha256": sha256_file(gate8_report_path),
            "gate8_validation_sha256": sha256_file(gate8_validation_path),
            "gate8_signals_sha256": sha256_file(signals_path),
            "development_boundaries": boundaries.to_dict(),
            "multiple_testing_method": PHASE25_GATE9_MULTIPLE_TESTING_METHOD,
            "multiple_testing_alpha": PHASE25_GATE9_MULTIPLE_TESTING_ALPHA,
            "selection_results": selection_results,
            "multiplicity": holm,
            "selected_strategy_ids": sorted(selected_ids),
            "selection_lock_sha256": selection_lock_sha,
            "internal_results": internal_results,
            "finalist_strategy_ids": finalist_ids,
            "finalist_lock_sha256": sha256_file(self.finalist_lock_path(through_date)),
            "protected_evidence_reads": 0,
            "support_replacement_authority": False,
            "phase11_support_writes": 0,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        return report
