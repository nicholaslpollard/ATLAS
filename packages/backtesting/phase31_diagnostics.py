from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.providers.massive.phase31 import parse_form4_date

from .phase31_feasibility import (
    PHASE31_PROBE_WINDOWS,
    PHASE31_PUBLIC_AVAILABILITY_RULE,
)


PHASE31_FORM4_LAG_DIAGNOSTIC_CONTRACT_VERSION = (
    "phase31-form4-lag-diagnostic-v1-frozen-provider-evidence-only-no-market-outcomes"
)
PHASE31_FAILED_TARGET_HEAD = "b59a64938eb84c0c1e7df3aaea390cc437326f94"
PHASE31_FAILED_TARGET_FINGERPRINT = (
    "edb2af8b5c0f0d9273aa8120cf878f11ccc1b8fbdce31dbbf6b5fe39df366bdc"
)
PHASE31_EXPECTED_FAILED_CHECK = "transaction_dates_do_not_postdate_filings"
PHASE31_DIAGNOSTIC_SAMPLE_LIMIT = 20


class Phase31Form4LagDiagnosticError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase31Form4LagDiagnosticError(f"cannot read JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise Phase31Form4LagDiagnosticError(f"JSON artifact must be an object: {path}")
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
                    raise Phase31Form4LagDiagnosticError(
                        f"JSONL row must be an object: {path}:{line_number}"
                    )
                rows.append(item)
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase31Form4LagDiagnosticError(f"cannot read JSONL artifact {path}: {exc}") from exc
    return tuple(rows)


def _display_key(value: object) -> str:
    if value is None:
        return "<MISSING>"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value if value else "<BLANK>"
    return str(value)


def _role_bucket(row: dict[str, Any]) -> str:
    roles: list[str] = []
    if row.get("is_officer") is True:
        roles.append("officer")
    if row.get("is_director") is True:
        roles.append("director")
    if row.get("is_ten_percent_owner") is True:
        roles.append("ten_percent_owner")
    return "+".join(roles) if roles else "other_or_missing"


def _ticker_values(row: dict[str, Any]) -> tuple[str, ...]:
    raw = row.get("tickers")
    if not isinstance(raw, list):
        return ()
    return tuple(value for value in raw if isinstance(value, str) and value)


def _sample_violation(label: str, row: dict[str, Any], lag_days: int) -> dict[str, Any]:
    fields = (
        "accession_number",
        "form_type",
        "filing_date",
        "date_of_original_submission",
        "period_of_report",
        "transaction_date",
        "deemed_execution_date",
        "transaction_code",
        "transaction_acquired_disposed",
        "transaction_shares",
        "transaction_price_per_share",
        "transaction_value",
        "security_type",
        "security_title",
        "direct_or_indirect",
        "is_officer",
        "officer_title",
        "is_director",
        "is_ten_percent_owner",
        "aff_10b5_one",
        "transaction_timeliness",
        "issuer_cik",
        "owner_cik",
        "tickers",
        "filing_url",
    )
    sample = {field: row.get(field) for field in fields if field in row}
    sample["probe_window"] = label
    sample["filing_minus_transaction_calendar_days"] = lag_days
    sample["transaction_after_filing_calendar_days"] = -lag_days
    return sample


class Phase31Form4LagDiagnostic:
    """Diagnose the failed Form-4 chronology invariant from frozen local evidence only."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        provider_root = settings.resolved_path(settings.data.paths.provider)
        derived_root = settings.resolved_path(settings.data.paths.derived)
        self.evidence_root = provider_root / "massive" / "phase31_form4_feasibility" / "v1"
        self.report_root = derived_root / "strategy_evaluation" / "phase31" / "v1"

    def source_report_path(self) -> Path:
        return self.report_root / "phase31_form4_feasibility.json"

    def report_path(self) -> Path:
        return self.report_root / "phase31_form4_lag_diagnostic.json"

    def violation_path(self) -> Path:
        return self.report_root / "phase31_form4_lag_violations.jsonl"

    def evidence_path(self, label: str) -> Path:
        return self.evidence_root / f"{label}.jsonl"

    def run(self) -> dict[str, Any]:
        source_path = self.source_report_path()
        if not source_path.is_file():
            raise Phase31Form4LagDiagnosticError(
                f"missing failed feasibility report; run the frozen Phase31 feasibility target first: {source_path}"
            )
        source = _load_json(source_path)

        if source.get("phase31_feasibility_fingerprint") != PHASE31_FAILED_TARGET_FINGERPRINT:
            raise Phase31Form4LagDiagnosticError(
                "Phase31 diagnostic refuses evidence from a different feasibility fingerprint"
            )
        source_checks = source.get("checks")
        if not isinstance(source_checks, dict):
            raise Phase31Form4LagDiagnosticError("failed feasibility report is missing checks")
        source_failed_checks = sorted(name for name, passed in source_checks.items() if passed is not True)
        if source_failed_checks != [PHASE31_EXPECTED_FAILED_CHECK]:
            raise Phase31Form4LagDiagnosticError(
                "Phase31 diagnostic expected exactly the chronology failure but found: "
                + ", ".join(source_failed_checks)
            )
        if source.get("target_outcome_rows_read") != 0:
            raise Phase31Form4LagDiagnosticError("source feasibility report unexpectedly read target outcomes")
        if source.get("protected_candidate_rows_read") != 0:
            raise Phase31Form4LagDiagnosticError("source feasibility report unexpectedly read protected candidates")
        if source.get("protected_return_rows_read") != 0:
            raise Phase31Form4LagDiagnosticError("source feasibility report unexpectedly read protected returns")

        source_windows = source.get("windows")
        if not isinstance(source_windows, list):
            raise Phase31Form4LagDiagnosticError("failed feasibility report is missing window lineage")
        source_by_label = {
            str(item.get("label")): item
            for item in source_windows
            if isinstance(item, dict) and item.get("label") is not None
        }

        relation_counts: Counter[str] = Counter()
        violation_codes: Counter[str] = Counter()
        violation_security_types: Counter[str] = Counter()
        violation_acquired_disposed: Counter[str] = Counter()
        violation_direct_indirect: Counter[str] = Counter()
        violation_10b5: Counter[str] = Counter()
        violation_timeliness: Counter[str] = Counter()
        violation_roles: Counter[str] = Counter()
        violation_gap_days: Counter[str] = Counter()
        violation_date_pairs: Counter[str] = Counter()
        violation_windows: Counter[str] = Counter()
        violation_tickers: Counter[str] = Counter()
        violation_accessions: set[str] = set()
        violation_issuers: set[str] = set()
        violation_owners: set[str] = set()
        violations: list[dict[str, Any]] = []
        window_diagnostics: list[dict[str, Any]] = []
        total_transaction_rows_with_dates = 0

        for window in PHASE31_PROBE_WINDOWS:
            path = self.evidence_path(window.label)
            if not path.is_file():
                raise Phase31Form4LagDiagnosticError(f"missing frozen provider evidence: {path}")
            source_window = source_by_label.get(window.label)
            if not isinstance(source_window, dict):
                raise Phase31Form4LagDiagnosticError(
                    f"failed feasibility report is missing lineage for {window.label}"
                )
            actual_sha = sha256_file(path)
            expected_sha = source_window.get("evidence_sha256")
            if actual_sha != expected_sha:
                raise Phase31Form4LagDiagnosticError(
                    f"frozen evidence SHA mismatch for {window.label}; expected={expected_sha} actual={actual_sha}"
                )

            rows = _load_jsonl(path)
            before = same = after = 0
            dated = 0
            for row in rows:
                if row.get("record_type") != "transaction" or row.get("transaction_date") is None:
                    continue
                filing = parse_form4_date(row.get("filing_date"), field="filing_date")
                transaction = parse_form4_date(row.get("transaction_date"), field="transaction_date")
                lag_days = (filing - transaction).days
                dated += 1
                total_transaction_rows_with_dates += 1
                if lag_days > 0:
                    before += 1
                    relation_counts["transaction_before_filing"] += 1
                    continue
                if lag_days == 0:
                    same += 1
                    relation_counts["transaction_same_day_as_filing"] += 1
                    continue

                after += 1
                relation_counts["transaction_after_filing"] += 1
                violation_windows[window.label] += 1
                violation_codes[_display_key(row.get("transaction_code"))] += 1
                violation_security_types[_display_key(row.get("security_type"))] += 1
                violation_acquired_disposed[_display_key(row.get("transaction_acquired_disposed"))] += 1
                violation_direct_indirect[_display_key(row.get("direct_or_indirect"))] += 1
                violation_10b5[_display_key(row.get("aff_10b5_one"))] += 1
                violation_timeliness[_display_key(row.get("transaction_timeliness"))] += 1
                violation_roles[_role_bucket(row)] += 1
                violation_gap_days[str(-lag_days)] += 1
                violation_date_pairs[f"{row.get('filing_date')} -> {row.get('transaction_date')}"] += 1
                accession = row.get("accession_number")
                if accession is not None:
                    violation_accessions.add(str(accession))
                issuer = row.get("issuer_cik")
                if issuer is not None:
                    violation_issuers.add(str(issuer))
                owner = row.get("owner_cik")
                if owner is not None:
                    violation_owners.add(str(owner))
                for ticker in _ticker_values(row):
                    violation_tickers[ticker] += 1
                violations.append(_sample_violation(window.label, row, lag_days))

            window_diagnostics.append(
                {
                    "label": window.label,
                    "evidence_path": str(path.resolve()),
                    "evidence_sha256": actual_sha,
                    "transaction_rows_with_both_dates": dated,
                    "transaction_before_filing": before,
                    "transaction_same_day_as_filing": same,
                    "transaction_after_filing": after,
                }
            )

        violations.sort(
            key=lambda item: (
                str(item.get("probe_window") or ""),
                str(item.get("filing_date") or ""),
                str(item.get("transaction_date") or ""),
                str(item.get("accession_number") or ""),
                str(item.get("transaction_code") or ""),
                json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            )
        )
        violation_text = "".join(
            json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
            for item in violations
        )
        violation_path = self.violation_path()
        violation_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(violation_path, violation_text)
        violation_sha = sha256_file(violation_path)

        checks = {
            "failed_target_fingerprint_exact": source.get("phase31_feasibility_fingerprint")
            == PHASE31_FAILED_TARGET_FINGERPRINT,
            "source_failed_only_chronology_check": source_failed_checks
            == [PHASE31_EXPECTED_FAILED_CHECK],
            "frozen_evidence_hashes_match_source_report": len(window_diagnostics)
            == len(PHASE31_PROBE_WINDOWS),
            "chronology_violation_population_reproduced": len(violations) > 0,
            "target_outcome_rows_read_zero": source.get("target_outcome_rows_read") == 0,
            "protected_candidate_rows_read_zero": source.get("protected_candidate_rows_read") == 0,
            "protected_return_rows_read_zero": source.get("protected_return_rows_read") == 0,
            "public_availability_rule_unchanged": PHASE31_PUBLIC_AVAILABILITY_RULE
            == "NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE",
        }

        report: dict[str, Any] = {
            "contract_version": PHASE31_FORM4_LAG_DIAGNOSTIC_CONTRACT_VERSION,
            "source_failed_target_head": PHASE31_FAILED_TARGET_HEAD,
            "source_feasibility_fingerprint": PHASE31_FAILED_TARGET_FINGERPRINT,
            "source_feasibility_report_path": str(source_path.resolve()),
            "source_feasibility_status": source.get("status"),
            "source_failed_checks": source_failed_checks,
            "public_availability_rule": PHASE31_PUBLIC_AVAILABILITY_RULE,
            "diagnostic_scope": "FROZEN_LOCAL_PROVIDER_EVIDENCE_ONLY_NO_PROVIDER_CALL_NO_MARKET_OUTCOMES",
            "total_transaction_rows_with_both_dates": total_transaction_rows_with_dates,
            "lag_relation_counts": dict(sorted(relation_counts.items())),
            "violating_rows": len(violations),
            "violating_unique_accessions": len(violation_accessions),
            "violating_unique_issuers": len(violation_issuers),
            "violating_unique_owners": len(violation_owners),
            "violation_window_counts": dict(sorted(violation_windows.items())),
            "violation_transaction_code_counts": dict(sorted(violation_codes.items())),
            "violation_security_type_counts": dict(sorted(violation_security_types.items())),
            "violation_acquired_disposed_counts": dict(sorted(violation_acquired_disposed.items())),
            "violation_direct_or_indirect_counts": dict(sorted(violation_direct_indirect.items())),
            "violation_10b5_1_counts": dict(sorted(violation_10b5.items())),
            "violation_timeliness_counts": dict(sorted(violation_timeliness.items())),
            "violation_role_counts": dict(sorted(violation_roles.items())),
            "violation_transaction_after_filing_gap_days": dict(sorted(violation_gap_days.items(), key=lambda item: int(item[0]))),
            "violation_filing_to_transaction_date_pairs": dict(sorted(violation_date_pairs.items())),
            "violation_ticker_counts": dict(sorted(violation_tickers.items())),
            "violation_samples": violations[:PHASE31_DIAGNOSTIC_SAMPLE_LIMIT],
            "violation_artifact_path": str(violation_path.resolve()),
            "violation_artifact_sha256": violation_sha,
            "windows": window_diagnostics,
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
            "checks": checks,
            "status": "DIAGNOSTIC_COMPLETE" if all(checks.values()) else "DIAGNOSTIC_FAIL",
            "pass": all(checks.values()),
        }
        report_path = self.report_path()
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(report_path.resolve())
        if not report["pass"]:
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase31Form4LagDiagnosticError(
                "Phase31 Form-4 lag diagnostic failed: " + ", ".join(failed)
            )
        return report
