from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.providers.massive.phase31 import MassivePhase31Form4Client, parse_form4_date

from .phase31_feasibility import PHASE31_PROBE_WINDOWS
from .phase31_policy import (
    PHASE31_PROTECTED_OUTCOME_END,
    PHASE31_SOURCE_HISTORY_START,
    PHASE31_SOURCE_QUALITY_FINGERPRINT,
    PHASE31_SOURCE_QUALITY_TARGET_AUTHORITATIVE_ROWS,
    PHASE31_SOURCE_QUALITY_TARGET_CONTAMINATED_ACCESSIONS,
    PHASE31_SOURCE_QUALITY_TARGET_QUARANTINE_SHA256,
    PHASE31_SOURCE_QUALITY_TARGET_QUARANTINED_ROWS,
    PHASE31_SOURCE_QUALITY_TARGET_RAW_ROWS,
    PHASE31_SOURCE_QUALITY_TARGET_VIOLATION_SEED_ROWS,
    PHASE31_SOURCE_QUALITY_TARGET_WINDOW_SHA256,
    phase31_policy_fingerprint,
)
from .phase31_source_quality import (
    PHASE31_QUARANTINE_REASON,
    Phase31SourceQualityError,
    classify_form4_source_quality,
)


PHASE31_ACQUISITION_CONTRACT_VERSION = (
    "phase31-form4-acquisition-v1-monthly-raw-preserved-source-quality-authoritative"
)
PHASE31_EXPECTED_MONTH_SHARDS = 62


class Phase31AcquisitionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Phase31MonthShard:
    label: str
    start_date: str
    end_date: str


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _jsonl(rows: Iterable[dict[str, Any]]) -> str:
    return "".join(_canonical_json(row) + "\n" for row in rows)


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase31AcquisitionError(f"cannot read JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise Phase31AcquisitionError(f"JSON artifact must be an object: {path}")
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
                    raise Phase31AcquisitionError(
                        f"JSONL row must be an object: {path}:{line_number}"
                    )
                rows.append(item)
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase31AcquisitionError(f"cannot read JSONL artifact {path}: {exc}") from exc
    return tuple(rows)


def _immutable_write(path: Path, text: str) -> str:
    expected = _sha_text(text)
    if path.is_file():
        actual = sha256_file(path)
        if actual != expected:
            raise Phase31AcquisitionError(
                f"immutable Phase31 acquisition artifact drifted: {path}; "
                f"existing={actual} current={expected}"
            )
        return actual
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, text)
    actual = sha256_file(path)
    if actual != expected:
        raise Phase31AcquisitionError(f"artifact SHA mismatch after write: {path}")
    return actual


def phase31_month_shards() -> tuple[Phase31MonthShard, ...]:
    start = date.fromisoformat(PHASE31_SOURCE_HISTORY_START)
    end = date.fromisoformat(PHASE31_PROTECTED_OUTCOME_END)
    current = date(start.year, start.month, 1)
    shards: list[Phase31MonthShard] = []
    while current <= end:
        if current.month == 12:
            next_month = date(current.year + 1, 1, 1)
        else:
            next_month = date(current.year, current.month + 1, 1)
        shard_start = max(start, current)
        shard_end = min(end, next_month - timedelta(days=1))
        shards.append(
            Phase31MonthShard(
                label=f"{current.year:04d}-{current.month:02d}",
                start_date=shard_start.isoformat(),
                end_date=shard_end.isoformat(),
            )
        )
        current = next_month
    if len(shards) != PHASE31_EXPECTED_MONTH_SHARDS:
        raise Phase31AcquisitionError(
            f"Phase31 monthly shard count drifted: {len(shards)} != {PHASE31_EXPECTED_MONTH_SHARDS}"
        )
    return tuple(shards)


def _chronology_violation_count(rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        if row.get("record_type") != "transaction" or row.get("transaction_date") is None:
            continue
        filing = parse_form4_date(row.get("filing_date"), field="filing_date")
        transaction = parse_form4_date(row.get("transaction_date"), field="transaction_date")
        if transaction > filing:
            count += 1
    return count


def _filing_date_in_range(row: dict[str, Any], start: date, end: date) -> bool:
    try:
        filing = parse_form4_date(row.get("filing_date"), field="filing_date")
    except Exception as exc:  # provider evidence must fail closed
        raise Phase31AcquisitionError(f"invalid filing_date in historical Form-4 row: {exc}") from exc
    return start <= filing <= end


class Phase31Form4HistoricalAcquisition:
    """Acquire full Form-4 history while retaining raw beta-feed provenance.

    Raw provider evidence is immutable. Source-quality rules create separate
    authoritative and quarantine artifacts. No market prices or returns are read.
    """

    def __init__(self, settings: AtlasSettings, client: MassivePhase31Form4Client) -> None:
        self.settings = settings
        self.client = client
        provider_root = settings.resolved_path(settings.data.paths.provider)
        derived_root = settings.resolved_path(settings.data.paths.derived)
        self.raw_root = provider_root / "massive" / "phase31_form4_history" / "v1" / "raw"
        self.root = derived_root / "strategy_evaluation" / "phase31" / "v1" / "form4_history"
        self.authoritative_root = self.root / "authoritative"
        self.quarantine_root = self.root / "quarantine"
        self.report_path = self.root / "phase31_form4_acquisition.json"
        self.source_repair_path = (
            derived_root
            / "strategy_evaluation"
            / "phase31"
            / "v1"
            / "phase31_form4_source_quality_repair.json"
        )
        self.source_feasibility_path = (
            derived_root
            / "strategy_evaluation"
            / "phase31"
            / "v1"
            / "phase31_form4_feasibility.json"
        )

    def raw_path(self, label: str) -> Path:
        return self.raw_root / f"{label}.jsonl"

    def authoritative_path(self, label: str) -> Path:
        return self.authoritative_root / f"{label}.jsonl"

    def quarantine_path(self, label: str) -> Path:
        return self.quarantine_root / f"{label}.jsonl"

    def _validate_source_repair(self) -> tuple[dict[str, Any], dict[str, Any]]:
        repair = _load_json(self.source_repair_path)
        feasibility = _load_json(self.source_feasibility_path)
        exact = {
            "pass": repair.get("pass") is True,
            "status": repair.get("status") == "SOURCE_QUALITY_REPAIR_PASS",
            "fingerprint": repair.get("source_quality_fingerprint") == PHASE31_SOURCE_QUALITY_FINGERPRINT,
            "raw_rows": repair.get("raw_rows") == PHASE31_SOURCE_QUALITY_TARGET_RAW_ROWS,
            "seed_rows": repair.get("chronology_violation_seed_rows")
            == PHASE31_SOURCE_QUALITY_TARGET_VIOLATION_SEED_ROWS,
            "contaminated_accessions": repair.get("contaminated_accessions")
            == PHASE31_SOURCE_QUALITY_TARGET_CONTAMINATED_ACCESSIONS,
            "quarantined_rows": repair.get("quarantined_accession_rows")
            == PHASE31_SOURCE_QUALITY_TARGET_QUARANTINED_ROWS,
            "authoritative_rows": repair.get("authoritative_rows")
            == PHASE31_SOURCE_QUALITY_TARGET_AUTHORITATIVE_ROWS,
            "quarantine_sha": repair.get("quarantine_sha256")
            == PHASE31_SOURCE_QUALITY_TARGET_QUARANTINE_SHA256,
            "target_outcomes_zero": repair.get("target_outcome_rows_read") == 0,
            "protected_candidates_zero": repair.get("protected_candidate_rows_read") == 0,
            "protected_returns_zero": repair.get("protected_return_rows_read") == 0,
            "scientific_freeze_authorized": repair.get("scientific_policy_freeze_authorized") is True,
        }
        if not all(exact.values()):
            failed = sorted(name for name, passed in exact.items() if not passed)
            raise Phase31AcquisitionError(
                "source-quality target evidence is not the frozen passing replay: " + ", ".join(failed)
            )
        if feasibility.get("phase31_feasibility_fingerprint") is None:
            raise Phase31AcquisitionError("missing original feasibility fingerprint")
        return repair, feasibility

    def _probe_reconciliation(
        self,
        all_raw_rows: tuple[dict[str, Any], ...],
        feasibility: dict[str, Any],
    ) -> list[dict[str, Any]]:
        source_windows = feasibility.get("windows")
        if not isinstance(source_windows, list):
            raise Phase31AcquisitionError("original feasibility report has no windows")
        source_by_label = {
            str(item.get("label")): item
            for item in source_windows
            if isinstance(item, dict) and item.get("label") is not None
        }
        reports: list[dict[str, Any]] = []
        for window in PHASE31_PROBE_WINDOWS:
            start = date.fromisoformat(window.start_date)
            end = date.fromisoformat(window.end_date)
            raw_subset = tuple(
                row for row in all_raw_rows if _filing_date_in_range(row, start, end)
            )
            classified = classify_form4_source_quality(raw_subset)
            raw_sha = _sha_text(_jsonl(raw_subset))
            authoritative_sha = _sha_text(_jsonl(classified.authoritative_rows))
            source_window = source_by_label.get(window.label)
            if not isinstance(source_window, dict):
                raise Phase31AcquisitionError(f"missing original probe lineage: {window.label}")
            expected_raw_sha = str(source_window.get("evidence_sha256") or "")
            expected_authoritative_sha = PHASE31_SOURCE_QUALITY_TARGET_WINDOW_SHA256[window.label]
            reports.append(
                {
                    "label": window.label,
                    "raw_rows": len(raw_subset),
                    "raw_sha256": raw_sha,
                    "expected_raw_sha256": expected_raw_sha,
                    "raw_exact": raw_sha == expected_raw_sha,
                    "authoritative_rows": len(classified.authoritative_rows),
                    "quarantined_rows": len(classified.quarantined_rows),
                    "authoritative_sha256": authoritative_sha,
                    "expected_authoritative_sha256": expected_authoritative_sha,
                    "authoritative_exact": authoritative_sha == expected_authoritative_sha,
                }
            )
        return reports

    def run(self, *, progress: callable | None = None) -> dict[str, Any]:
        repair, feasibility = self._validate_source_repair()
        shard_reports: list[dict[str, Any]] = []
        all_raw: list[dict[str, Any]] = []
        total_provider_pages = 0
        total_fresh_shards = 0
        total_reused_shards = 0
        total_raw = 0
        total_authoritative = 0
        total_quarantined = 0
        contaminated_accessions: set[str] = set()

        for shard in phase31_month_shards():
            raw_path = self.raw_path(shard.label)
            if raw_path.is_file():
                raw_rows = _load_jsonl(raw_path)
                page_count = 0
                request_ids: tuple[str, ...] = ()
                reused = True
                total_reused_shards += 1
                if progress is not None:
                    progress(f"{shard.label}: reuse immutable raw shard rows={len(raw_rows)}")
            else:
                if progress is not None:
                    progress(f"{shard.label}: provider acquisition {shard.start_date}..{shard.end_date}")
                result = self.client.form4_window(
                    start_date=date.fromisoformat(shard.start_date),
                    end_date=date.fromisoformat(shard.end_date),
                )
                raw_rows = tuple(dict(row) for row in result.rows)
                page_count = int(result.page_count)
                request_ids = tuple(str(value) for value in result.request_ids)
                _immutable_write(raw_path, _jsonl(raw_rows))
                reused = False
                total_fresh_shards += 1
                total_provider_pages += page_count

            raw_sha = sha256_file(raw_path)
            classified = classify_form4_source_quality(raw_rows)
            authoritative_path = self.authoritative_path(shard.label)
            quarantine_path = self.quarantine_path(shard.label)
            authoritative_sha = _immutable_write(
                authoritative_path, _jsonl(classified.authoritative_rows)
            )
            quarantine_envelopes = tuple(
                {
                    "month_shard": shard.label,
                    "quarantine_reason": PHASE31_QUARANTINE_REASON,
                    "quarantine_scope": "ENTIRE_ACCESSION",
                    "raw_row": row,
                }
                for row in classified.quarantined_rows
            )
            quarantine_sha = _immutable_write(quarantine_path, _jsonl(quarantine_envelopes))
            invalid_authoritative = _chronology_violation_count(classified.authoritative_rows)
            if invalid_authoritative:
                raise Phase31AcquisitionError(
                    f"authoritative shard still has chronology violations: {shard.label}"
                )

            contaminated_accessions.update(classified.contaminated_accessions)
            all_raw.extend(raw_rows)
            total_raw += len(raw_rows)
            total_authoritative += len(classified.authoritative_rows)
            total_quarantined += len(classified.quarantined_rows)
            shard_reports.append(
                {
                    **asdict(shard),
                    "reused_raw_shard": reused,
                    "provider_pages_this_run": page_count,
                    "request_ids_this_run": list(request_ids),
                    "raw_rows": len(raw_rows),
                    "raw_path": str(raw_path.resolve()),
                    "raw_sha256": raw_sha,
                    "chronology_violation_seed_rows": len(classified.violating_seed_rows),
                    "contaminated_accessions": list(classified.contaminated_accessions),
                    "quarantined_rows": len(classified.quarantined_rows),
                    "quarantine_path": str(quarantine_path.resolve()),
                    "quarantine_sha256": quarantine_sha,
                    "authoritative_rows": len(classified.authoritative_rows),
                    "authoritative_path": str(authoritative_path.resolve()),
                    "authoritative_sha256": authoritative_sha,
                    "authoritative_chronology_violations": invalid_authoritative,
                }
            )

        all_raw_rows = tuple(all_raw)
        probe_reconciliation = self._probe_reconciliation(all_raw_rows, feasibility)
        checks = {
            "source_quality_target_replay_exact": repair.get("pass") is True,
            "scientific_policy_frozen": len(phase31_policy_fingerprint()) == 64,
            "monthly_shard_count_exact": len(shard_reports) == PHASE31_EXPECTED_MONTH_SHARDS,
            "full_history_scope_exact": shard_reports[0]["start_date"] == PHASE31_SOURCE_HISTORY_START
            and shard_reports[-1]["end_date"] == PHASE31_PROTECTED_OUTCOME_END,
            "raw_row_conservation_exact": total_raw == total_authoritative + total_quarantined,
            "all_authoritative_shards_chronology_clean": all(
                item["authoritative_chronology_violations"] == 0 for item in shard_reports
            ),
            "all_raw_shards_hashed": all(len(str(item["raw_sha256"])) == 64 for item in shard_reports),
            "all_authoritative_shards_hashed": all(
                len(str(item["authoritative_sha256"])) == 64 for item in shard_reports
            ),
            "probe_raw_reconciliation_exact": all(item["raw_exact"] for item in probe_reconciliation),
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
            "contract_version": PHASE31_ACQUISITION_CONTRACT_VERSION,
            "phase31_policy_fingerprint": phase31_policy_fingerprint(),
            "source_quality_fingerprint": PHASE31_SOURCE_QUALITY_FINGERPRINT,
            "source_history_start": PHASE31_SOURCE_HISTORY_START,
            "source_history_end": PHASE31_PROTECTED_OUTCOME_END,
            "month_shards": len(shard_reports),
            "fresh_provider_shards_this_run": total_fresh_shards,
            "reused_raw_shards_this_run": total_reused_shards,
            "successful_provider_pages_this_run": total_provider_pages,
            "raw_rows": total_raw,
            "authoritative_rows": total_authoritative,
            "quarantined_rows": total_quarantined,
            "contaminated_accessions": len(contaminated_accessions),
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
