from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.ml.historical_backfill_model_benchmark import (
    HISTORICAL_BACKFILL_ACCEPTED_GATE11D_SOURCE_FINGERPRINT,
    HISTORICAL_BACKFILL_MODEL_BENCHMARK_CONTRACT_VERSION,
    HistoricalBackfillModelBenchmark,
)
from packages.ml.historical_backfill_model_benchmark_validation import (
    HISTORICAL_BACKFILL_MODEL_VALIDATION_CONTRACT_VERSION,
    HistoricalBackfillModelBenchmarkValidator,
)
from packages.ml.model_registry import accepted_model_id, model_registry_fingerprint


HISTORICAL_BACKFILL_CLOSEOUT_CONTRACT_VERSION = (
    "historical-backfill-closeout-v1-phase-level-acceptance"
)
HISTORICAL_BACKFILL_CLOSEOUT_PRODUCTION_MODEL_REPLACEMENT_ALLOWED = False
HISTORICAL_BACKFILL_CLOSEOUT_BROKER_WRITES = 0


class HistoricalBackfillCloseoutError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class HistoricalBackfillCloseout:
    """Create the single phase-level acceptance record for the historical extension."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.benchmark = HistoricalBackfillModelBenchmark(settings)
        self.validator = HistoricalBackfillModelBenchmarkValidator(settings)
        self.report_path = self.benchmark.root / "historical_extension_final_acceptance.json"

    @staticmethod
    def _read_json(path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise HistoricalBackfillCloseoutError(f"missing {label}: {path}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HistoricalBackfillCloseoutError(f"invalid JSON for {label}: {path}") from exc

    def run(self) -> dict[str, object]:
        benchmark = self._read_json(self.benchmark.report_path, "historical model benchmark")
        validation = self._read_json(self.validator.report_path, "historical benchmark validation")
        if benchmark.get("contract_version") != HISTORICAL_BACKFILL_MODEL_BENCHMARK_CONTRACT_VERSION:
            raise HistoricalBackfillCloseoutError("historical benchmark contract changed")
        if validation.get("contract_version") != HISTORICAL_BACKFILL_MODEL_VALIDATION_CONTRACT_VERSION:
            raise HistoricalBackfillCloseoutError("historical validation contract changed")
        if benchmark.get("design_source_fingerprint") != HISTORICAL_BACKFILL_ACCEPTED_GATE11D_SOURCE_FINGERPRINT:
            raise HistoricalBackfillCloseoutError("historical benchmark design fingerprint changed")
        if benchmark.get("pass") is not True or validation.get("pass") is not True:
            raise HistoricalBackfillCloseoutError("historical benchmark evidence is not accepted")
        if validation.get("benchmark_result_fingerprint") != benchmark.get("result_fingerprint"):
            raise HistoricalBackfillCloseoutError("validation does not bind the current benchmark result")

        benchmark_decision = str(dict(benchmark["primary_selection"])["decision"])
        independent_decision = str(dict(validation["independent_primary_decision"])["decision"])
        if benchmark_decision != independent_decision:
            raise HistoricalBackfillCloseoutError("benchmark and independent validator disagree on decision")

        production_id = accepted_model_id()
        production_fingerprint = model_registry_fingerprint()
        challenger_registered = benchmark_decision == "REGISTER_C_AS_VERSIONED_CHALLENGER_EVIDENCE"
        final_disposition = {
            "primary_comparison_decision": benchmark_decision,
            "accepted_phase10_production_model_remains_authoritative": True,
            "accepted_phase10_model_id": production_id,
            "accepted_phase10_model_fingerprint": production_fingerprint,
            "historical_C_challenger_evidence_registered": challenger_registered,
            "historical_C_challenger_is_production": False,
            "nested_history_is_attribution_only": True,
            "production_model_replacement_allowed": False,
            "next_phase": "PHASE_11_STRATEGY_EVALUATION_AND_REGIME_ROUTING",
        }
        checks = {
            "benchmark_pass": benchmark.get("pass") is True,
            "validation_pass": validation.get("pass") is True,
            "benchmark_validation_binding_exact": validation.get("benchmark_result_fingerprint")
            == benchmark.get("result_fingerprint"),
            "decision_recomputed_exact": benchmark_decision == independent_decision,
            "accepted_phase10_model_remains_authoritative": True,
            "historical_challenger_not_silent_production_replacement": final_disposition[
                "historical_C_challenger_is_production"
            ]
            is False,
            "nested_history_attribution_only": final_disposition["nested_history_is_attribution_only"]
            is True,
            "final_holdout_not_accessed": benchmark.get("final_holdout_accessed") is False,
            "production_registry_unchanged": benchmark.get("production_registry_inventory_unchanged")
            is True,
            "production_model_replacement_forbidden": (
                HISTORICAL_BACKFILL_CLOSEOUT_PRODUCTION_MODEL_REPLACEMENT_ALLOWED is False
            ),
            "production_ml_writes_zero": int(benchmark.get("production_ml_writes", -1)) == 0
            and int(validation.get("production_ml_writes", -1)) == 0,
            "broker_writes_zero": HISTORICAL_BACKFILL_CLOSEOUT_BROKER_WRITES == 0,
        }
        source_fingerprint = _stable_hash(
            {
                "contract_version": HISTORICAL_BACKFILL_CLOSEOUT_CONTRACT_VERSION,
                "benchmark_result_fingerprint": benchmark["result_fingerprint"],
                "validation_fingerprint": validation["source_fingerprint"],
                "final_disposition": final_disposition,
            }
        )
        report: dict[str, object] = {
            "contract_version": HISTORICAL_BACKFILL_CLOSEOUT_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": source_fingerprint,
            "benchmark_result_fingerprint": benchmark["result_fingerprint"],
            "validation_fingerprint": validation["source_fingerprint"],
            "design_source_fingerprint": benchmark["design_source_fingerprint"],
            "aggregates": benchmark["aggregates"],
            "primary_selection": benchmark["primary_selection"],
            "nested_history_attribution": benchmark["nested_history_attribution"],
            "final_disposition": final_disposition,
            "checks": checks,
            "production_ml_writes": 0,
            "broker_writes": HISTORICAL_BACKFILL_CLOSEOUT_BROKER_WRITES,
            "pass": all(bool(value) for value in checks.values()),
        }
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        return report
