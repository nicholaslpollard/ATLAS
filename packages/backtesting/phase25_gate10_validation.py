from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .phase24_gate2 import TrancheMetrics
from .phase25_gate10 import (
    PHASE25_GATE10_REPORT_CONTRACT_VERSION,
    PHASE25_GATE10_SIGNAL_CONTRACT_VERSION,
    Phase25Gate10ProtectedConfirmation,
    protected_checks,
)
from .phase25_gate8_policy import (
    PHASE25_GATE10_PROTECTED_END,
    PHASE25_GATE10_PROTECTED_EVIDENCE_FRESH,
    PHASE25_GATE10_PROTECTED_START,
    phase25_gate10_policy_fingerprint,
)


PHASE25_GATE10_VALIDATION_CONTRACT_VERSION = (
    "phase25-gate10-validation-v1-finalist-lock-protected-bounds-checks"
)


class Phase25Gate10IndependentValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate10IndependentValidationError(f"missing Gate10 evidence: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate10IndependentValidationError(f"invalid Gate10 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise Phase25Gate10IndependentValidationError("Gate10 JSON must be an object")
    return value


def _metrics(item: dict[str, object]) -> TrancheMetrics:
    raw = dict(item["metrics"])
    raw["fold_means"] = tuple(raw.get("fold_means", []))
    return TrancheMetrics(**raw)


class Phase25Gate10IndependentValidator:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate10"

    def report_path(self, through_date: date) -> Path:
        return self.root / f"through={through_date}" / "independent_validation.json"

    def run(self, *, through_date: date) -> dict[str, object]:
        gate = Phase25Gate10ProtectedConfirmation(self.settings)
        report_path = gate.report_path(through_date)
        report = _read_json(report_path)
        if report.get("contract_version") != PHASE25_GATE10_REPORT_CONTRACT_VERSION:
            raise Phase25Gate10IndependentValidationError("Gate10 report contract mismatch")
        if report.get("phase25_gate10_policy_fingerprint") != phase25_gate10_policy_fingerprint():
            raise Phase25Gate10IndependentValidationError("Gate10 policy fingerprint mismatch")
        finalists = sorted(str(item) for item in report.get("finalist_strategy_ids", []))
        confirmed = sorted(str(item) for item in report.get("confirmed_strategy_ids", []))

        if not finalists:
            checks = {
                "policy_exact": report.get("phase25_gate10_policy_fingerprint") == phase25_gate10_policy_fingerprint(),
                "zero_finalists": finalists == [],
                "zero_confirmed": confirmed == [],
                "zero_protected_reads": int(report.get("protected_evidence_reads", -1)) == 0,
                "skip_disposition_exact": report.get("disposition") == "SKIPPED_ZERO_FINALISTS",
                "nonfresh_exact": report.get("protected_evidence_fresh") is PHASE25_GATE10_PROTECTED_EVIDENCE_FRESH,
                "support_authority_false": report.get("support_replacement_authority") is False and int(report.get("phase11_support_writes", -1)) == 0,
                "report_pass": report.get("pass") is True,
            }
        else:
            signals_path = gate.signals_path(through_date)
            if not signals_path.is_file() or report.get("signals_sha256") != sha256_file(signals_path):
                raise Phase25Gate10IndependentValidationError("Gate10 protected signal artifact missing/hash-mismatched")
            con = connect_utc(":memory:")
            try:
                stats = con.execute(
                    f"""
                    SELECT
                        count(*),
                        count(DISTINCT CAST(session_date AS VARCHAR) || ':' || instrument_id || ':' || strategy_id),
                        count(*) FILTER (WHERE contract_version <> ?),
                        count(*) FILTER (WHERE session_date < DATE ? OR session_date > DATE ?),
                        count(*) FILTER (WHERE forward_return IS NULL OR NOT isfinite(forward_return)),
                        count(*) FILTER (
                            WHERE abs(directional_return - CASE WHEN strategy_direction='LONG' THEN forward_return ELSE -forward_return END) > 1e-12
                        )
                    FROM read_parquet({sql_string(signals_path)})
                    """,
                    [
                        PHASE25_GATE10_SIGNAL_CONTRACT_VERSION,
                        PHASE25_GATE10_PROTECTED_START.isoformat(),
                        PHASE25_GATE10_PROTECTED_END.isoformat(),
                    ],
                ).fetchone()
            finally:
                con.close()
            recomputed_confirmed: list[str] = []
            bad_checks = 0
            for item_raw in report.get("protected_results", []):
                item = dict(item_raw)
                expected = protected_checks(_metrics(item))
                if expected != dict(item["checks"]):
                    bad_checks += 1
                if all(expected.values()):
                    recomputed_confirmed.append(str(item["strategy_id"]))
            checks = {
                "policy_exact": report.get("phase25_gate10_policy_fingerprint") == phase25_gate10_policy_fingerprint(),
                "protected_read_once": int(report.get("protected_evidence_reads", -1)) == 1,
                "protected_bounds_exact": report.get("protected_start") == PHASE25_GATE10_PROTECTED_START.isoformat() and report.get("protected_end") == PHASE25_GATE10_PROTECTED_END.isoformat(),
                "signal_rows_unique": int(stats[0]) == int(stats[1]),
                "signal_contract_exact": int(stats[2]) == 0,
                "signals_within_protected": int(stats[3]) == 0,
                "finite_returns": int(stats[4]) == 0,
                "directional_return_exact": int(stats[5]) == 0,
                "protected_checks_recomputed": bad_checks == 0,
                "confirmed_ids_recomputed": confirmed == sorted(recomputed_confirmed),
                "confirmed_subset_finalists": set(confirmed).issubset(set(finalists)),
                "nonfresh_exact": report.get("protected_evidence_fresh") is PHASE25_GATE10_PROTECTED_EVIDENCE_FRESH,
                "support_authority_false": report.get("support_replacement_authority") is False and int(report.get("phase11_support_writes", -1)) == 0,
                "report_pass": report.get("pass") is True,
            }
        if not all(checks.values()):
            failed = [name for name, passed in checks.items() if not passed]
            raise Phase25Gate10IndependentValidationError("Gate10 independent validation failed: " + ", ".join(failed))

        path = self.report_path(through_date)
        validation: dict[str, object] = {
            "contract_version": PHASE25_GATE10_VALIDATION_CONTRACT_VERSION,
            "through_date": through_date.isoformat(),
            "gate10_report_sha256": sha256_file(report_path),
            "finalist_strategy_ids": finalists,
            "confirmed_strategy_ids": confirmed,
            "protected_evidence_reads": int(report.get("protected_evidence_reads", 0)),
            "checks": checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(path.resolve()),
            "pass": True,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(validation, indent=2, sort_keys=True) + "\n")
        return validation
