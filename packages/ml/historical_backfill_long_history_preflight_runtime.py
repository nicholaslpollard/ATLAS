from __future__ import annotations

import json
from datetime import UTC, datetime

from packages.core.atomic_io import atomic_write_text
from packages.features.partition_store import sha256_file

from .historical_backfill_long_history_preflight import (
    GATE11_LONG_HISTORY_PREFLIGHT_CONTRACT_VERSION,
    HistoricalBackfillLongHistoryMLPreflight,
    _stable_hash,
)


GATE11_LONG_HISTORY_FINGERPRINT_SCOPE = "CONTENT_ONLY_NO_ABSOLUTE_PATHS"


def _without_paths(payload: dict[str, object]) -> dict[str, object]:
    """Drop display-only absolute paths while retaining their content hashes."""

    result: dict[str, object] = {}
    for key, value in payload.items():
        if key.endswith("_path") or key == "dataset_glob":
            continue
        result[key] = value
    return result


class HistoricalBackfillLongHistoryMLPreflightRuntime(
    HistoricalBackfillLongHistoryMLPreflight
):
    """Runtime wrapper that makes Gate 11-A provenance machine-path independent."""

    def run(self) -> dict[str, object]:
        report = super().run()
        accepted = dict(report["accepted_phase10_A"])  # type: ignore[arg-type]
        rebase = dict(report["B_rebase_evidence"])  # type: ignore[arg-type]
        preseam = dict(  # type: ignore[arg-type]
            report["C_preseam_feasibility_before_structural_reconciliation"]
        )
        feature_lineage = report["feature_lineage"]
        comparison = report["comparison_policy"]

        fingerprint_payload = {
            "contract_version": GATE11_LONG_HISTORY_PREFLIGHT_CONTRACT_VERSION,
            "fingerprint_scope": GATE11_LONG_HISTORY_FINGERPRINT_SCOPE,
            "as_of_date": report["as_of_date"],
            "gate9c_validation_sha256": sha256_file(self.gate9_validation_path),
            "gate10c_writer_sha256": sha256_file(self.gate10_report_path),
            "gate10c_validation_sha256": sha256_file(self.gate10_validation_path),
            "comparison_policy": comparison,
            "accepted_phase10": _without_paths(accepted),
            "feature_lineage": feature_lineage,
            "B_rebase": _without_paths(rebase),
            "C_preseam": _without_paths(preseam),
        }
        report["source_fingerprint"] = _stable_hash(fingerprint_payload)
        report["fingerprint_scope"] = GATE11_LONG_HISTORY_FINGERPRINT_SCOPE
        checks = dict(report["checks"])  # type: ignore[arg-type]
        checks["source_fingerprint_excludes_absolute_paths"] = True
        report["checks"] = checks
        report["pass"] = all(bool(value) for value in checks.values())
        report["generated_at_utc"] = datetime.now(UTC).isoformat()
        atomic_write_text(
            self.report_path,
            json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        )
        report["report_path"] = str(self.report_path.resolve())
        return report
