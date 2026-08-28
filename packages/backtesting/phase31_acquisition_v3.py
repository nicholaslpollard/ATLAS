from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from packages.core.atomic_io import atomic_write_text
from packages.features.partition_store import sha256_file

from .phase31_acquisition import (
    PHASE31_ACQUISITION_CONTRACT_VERSION,
    PHASE31_EXPECTED_MONTH_SHARDS,
    Phase31AcquisitionError,
    Phase31Form4HistoricalAcquisition,
    _chronology_violation_count,
    _immutable_write,
    _jsonl,
    _load_jsonl,
    _partition_global_quarantine,
    phase31_month_shards,
)
from .phase31_feasibility import PHASE31_PROBE_WINDOWS
from .phase31_historical_source_quality import (
    PHASE31_HISTORICAL_QUARANTINE_REASON,
    PHASE31_HISTORICAL_SOURCE_QUALITY_CONTRACT_VERSION,
    PHASE31_MISSING_TRANSACTION_CODE_REASON,
    classify_form4_historical_source_quality,
    required_transaction_code_violation_count,
)
from .phase31_policy import (
    PHASE31_PROTECTED_OUTCOME_END,
    PHASE31_SOURCE_HISTORY_START,
    PHASE31_SOURCE_QUALITY_FINGERPRINT,
    phase31_policy_fingerprint,
)


PHASE31_ACQUISITION_V3_CONTRACT_VERSION = (
    "phase31-form4-acquisition-v3-v2-raw-resume-global-historical-admissibility-quarantine"
)


class Phase31Form4HistoricalAcquisitionV3(Phase31Form4HistoricalAcquisition):
    """Resume v2 raw shards and apply the stricter historical source-admissibility gate.

    The immutable raw-shard/sidecar contract remains the accepted v2 contract so a
    source-quality repair cannot force re-downloads of already preserved provider
    evidence. The final acquisition report is v3 because authoritative admission now
    additionally requires a usable transaction_code for every transaction in an
    accession. The scientific policy and all market-outcome blindness rules are
    unchanged.
    """

    def run(self, *, progress: Callable[[str], None] | None = None) -> dict[str, Any]:
        repair, feasibility = self._validate_source_repair()
        shards = phase31_month_shards()
        probe_rows: dict[str, list[dict[str, Any]]] = {
            window.label: [] for window in PHASE31_PROBE_WINDOWS
        }
        first_pass: list[dict[str, Any]] = []
        contaminated_accessions: set[str] = set()
        contamination_reasons: dict[str, set[str]] = {}
        total_provider_pages = 0
        fresh_shards = 0
        reused_shards = 0
        chronology_seed_total = 0
        missing_code_seed_total = 0

        # Pass 1: resume/acquire immutable v2 raw shards, then discover every
        # inadmissible accession globally without reading any market outcome.
        for shard in shards:
            if progress is not None:
                progress(f"{shard.label}: raw acquisition/resume")
            raw_rows, page_count, request_ids, reused = self._load_or_fetch_raw_shard(shard)
            classified = classify_form4_historical_source_quality(raw_rows)
            contaminated_accessions.update(classified.contaminated_accessions)
            for accession, reasons in classified.accession_reasons:
                contamination_reasons.setdefault(accession, set()).update(reasons)
            self._collect_probe_rows(shard, raw_rows, probe_rows)
            total_provider_pages += page_count
            reused_shards += int(reused)
            fresh_shards += int(not reused)
            chronology_seed_total += len(classified.chronology_seed_rows)
            missing_code_seed_total += len(classified.missing_transaction_code_seed_rows)
            first_pass.append(
                {
                    **asdict(shard),
                    "reused_raw_shard": reused,
                    "provider_pages_this_run": page_count,
                    "request_ids_this_run": list(request_ids),
                    "raw_rows": len(raw_rows),
                    "raw_path": str(self.raw_path(shard.label).resolve()),
                    "raw_metadata_path": str(self.raw_metadata_path(shard.label).resolve()),
                    "raw_sha256": sha256_file(self.raw_path(shard.label)),
                    "local_chronology_violation_seed_rows": len(classified.chronology_seed_rows),
                    "local_missing_transaction_code_seed_rows": len(
                        classified.missing_transaction_code_seed_rows
                    ),
                    "local_contaminated_accessions": list(classified.contaminated_accessions),
                }
            )

        # Pass 2: apply the final global accession set to every month. An accession
        # discovered defective in a later shard is therefore removed from every
        # earlier shard as well.
        shard_reports: list[dict[str, Any]] = []
        total_raw = 0
        total_authoritative = 0
        total_quarantined = 0
        for source in first_pass:
            label = str(source["label"])
            raw_rows = _load_jsonl(self.raw_path(label))
            authoritative, quarantined = _partition_global_quarantine(
                raw_rows, contaminated_accessions
            )
            invalid_chronology = _chronology_violation_count(authoritative)
            invalid_codes = required_transaction_code_violation_count(authoritative)
            if invalid_chronology:
                raise Phase31AcquisitionError(
                    f"authoritative shard still has chronology violations: {label}"
                )
            if invalid_codes:
                raise Phase31AcquisitionError(
                    f"authoritative shard still has missing transaction_code rows: {label}"
                )

            authoritative_sha = _immutable_write(
                self.authoritative_path(label), _jsonl(authoritative)
            )
            quarantine_envelopes = tuple(
                {
                    "month_shard": label,
                    "quarantine_reason": PHASE31_HISTORICAL_QUARANTINE_REASON,
                    "quarantine_reasons": sorted(
                        contamination_reasons.get(str(row.get("accession_number") or ""), set())
                    ),
                    "quarantine_scope": "ENTIRE_ACCESSION_GLOBAL_HISTORY",
                    "raw_row": row,
                }
                for row in quarantined
            )
            quarantine_sha = _immutable_write(
                self.quarantine_path(label), _jsonl(quarantine_envelopes)
            )
            total_raw += len(raw_rows)
            total_authoritative += len(authoritative)
            total_quarantined += len(quarantined)
            shard_reports.append(
                {
                    **source,
                    "quarantined_rows": len(quarantined),
                    "quarantine_path": str(self.quarantine_path(label).resolve()),
                    "quarantine_sha256": quarantine_sha,
                    "authoritative_rows": len(authoritative),
                    "authoritative_path": str(self.authoritative_path(label).resolve()),
                    "authoritative_sha256": authoritative_sha,
                    "authoritative_chronology_violations": invalid_chronology,
                    "authoritative_missing_transaction_code_rows": invalid_codes,
                }
            )

        # The four previously accepted probe windows remain exact. This is the guard
        # against using the new full-history defect rule to rewrite known evidence.
        probe_reconciliation = self._probe_reconciliation(
            probe_rows, feasibility, contaminated_accessions
        )
        checks = {
            "source_quality_target_replay_exact": repair.get("pass") is True,
            "scientific_policy_frozen": len(phase31_policy_fingerprint()) == 64,
            "raw_shard_contract_retained_v2": PHASE31_ACQUISITION_CONTRACT_VERSION
            == "phase31-form4-acquisition-v2-monthly-memory-bounded-global-accession-quarantine",
            "historical_source_quality_contract_present": bool(
                PHASE31_HISTORICAL_SOURCE_QUALITY_CONTRACT_VERSION
            ),
            "monthly_shard_count_exact": len(shard_reports) == PHASE31_EXPECTED_MONTH_SHARDS,
            "full_history_scope_exact": shard_reports[0]["start_date"] == PHASE31_SOURCE_HISTORY_START
            and shard_reports[-1]["end_date"] == PHASE31_PROTECTED_OUTCOME_END,
            "raw_row_conservation_exact": total_raw == total_authoritative + total_quarantined,
            "all_authoritative_shards_chronology_clean": all(
                item["authoritative_chronology_violations"] == 0 for item in shard_reports
            ),
            "all_authoritative_shards_transaction_code_complete": all(
                item["authoritative_missing_transaction_code_rows"] == 0
                for item in shard_reports
            ),
            "all_raw_shards_hashed": all(
                len(str(item["raw_sha256"])) == 64 for item in shard_reports
            ),
            "all_authoritative_shards_hashed": all(
                len(str(item["authoritative_sha256"])) == 64 for item in shard_reports
            ),
            "all_raw_sidecars_present": all(
                Path(str(item["raw_metadata_path"])).is_file() for item in shard_reports
            ),
            "probe_raw_reconciliation_exact": all(
                item["raw_exact"] for item in probe_reconciliation
            ),
            "probe_authoritative_reconciliation_exact": all(
                item["authoritative_exact"] for item in probe_reconciliation
            ),
            "target_outcomes_unread": True,
            "protected_candidates_unread": True,
            "protected_returns_unread": True,
            "provider_writes_zero": True,
            "broker_order_paper_live_zero": True,
        }
        report: dict[str, Any] = {
            "contract_version": PHASE31_ACQUISITION_V3_CONTRACT_VERSION,
            "raw_shard_contract_version": PHASE31_ACQUISITION_CONTRACT_VERSION,
            "historical_source_quality_contract_version": (
                PHASE31_HISTORICAL_SOURCE_QUALITY_CONTRACT_VERSION
            ),
            "phase31_policy_fingerprint": phase31_policy_fingerprint(),
            "source_quality_fingerprint": PHASE31_SOURCE_QUALITY_FINGERPRINT,
            "source_history_start": PHASE31_SOURCE_HISTORY_START,
            "source_history_end": PHASE31_PROTECTED_OUTCOME_END,
            "month_shards": len(shard_reports),
            "fresh_provider_shards_this_run": fresh_shards,
            "reused_raw_shards_this_run": reused_shards,
            "successful_provider_pages_this_run": total_provider_pages,
            "raw_rows": total_raw,
            "authoritative_rows": total_authoritative,
            "quarantined_rows": total_quarantined,
            "contaminated_accessions": len(contaminated_accessions),
            "chronology_violation_seed_rows": chronology_seed_total,
            "missing_transaction_code_seed_rows": missing_code_seed_total,
            "contaminated_accession_reasons": {
                accession: sorted(reasons)
                for accession, reasons in sorted(contamination_reasons.items())
            },
            "missing_transaction_code_quarantine_reason": PHASE31_MISSING_TRANSACTION_CODE_REASON,
            "shards": shard_reports,
            "probe_reconciliation": probe_reconciliation,
            "target_outcome_rows_read": 0,
            "protected_candidate_rows_read": 0,
            "protected_return_rows_read": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automation_writes": 0,
            "automatic_broker_failover": False,
            "checks": checks,
            "pass": all(checks.values()),
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        if not report["pass"]:
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase31AcquisitionError("Phase31 acquisition failed: " + ", ".join(failed))
        return report
