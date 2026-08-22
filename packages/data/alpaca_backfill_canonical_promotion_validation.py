from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_candidate_canonical import (
    ALPACA_BACKFILL_CANDIDATE_CANONICAL_CONTRACT_VERSION,
    candidate_source_id,
)
from packages.data.alpaca_backfill_canonical_promotion import (
    ALPACA_BACKFILL_CANONICAL_PROMOTION_CONTRACT_VERSION,
    PROMOTION_STATUS_COMPLETE,
    AlpacaBackfillCanonicalPromotion,
    gate8_acceptance_checks,
    inventory_fingerprint,
    promotion_source_fingerprint,
)
from packages.data.alpaca_backfill_seam import ALPACA_BACKFILL_SEAM_TARGET_SESSION
from packages.data.alpaca_backfill_seam_final import ALPACA_BACKFILL_SEAM_FINAL_CONTRACT_VERSION
from packages.data.alpaca_backfill_validated_evidence import sha256_file


GATE8_REVALIDATION_CONTRACT_VERSION = (
    "historical-backfill-canonical-promotion-revalidation-v1-independent-disk-proof"
)


def gate8_revalidation_checks(report: dict[str, object]) -> dict[str, bool]:
    checks = gate8_acceptance_checks(report)
    checks.update(
        {
            "revalidation_contract": report.get("revalidation_contract_version")
            == GATE8_REVALIDATION_CONTRACT_VERSION,
            "stored_manifest_complete": report.get("stored_manifest_status")
            == PROMOTION_STATUS_COMPLETE,
            "preflight_report_hash_exact": report.get("preflight_report_hash_exact") is True,
            "candidate_parent_current": report.get("candidate_parent_current") is True,
            "gate7_parent_current": report.get("gate7_parent_current") is True,
            "promotion_source_fingerprint_current": report.get(
                "promotion_source_fingerprint_current"
            )
            is True,
            "promoted_symbol_accounting_exact": report.get(
                "promoted_symbol_accounting_exact"
            )
            is True,
            "promotion_session_journal_accounting_exact": report.get(
                "promotion_session_journal_accounting_exact"
            )
            is True,
        }
    )
    return checks


class AlpacaBackfillCanonicalPromotionValidator:
    """Independently re-prove a completed Gate 8 promotion from disk.

    The promotion writer's final manifest is treated as a claim, not as proof. This
    validator re-reads the accepted Gate 6 candidate, current Gate 7 report/decision
    map, promoted canonical files, and the preflight-frozen Massive baseline. It then
    recomputes hashes, schema/semantic counts, and lineage fingerprints.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.promotion = AlpacaBackfillCanonicalPromotion(settings)

    @staticmethod
    def _load_json(path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise RuntimeError(f"Gate 8 revalidation requires {label}: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def run(self) -> dict[str, object]:
        stored = self._load_json(
            self.promotion.promotion_manifest_path,
            "completed promotion manifest",
        )
        if stored.get("contract_version") != ALPACA_BACKFILL_CANONICAL_PROMOTION_CONTRACT_VERSION:
            raise RuntimeError("Gate 8 revalidation promotion contract mismatch")
        if stored.get("status") != PROMOTION_STATUS_COMPLETE:
            raise RuntimeError("Gate 8 revalidation requires a COMPLETE promotion manifest")

        preflight_path = Path(
            str(stored.get("preflight_report_path") or self.promotion.preflight_report_path)
        )
        preflight = self._load_json(preflight_path, "promotion preflight report")
        preflight_hash_exact = (
            sha256_file(preflight_path) == stored.get("preflight_report_sha256")
        )

        candidate_report = self._load_json(
            self.promotion.candidate_builder.report_path,
            "Gate 6 candidate manifest",
        )
        candidate_validation = self.promotion.candidate_validator.run()
        candidate_files = self.promotion._candidate_inventory(candidate_report)
        candidate_inventory_fp = inventory_fingerprint(candidate_files)
        candidate_hashes_exact = all(
            Path(str(item["path"])).is_file()
            and sha256_file(Path(str(item["path"]))) == str(item["sha256"])
            for item in candidate_files
        )

        gate7_report = self._load_json(
            self.promotion.gate7_report_path,
            "Gate 7 final report",
        )
        if not self.promotion.gate7_decision_path.is_file():
            raise RuntimeError("Gate 8 revalidation requires the Gate 7 decision map")
        gate7_decision_sha = sha256_file(self.promotion.gate7_decision_path)

        candidate_parent_current = (
            candidate_report.get("contract_version")
            == ALPACA_BACKFILL_CANDIDATE_CANONICAL_CONTRACT_VERSION
            and candidate_validation.get("pass") is True
            and candidate_report.get("source_fingerprint")
            == stored.get("candidate_source_fingerprint")
            and candidate_inventory_fp == stored.get("candidate_inventory_fingerprint")
        )
        gate7_parent_current = (
            gate7_report.get("contract_version") == ALPACA_BACKFILL_SEAM_FINAL_CONTRACT_VERSION
            and gate7_report.get("gate7_pass") is True
            and gate7_report.get("source_fingerprint") == stored.get("gate7_source_fingerprint")
            and gate7_decision_sha == stored.get("gate7_decision_sha256")
        )

        baseline = list(preflight.get("massive_baseline_files") or [])
        massive_baseline_unchanged = bool(baseline) and self.promotion._massive_baseline_unchanged(
            baseline
        )
        baseline_fp = inventory_fingerprint(baseline)

        current_source_fp = promotion_source_fingerprint(
            candidate_fingerprint=str(candidate_report.get("source_fingerprint")),
            gate7_fingerprint=str(gate7_report.get("source_fingerprint")),
            gate7_decision_sha256=gate7_decision_sha,
            candidate_inventory_fingerprint=candidate_inventory_fp,
            massive_baseline_fingerprint=baseline_fp,
        )
        source_fp_current = (
            current_source_fp == stored.get("source_fingerprint")
            and baseline_fp == stored.get("massive_baseline_fingerprint")
        )

        targets = [
            self.promotion.canonical_root / str(item["relative_path"])
            for item in candidate_files
        ]
        promoted_hashes_exact = all(
            target.is_file() and sha256_file(target) == str(item["sha256"])
            for target, item in zip(targets, candidate_files)
        )
        expected_source_id = candidate_source_id(str(candidate_report["source_fingerprint"]))
        stats = self.promotion._promoted_stats(targets, expected_source_id=expected_source_id)

        expected_rows = int(candidate_report["candidate_rows"])
        expected_sessions = int(candidate_report["candidate_sessions"])
        expected_symbols = int(candidate_report["observed_symbols"])
        copied = int(stored.get("copied_sessions", -1))
        reused = int(stored.get("reused_exact_sessions", -1))

        live: dict[str, object] = {
            "contract_version": stored["contract_version"],
            "status": stored["status"],
            "revalidation_contract_version": GATE8_REVALIDATION_CONTRACT_VERSION,
            "stored_manifest_status": stored["status"],
            "source_fingerprint": stored["source_fingerprint"],
            "candidate_source_fingerprint": candidate_report["source_fingerprint"],
            "gate7_source_fingerprint": gate7_report["source_fingerprint"],
            "gate7_decision_sha256": gate7_decision_sha,
            "candidate_inventory_fingerprint": candidate_inventory_fp,
            "massive_baseline_fingerprint": baseline_fp,
            "preflight_report_hash_exact": preflight_hash_exact,
            "candidate_parent_current": candidate_parent_current,
            "gate7_parent_current": gate7_parent_current,
            "promotion_source_fingerprint_current": source_fp_current,
            "candidate_hashes_exact": candidate_hashes_exact,
            "promoted_hashes_exact": promoted_hashes_exact,
            "massive_baseline_unchanged": massive_baseline_unchanged,
            "promoted_rows": stats["rows"],
            "promoted_sessions": stats["sessions"],
            "promoted_symbols": stats["symbols"],
            "duplicate_keys": stats["duplicate_keys"],
            "semantic_mismatches": stats["semantic_mismatches"],
            "first_session": stats["first_session"],
            "last_session": stats["last_session"],
            "row_accounting_exact": stats["rows"] == expected_rows,
            "session_accounting_exact": stats["sessions"] == expected_sessions,
            "promoted_symbol_accounting_exact": stats["symbols"] == expected_symbols,
            "production_schema_exact": stats["schema_exact"] is True,
            "production_semantics_exact": stats["semantic_mismatches"] == 0,
            "seam_not_overwritten": all(
                session_date_from_item(item) < ALPACA_BACKFILL_SEAM_TARGET_SESSION
                for item in candidate_files
            )
            and massive_baseline_unchanged,
            "gate7_policy_bound": gate7_decision_sha == stored.get("gate7_decision_sha256"),
            "promotion_session_journal_accounting_exact": copied >= 0
            and reused >= 0
            and copied + reused == expected_sessions,
            "promotion_manifest_path": str(self.promotion.promotion_manifest_path),
            "preflight_report_path": str(preflight_path),
        }
        checks = gate8_revalidation_checks(live)
        live["checks"] = checks
        live["pass"] = all(checks.values())
        return live


def session_date_from_item(item: dict[str, object]):
    from datetime import date

    return date.fromisoformat(str(item["session_date"]))
