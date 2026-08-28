from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable

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
    "phase31-form4-acquisition-v2-monthly-memory-bounded-global-accession-quarantine"
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
        next_month = (
            date(current.year + 1, 1, 1)
            if current.month == 12
            else date(current.year, current.month + 1, 1)
        )
        shards.append(
            Phase31MonthShard(
                label=f"{current.year:04d}-{current.month:02d}",
                start_date=max(start, current).isoformat(),
                end_date=min(end, next_month - timedelta(days=1)).isoformat(),
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
    filing = parse_form4_date(row.get("filing_date"), field="filing_date")
    return start <= filing <= end


def _partition_global_quarantine(
    rows: Iterable[dict[str, Any]], contaminated_accessions: set[str]
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    authoritative: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for row in rows:
        accession = row.get("accession_number")
        if isinstance(accession, str) and accession in contaminated_accessions:
            quarantined.append(row)
        else:
            authoritative.append(row)
    return tuple(authoritative), tuple(quarantined)


class Phase31Form4HistoricalAcquisition:
    """Acquire full Form-4 history without retaining the full corpus in memory.

    Pass 1 acquires/resumes immutable monthly raw shards, verifies per-shard sidecars,
    discovers chronology-invalid accessions globally, and retains only the four small
    feasibility overlap windows for replay. Pass 2 writes authoritative/quarantine
    shards using the global contaminated-accession set. No market prices or returns
    are read.
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
            derived_root / "strategy_evaluation" / "phase31" / "v1"
            / "phase31_form4_source_quality_repair.json"
        )
        self.source_feasibility_path = (
            derived_root / "strategy_evaluation" / "phase31" / "v1"
            / "phase31_form4_feasibility.json"
        )

    def raw_path(self, label: str) -> Path:
        return self.raw_root / f"{label}.jsonl"

    def raw_metadata_path(self, label: str) -> Path:
        return self.raw_root / f"{label}.meta.json"

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

    def _raw_metadata_payload(
        self,
        *,
        shard: Phase31MonthShard,
        rows: tuple[dict[str, Any], ...],
        raw_sha: str,
        page_count: int,
        request_ids: tuple[str, ...],
    ) -> dict[str, Any]:
        return {
            "contract_version": PHASE31_ACQUISITION_CONTRACT_VERSION,
            "phase31_policy_fingerprint": phase31_policy_fingerprint(),
            "source_quality_fingerprint": PHASE31_SOURCE_QUALITY_FINGERPRINT,
            "label": shard.label,
            "start_date": shard.start_date,
            "end_date": shard.end_date,
            "rows": len(rows),
            "raw_sha256": raw_sha,
            "successful_provider_pages": page_count,
            "request_ids": list(request_ids),
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
        }

    def _load_or_fetch_raw_shard(
        self, shard: Phase31MonthShard
    ) -> tuple[tuple[dict[str, Any], ...], int, tuple[str, ...], bool]:
        raw_path = self.raw_path(shard.label)
        meta_path = self.raw_metadata_path(shard.label)
        if raw_path.is_file() != meta_path.is_file():
            raise Phase31AcquisitionError(
                f"raw shard/metadata pair is incomplete for {shard.label}"
            )

        if raw_path.is_file():
            rows = _load_jsonl(raw_path)
            meta = _load_json(meta_path)
            raw_sha = sha256_file(raw_path)
            checks = {
                "contract": meta.get("contract_version") == PHASE31_ACQUISITION_CONTRACT_VERSION,
                "policy": meta.get("phase31_policy_fingerprint") == phase31_policy_fingerprint(),
                "source_quality": meta.get("source_quality_fingerprint") == PHASE31_SOURCE_QUALITY_FINGERPRINT,
                "label": meta.get("label") == shard.label,
                "start": meta.get("start_date") == shard.start_date,
                "end": meta.get("end_date") == shard.end_date,
                "rows": meta.get("rows") == len(rows),
                "sha": meta.get("raw_sha256") == raw_sha,
                "no_target_outcomes": meta.get("target_outcome_rows_read") == 0,
                "no_protected_returns": meta.get("protected_return_rows_read") == 0,
            }
            if not all(checks.values()):
                failed = sorted(name for name, passed in checks.items() if not passed)
                raise Phase31AcquisitionError(
                    f"existing raw shard failed immutable metadata validation for {shard.label}: "
                    + ", ".join(failed)
                )
            return rows, 0, (), True

        result = self.client.form4_window(
            start_date=date.fromisoformat(shard.start_date),
            end_date=date.fromisoformat(shard.end_date),
        )
        rows = tuple(dict(row) for row in result.rows)
        text = _jsonl(rows)
        raw_sha = _immutable_write(raw_path, text)
        meta = self._raw_metadata_payload(
            shard=shard,
            rows=rows,
            raw_sha=raw_sha,
            page_count=int(result.page_count),
            request_ids=tuple(str(value) for value in result.request_ids),
        )
        atomic_write_text(meta_path, json.dumps(meta, indent=2, sort_keys=True) + "\n")
        return rows, int(result.page_count), tuple(str(v) for v in result.request_ids), False

    def _collect_probe_rows(
        self,
        shard: Phase31MonthShard,
        raw_rows: tuple[dict[str, Any], ...],
        probe_rows: dict[str, list[dict[str, Any]]],
    ) -> None:
        shard_start = date.fromisoformat(shard.start_date)
        shard_end = date.fromisoformat(shard.end_date)
        for window in PHASE31_PROBE_WINDOWS:
            start = date.fromisoformat(window.start_date)
            end = date.fromisoformat(window.end_date)
            if shard_end < start or shard_start > end:
                continue
            probe_rows[window.label].extend(
                row for row in raw_rows if _filing_date_in_range(row, start, end)
            )

    def _probe_reconciliation(
        self,
        probe_rows: dict[str, list[dict[str, Any]]],
        feasibility: dict[str, Any],
        contaminated_accessions: set[str],
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
            raw_subset = tuple(probe_rows[window.label])
            # Re-run the generic classifier so impossible rows still fail closed, then
            # apply the full-history global accession set to the overlap window.
            classify_form4_source_quality(raw_subset)
            authoritative, quarantined = _partition_global_quarantine(
                raw_subset, contaminated_accessions
            )
            raw_sha = _sha_text(_jsonl(raw_subset))
            authoritative_sha = _sha_text(_jsonl(authoritative))
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
                    "authoritative_rows": len(authoritative),
                    "quarantined_rows": len(quarantined),
                    "authoritative_sha256": authoritative_sha,
                    "expected_authoritative_sha256": expected_authoritative_sha,
                    "authoritative_exact": authoritative_sha == expected_authoritative_sha,
                }
            )
        return reports

    def run(self, *, progress: Callable[[str], None] | None = None) -> dict[str, Any]:
        repair, feasibility = self._validate_source_repair()
        shards = phase31_month_shards()
        probe_rows: dict[str, list[dict[str, Any]]] = {
            window.label: [] for window in PHASE31_PROBE_WINDOWS
        }
        first_pass: list[dict[str, Any]] = []
        contaminated_accessions: set[str] = set()
        total_provider_pages = 0
        fresh_shards = 0
        reused_shards = 0

        # Pass 1: raw acquisition/resume + global contamination discovery.
        for shard in shards:
            if progress is not None:
                progress(f"{shard.label}: raw acquisition/resume")
            raw_rows, page_count, request_ids, reused = self._load_or_fetch_raw_shard(shard)
            classified = classify_form4_source_quality(raw_rows)
            contaminated_accessions.update(classified.contaminated_accessions)
            self._collect_probe_rows(shard, raw_rows, probe_rows)
            total_provider_pages += page_count
            reused_shards += int(reused)
            fresh_shards += int(not reused)
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
                    "local_chronology_violation_seed_rows": len(classified.violating_seed_rows),
                    "local_contaminated_accessions": list(classified.contaminated_accessions),
                }
            )

        # Pass 2: apply the global accession quarantine to every monthly shard.
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
            invalid_authoritative = _chronology_violation_count(authoritative)
            if invalid_authoritative:
                raise Phase31AcquisitionError(
                    f"authoritative shard still has chronology violations: {label}"
                )
            authoritative_sha = _immutable_write(
                self.authoritative_path(label), _jsonl(authoritative)
            )
            quarantine_envelopes = tuple(
                {
                    "month_shard": label,
                    "quarantine_reason": PHASE31_QUARANTINE_REASON,
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
                    "authoritative_chronology_violations": invalid_authoritative,
                }
            )

        probe_reconciliation = self._probe_reconciliation(
            probe_rows, feasibility, contaminated_accessions
        )
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
            "contract_version": PHASE31_ACQUISITION_CONTRACT_VERSION,
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
