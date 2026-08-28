from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.providers.massive.phase31 import parse_form4_date

from .phase31_feasibility import (
    PHASE31_PROBE_WINDOWS,
    PHASE31_PUBLIC_AVAILABILITY_RULE,
)


PHASE31_SOURCE_QUALITY_CONTRACT_VERSION = (
    "phase31-form4-source-quality-v1-raw-preserved-accession-quarantine-no-market-outcomes"
)
PHASE31_SOURCE_QUALITY_POLICY = "RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE"
PHASE31_QUARANTINE_REASON = "SOURCE_TRANSACTION_DATE_POSTDATES_FILING_DATE"
PHASE31_FAILED_TARGET_HEAD = "b59a64938eb84c0c1e7df3aaea390cc437326f94"
PHASE31_FAILED_TARGET_FINGERPRINT = (
    "edb2af8b5c0f0d9273aa8120cf878f11ccc1b8fbdce31dbbf6b5fe39df366bdc"
)
PHASE31_EXPECTED_FAILED_CHECK = "transaction_dates_do_not_postdate_filings"
PHASE31_EXPECTED_DIAGNOSTIC_VIOLATION_SHA256 = (
    "3fac83bf60206e4056d6d9b1fd285b79f7a6b366b7fb154aefd4daaea4abc044"
)


class Phase31SourceQualityError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Phase31SourceQualityClassification:
    authoritative_rows: tuple[dict[str, Any], ...]
    quarantined_rows: tuple[dict[str, Any], ...]
    violating_seed_rows: tuple[dict[str, Any], ...]
    contaminated_accessions: tuple[str, ...]


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _jsonl(rows: Iterable[dict[str, Any]]) -> str:
    return "".join(_canonical_json(row) + "\n" for row in rows)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase31SourceQualityError(f"cannot read JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise Phase31SourceQualityError(f"JSON artifact must be an object: {path}")
    return payload


def _load_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, raw in enumerate(handle, start=1):
                line = raw.strip()
                if not line:
                    continue
                item = json.loads(line)
                if not isinstance(item, dict):
                    raise Phase31SourceQualityError(
                        f"JSONL row must be an object: {path}:{line_number}"
                    )
                rows.append(item)
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase31SourceQualityError(f"cannot read JSONL artifact {path}: {exc}") from exc
    return tuple(rows)


def _source_quality_fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE31_SOURCE_QUALITY_CONTRACT_VERSION,
        "policy": PHASE31_SOURCE_QUALITY_POLICY,
        "quarantine_trigger": "transaction row has transaction_date > filing_date",
        "quarantine_scope": "entire accession_number containing any trigger row",
        "raw_provider_evidence": "immutable and retained unchanged",
        "authoritative_corpus_requirement": "zero transaction_date > filing_date rows",
        "correction_policy": "no date coercion, no field swap, no inferred reassignment",
        "ticker_policy": "provider-native ticker strings/case preserved",
        "source_failed_target_head": PHASE31_FAILED_TARGET_HEAD,
        "source_feasibility_fingerprint": PHASE31_FAILED_TARGET_FINGERPRINT,
        "source_expected_failed_check": PHASE31_EXPECTED_FAILED_CHECK,
        "public_availability_rule": PHASE31_PUBLIC_AVAILABILITY_RULE,
        "target_market_outcomes": "forbidden",
        "protected_market_outcomes": "forbidden",
        "provider_calls": 0,
        "broker_order_paper_live_authority": 0,
    }


def phase31_source_quality_fingerprint() -> str:
    return hashlib.sha256(
        _canonical_json(_source_quality_fingerprint_payload()).encode("utf-8")
    ).hexdigest()


def _is_chronology_violation(row: dict[str, Any]) -> bool:
    if row.get("record_type") != "transaction" or row.get("transaction_date") is None:
        return False
    filing = parse_form4_date(row.get("filing_date"), field="filing_date")
    transaction = parse_form4_date(row.get("transaction_date"), field="transaction_date")
    return transaction > filing


def classify_form4_source_quality(
    rows: Iterable[dict[str, Any]],
) -> Phase31SourceQualityClassification:
    """Fail closed on impossible Form-4 chronology without using ticker/code/performance.

    Any transaction row whose provider transaction_date is later than its filing_date
    contaminates the whole SEC accession. Raw rows are never corrected or reassigned.
    """
    materialized = tuple(dict(row) for row in rows)
    contaminated: set[str] = set()
    seeds: list[dict[str, Any]] = []

    for row in materialized:
        if not _is_chronology_violation(row):
            continue
        accession = row.get("accession_number")
        if not isinstance(accession, str) or not accession.strip():
            raise Phase31SourceQualityError(
                "chronology-violating Form-4 row is missing accession_number; cannot quarantine safely"
            )
        contaminated.add(accession)
        seeds.append(row)

    authoritative: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for row in materialized:
        accession = row.get("accession_number")
        if isinstance(accession, str) and accession in contaminated:
            quarantined.append(row)
        else:
            authoritative.append(row)

    sort_key = lambda row: (
        str(row.get("filing_date") or ""),
        str(row.get("accession_number") or ""),
        str(row.get("owner_cik") or ""),
        str(row.get("record_type") or ""),
        str(row.get("transaction_date") or ""),
        str(row.get("transaction_code") or ""),
        str(row.get("security_title") or ""),
        _canonical_json(row),
    )
    return Phase31SourceQualityClassification(
        authoritative_rows=tuple(sorted(authoritative, key=sort_key)),
        quarantined_rows=tuple(sorted(quarantined, key=sort_key)),
        violating_seed_rows=tuple(sorted(seeds, key=sort_key)),
        contaminated_accessions=tuple(sorted(contaminated)),
    )


def _count_chronology_violations(rows: Iterable[dict[str, Any]]) -> int:
    return sum(1 for row in rows if _is_chronology_violation(row))


def _present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def _ticker_values(rows: Iterable[dict[str, Any]]) -> set[str]:
    values: set[str] = set()
    for row in rows:
        tickers = row.get("tickers") or []
        if isinstance(tickers, list):
            values.update(ticker for ticker in tickers if isinstance(ticker, str) and ticker)
    return values


class Phase31Form4SourceQualityRepair:
    """Reconcile the failed feasibility evidence without a provider or market-outcome read."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        provider_root = settings.resolved_path(settings.data.paths.provider)
        derived_root = settings.resolved_path(settings.data.paths.derived)
        self.evidence_root = provider_root / "massive" / "phase31_form4_feasibility" / "v1"
        self.report_root = derived_root / "strategy_evaluation" / "phase31" / "v1"
        self.authoritative_root = self.report_root / "source_quality_authoritative"

    def source_report_path(self) -> Path:
        return self.report_root / "phase31_form4_feasibility.json"

    def diagnostic_report_path(self) -> Path:
        return self.report_root / "phase31_form4_lag_diagnostic.json"

    def diagnostic_violation_path(self) -> Path:
        return self.report_root / "phase31_form4_lag_violations.jsonl"

    def quarantine_path(self) -> Path:
        return self.report_root / "phase31_form4_source_quality_quarantine.jsonl"

    def report_path(self) -> Path:
        return self.report_root / "phase31_form4_source_quality_repair.json"

    def evidence_path(self, label: str) -> Path:
        return self.evidence_root / f"{label}.jsonl"

    def authoritative_path(self, label: str) -> Path:
        return self.authoritative_root / f"{label}.jsonl"

    def run(self) -> dict[str, Any]:
        source_path = self.source_report_path()
        diagnostic_path = self.diagnostic_report_path()
        violation_path = self.diagnostic_violation_path()
        if not source_path.is_file() or not diagnostic_path.is_file() or not violation_path.is_file():
            raise Phase31SourceQualityError(
                "missing frozen failed-feasibility/diagnostic evidence; run the accepted diagnostic first"
            )

        source = _load_json(source_path)
        diagnostic = _load_json(diagnostic_path)
        if source.get("phase31_feasibility_fingerprint") != PHASE31_FAILED_TARGET_FINGERPRINT:
            raise Phase31SourceQualityError("source feasibility fingerprint does not match failed target")
        source_checks = source.get("checks")
        if not isinstance(source_checks, dict):
            raise Phase31SourceQualityError("source feasibility report is missing checks")
        failed_checks = sorted(name for name, passed in source_checks.items() if passed is not True)
        if failed_checks != [PHASE31_EXPECTED_FAILED_CHECK]:
            raise Phase31SourceQualityError(
                "repair requires the original target to have failed only the chronology invariant"
            )
        if diagnostic.get("pass") is not True or diagnostic.get("status") != "DIAGNOSTIC_COMPLETE":
            raise Phase31SourceQualityError("chronology diagnostic is not an accepted complete diagnostic")
        if diagnostic.get("source_feasibility_fingerprint") != PHASE31_FAILED_TARGET_FINGERPRINT:
            raise Phase31SourceQualityError("diagnostic lineage does not match failed feasibility")
        actual_violation_sha = sha256_file(violation_path)
        if actual_violation_sha != PHASE31_EXPECTED_DIAGNOSTIC_VIOLATION_SHA256:
            raise Phase31SourceQualityError(
                "diagnostic violation artifact drifted from the target-machine root-cause evidence"
            )
        if diagnostic.get("violation_artifact_sha256") != actual_violation_sha:
            raise Phase31SourceQualityError("diagnostic report and violation artifact SHA disagree")

        for key in (
            "target_outcome_rows_read",
            "protected_candidate_rows_read",
            "protected_return_rows_read",
            "provider_reads",
            "provider_writes",
            "broker_reads",
            "broker_writes",
            "order_writes",
            "paper_submits",
            "live_writes",
        ):
            if diagnostic.get(key) != 0:
                raise Phase31SourceQualityError(f"diagnostic authority boundary violated: {key}")

        source_windows = source.get("windows")
        if not isinstance(source_windows, list):
            raise Phase31SourceQualityError("source feasibility report is missing window lineage")
        source_by_label = {
            str(item.get("label")): item
            for item in source_windows
            if isinstance(item, dict) and item.get("label") is not None
        }

        quarantine_envelopes: list[dict[str, Any]] = []
        window_reports: list[dict[str, Any]] = []
        aggregate_codes: Counter[str] = Counter()
        raw_total = 0
        authoritative_total = 0
        quarantined_total = 0
        seed_total = 0
        contaminated_accessions: set[str] = set()

        for window in PHASE31_PROBE_WINDOWS:
            raw_path = self.evidence_path(window.label)
            source_window = source_by_label.get(window.label)
            if not raw_path.is_file() or not isinstance(source_window, dict):
                raise Phase31SourceQualityError(f"missing raw/source lineage for {window.label}")
            raw_sha = sha256_file(raw_path)
            if raw_sha != source_window.get("evidence_sha256"):
                raise Phase31SourceQualityError(
                    f"immutable raw evidence SHA mismatch for {window.label}"
                )

            raw_rows = _load_jsonl(raw_path)
            classified = classify_form4_source_quality(raw_rows)
            authoritative_rows = classified.authoritative_rows
            quarantined_rows = classified.quarantined_rows
            seed_rows = classified.violating_seed_rows
            contaminated_accessions.update(classified.contaminated_accessions)

            if len(raw_rows) != len(authoritative_rows) + len(quarantined_rows):
                raise Phase31SourceQualityError(f"row conservation failed for {window.label}")
            if _count_chronology_violations(authoritative_rows) != 0:
                raise Phase31SourceQualityError(
                    f"authoritative corpus still contains chronology violations for {window.label}"
                )

            authoritative_path = self.authoritative_path(window.label)
            authoritative_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(authoritative_path, _jsonl(authoritative_rows))
            authoritative_sha = sha256_file(authoritative_path)

            for row in quarantined_rows:
                quarantine_envelopes.append(
                    {
                        "probe_window": window.label,
                        "quarantine_reason": PHASE31_QUARANTINE_REASON,
                        "quarantine_scope": "ENTIRE_ACCESSION",
                        "raw_row": row,
                    }
                )

            transaction_rows = tuple(
                row for row in authoritative_rows if row.get("record_type") == "transaction"
            )
            codes = Counter(
                str(row.get("transaction_code"))
                for row in transaction_rows
                if _present(row.get("transaction_code"))
            )
            aggregate_codes.update(codes)
            ticker_linked = sum(1 for row in authoritative_rows if _present(row.get("tickers")))
            window_reports.append(
                {
                    "label": window.label,
                    "raw_evidence_path": str(raw_path.resolve()),
                    "raw_evidence_sha256": raw_sha,
                    "raw_rows": len(raw_rows),
                    "chronology_violation_seed_rows": len(seed_rows),
                    "contaminated_accessions": list(classified.contaminated_accessions),
                    "quarantined_accession_rows": len(quarantined_rows),
                    "authoritative_rows": len(authoritative_rows),
                    "authoritative_transaction_rows": len(transaction_rows),
                    "authoritative_unique_tickers": len(_ticker_values(authoritative_rows)),
                    "authoritative_ticker_linked_rows": ticker_linked,
                    "authoritative_purchase_rows_P": codes.get("P", 0),
                    "authoritative_sale_rows_S": codes.get("S", 0),
                    "authoritative_chronology_violation_rows": 0,
                    "authoritative_path": str(authoritative_path.resolve()),
                    "authoritative_sha256": authoritative_sha,
                    "authoritative_nonempty": bool(authoritative_rows),
                    "authoritative_transaction_nonempty": bool(transaction_rows),
                    "authoritative_ticker_linked_nonempty": ticker_linked > 0,
                }
            )
            raw_total += len(raw_rows)
            authoritative_total += len(authoritative_rows)
            quarantined_total += len(quarantined_rows)
            seed_total += len(seed_rows)

        quarantine_envelopes.sort(
            key=lambda item: (
                str(item.get("probe_window") or ""),
                str(item["raw_row"].get("filing_date") or ""),
                str(item["raw_row"].get("accession_number") or ""),
                str(item["raw_row"].get("transaction_date") or ""),
                _canonical_json(item["raw_row"]),
            )
        )
        quarantine_path = self.quarantine_path()
        atomic_write_text(quarantine_path, _jsonl(quarantine_envelopes))
        quarantine_sha = sha256_file(quarantine_path)

        raw_violation_count = sum(
            int(window["chronology_violation_seed_rows"]) for window in window_reports
        )
        checks = {
            "source_failed_only_original_chronology_gate": failed_checks
            == [PHASE31_EXPECTED_FAILED_CHECK],
            "diagnostic_complete_and_lineage_exact": diagnostic.get("pass") is True
            and diagnostic.get("source_feasibility_fingerprint")
            == PHASE31_FAILED_TARGET_FINGERPRINT,
            "diagnostic_violation_artifact_exact": actual_violation_sha
            == PHASE31_EXPECTED_DIAGNOSTIC_VIOLATION_SHA256,
            "raw_provider_evidence_hashes_preserved": all(
                len(str(window["raw_evidence_sha256"])) == 64 for window in window_reports
            ),
            "raw_violation_population_reproduced": raw_violation_count > 0
            and raw_violation_count == diagnostic.get("violating_rows"),
            "quarantine_is_accession_level_and_complete": quarantined_total >= seed_total > 0
            and bool(contaminated_accessions),
            "raw_row_conservation_exact": raw_total == authoritative_total + quarantined_total,
            "authoritative_corpus_has_zero_post_filing_transactions": all(
                window["authoritative_chronology_violation_rows"] == 0
                for window in window_reports
            ),
            "all_authoritative_probe_windows_nonempty": all(
                bool(window["authoritative_nonempty"]) for window in window_reports
            ),
            "all_authoritative_probe_windows_have_transactions": all(
                bool(window["authoritative_transaction_nonempty"]) for window in window_reports
            ),
            "all_authoritative_probe_windows_have_ticker_linkage": all(
                bool(window["authoritative_ticker_linked_nonempty"]) for window in window_reports
            ),
            "authoritative_purchase_population_present": aggregate_codes.get("P", 0) > 0,
            "authoritative_sale_population_present": aggregate_codes.get("S", 0) > 0,
            "all_original_nonchronology_checks_remain_pass": all(
                passed is True
                for name, passed in source_checks.items()
                if name != PHASE31_EXPECTED_FAILED_CHECK
            ),
            "public_availability_rule_unchanged": PHASE31_PUBLIC_AVAILABILITY_RULE
            == "NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE",
            "target_and_protected_outcomes_unread": source.get("target_outcome_rows_read") == 0
            and source.get("protected_candidate_rows_read") == 0
            and source.get("protected_return_rows_read") == 0,
            "external_authority_zero": all(
                diagnostic.get(key) == 0
                for key in (
                    "provider_reads",
                    "provider_writes",
                    "broker_reads",
                    "broker_writes",
                    "order_writes",
                    "paper_submits",
                    "live_writes",
                )
            ),
        }

        report: dict[str, Any] = {
            "contract_version": PHASE31_SOURCE_QUALITY_CONTRACT_VERSION,
            "source_quality_fingerprint": phase31_source_quality_fingerprint(),
            "source_quality_policy": PHASE31_SOURCE_QUALITY_POLICY,
            "quarantine_reason": PHASE31_QUARANTINE_REASON,
            "quarantine_scope": "ENTIRE_ACCESSION",
            "source_failed_target_head": PHASE31_FAILED_TARGET_HEAD,
            "source_feasibility_fingerprint": PHASE31_FAILED_TARGET_FINGERPRINT,
            "source_original_status": source.get("status"),
            "source_original_failed_checks": failed_checks,
            "diagnostic_status": diagnostic.get("status"),
            "diagnostic_violation_artifact_sha256": actual_violation_sha,
            "public_availability_rule": PHASE31_PUBLIC_AVAILABILITY_RULE,
            "raw_rows": raw_total,
            "chronology_violation_seed_rows": seed_total,
            "contaminated_accessions": len(contaminated_accessions),
            "quarantined_accession_rows": quarantined_total,
            "authoritative_rows": authoritative_total,
            "aggregate_authoritative_transaction_code_counts": dict(sorted(aggregate_codes.items())),
            "windows": window_reports,
            "quarantine_path": str(quarantine_path.resolve()),
            "quarantine_sha256": quarantine_sha,
            "target_outcome_rows_read": 0,
            "protected_candidate_rows_read": 0,
            "protected_return_rows_read": 0,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automatic_broker_failover": False,
            "alpha_hypotheses_frozen": False,
            "alpha_support_granted": False,
            "phase32_entry_satisfied": False,
            "scientific_policy_freeze_authorized": all(checks.values()),
            "checks": checks,
            "status": "SOURCE_QUALITY_REPAIR_PASS" if all(checks.values()) else "SOURCE_QUALITY_REPAIR_FAIL",
            "pass": all(checks.values()),
        }
        report_path = self.report_path()
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(report_path.resolve())

        if not report["pass"]:
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase31SourceQualityError(
                "Phase31 Form-4 source-quality repair failed: " + ", ".join(failed)
            )
        return report
