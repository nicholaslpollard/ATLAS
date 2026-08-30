from __future__ import annotations

import hashlib
import html
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from packages.backtesting.alpha_gate_beneficial_ownership_feasibility import (
    BENEFICIAL_OWNERSHIP_QUARTERS,
    BeneficialOwnershipFeasibilityError,
    BeneficialOwnershipIndexRow,
    _decision_session,
    _resolve_identity,
    parse_master_index,
    parse_submission_metadata,
)
from packages.backtesting.alpha_gate_beneficial_ownership_scientific_policy import (
    BENEFICIAL_OWNERSHIP_DEVELOPMENT_LAST_SIGNAL,
    BENEFICIAL_OWNERSHIP_DEVELOPMENT_SAMPLE_PER_FORM_FAMILY,
    BENEFICIAL_OWNERSHIP_ENTRY_QUARTER_INDEXES,
    BENEFICIAL_OWNERSHIP_ENTRY_SOURCE_REPAIR_FINGERPRINT,
    BENEFICIAL_OWNERSHIP_ENTRY_SOURCE_REPAIR_STATUS,
    BENEFICIAL_OWNERSHIP_ENTRY_SUBMISSION_SUCCESS,
    BENEFICIAL_OWNERSHIP_ENTRY_UNAMBIGUOUS_MAPPINGS,
    BENEFICIAL_OWNERSHIP_ENTRY_UNIQUE_SUBJECT_CIKS,
    BENEFICIAL_OWNERSHIP_HYPOTHESES,
    BENEFICIAL_OWNERSHIP_PERFORMANCE_SIGNAL_START,
    BENEFICIAL_OWNERSHIP_PROTECTED_LAST_SIGNAL,
    BENEFICIAL_OWNERSHIP_PROTECTED_SAMPLE_PER_FORM_FAMILY,
    BENEFICIAL_OWNERSHIP_PROTECTED_START,
    BENEFICIAL_OWNERSHIP_SCIENTIFIC_CONTRACT,
    BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT,
    beneficial_ownership_scientific_fingerprint,
)
from packages.backtesting.alpha_gate_beneficial_ownership_source_repair import (
    BENEFICIAL_OWNERSHIP_REPAIR_REPORT_RELATIVE,
    BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_CONTRACT,
    BeneficialOwnershipSourceFeasibilityV2,
    authoritative_subject_cik,
    dedupe_discovery_v2,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.providers.massive.xbrl_pit import MassiveCIKPITReferenceProvider
from packages.providers.sec_edgar_archive import SECEDGARArchiveClient


BENEFICIAL_OWNERSHIP_PREDICTOR_CONTRACT = (
    "alpha-gate-beneficial-ownership-predictor-v1-initial-percent-intent-source-only"
)
BENEFICIAL_OWNERSHIP_DEVELOPMENT_ROOT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/beneficial_ownership_development_v1"
)
BENEFICIAL_OWNERSHIP_PREDICTOR_ROWS_RELATIVE = (
    BENEFICIAL_OWNERSHIP_DEVELOPMENT_ROOT_RELATIVE / "predictor_rows.jsonl"
)
BENEFICIAL_OWNERSHIP_PREDICTOR_REPORT_RELATIVE = (
    BENEFICIAL_OWNERSHIP_DEVELOPMENT_ROOT_RELATIVE / "predictor_report.json"
)

_STRUCTURED_PERCENT_RE = re.compile(
    r"<(?:[A-Za-z0-9_]+:)?(?:percentOfClass|classPercent)\b[^>]*>\s*"
    r"([0-9]+(?:\.[0-9]+)?)\s*</(?:[A-Za-z0-9_]+:)?(?:percentOfClass|classPercent)>",
    re.IGNORECASE,
)
_LEGACY_PERCENT_RE = re.compile(
    r"PERCENT\s+OF\s+CLASS\s+REPRESENTED\s+BY\s+AMOUNT\s+IN\s+ROW\s*"
    r"\(?\s*(?:11|9)\s*\)?\s*[:|\-]*\s*([0-9]+(?:\.[0-9]+)?)\s*%",
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


class BeneficialOwnershipPredictorError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _as_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == text else None


def extract_percent_of_class_values(text: str) -> tuple[float, ...]:
    """Extract filing-reported cover-page ownership percentages without summing group members."""
    values: list[float] = []
    for match in _STRUCTURED_PERCENT_RE.finditer(text):
        try:
            value = float(match.group(1))
        except ValueError:
            continue
        if math.isfinite(value) and 0.0 < value <= 100.0:
            values.append(value)

    normalized = html.unescape(_TAG_RE.sub(" ", text))
    normalized = _SPACE_RE.sub(" ", normalized)
    for match in _LEGACY_PERCENT_RE.finditer(normalized):
        try:
            value = float(match.group(1))
        except ValueError:
            continue
        if math.isfinite(value) and 0.0 < value <= 100.0:
            values.append(value)

    return tuple(sorted(set(values)))


def maximum_percent_of_class(text: str) -> float | None:
    values = extract_percent_of_class_values(text)
    return max(values) if values else None


def candidate_for(*, form_family: str, percent_of_class: float) -> str | None:
    for spec in BENEFICIAL_OWNERSHIP_HYPOTHESES:
        if spec.form_family != form_family:
            continue
        if percent_of_class < spec.percent_min:
            continue
        if spec.percent_max_exclusive is not None and percent_of_class >= spec.percent_max_exclusive:
            continue
        return spec.candidate_id
    return None


def _source_stage(filing_date: date) -> str | None:
    development_start = date.fromisoformat(BENEFICIAL_OWNERSHIP_PERFORMANCE_SIGNAL_START)
    development_end = date.fromisoformat(BENEFICIAL_OWNERSHIP_DEVELOPMENT_LAST_SIGNAL)
    protected_start = date.fromisoformat(BENEFICIAL_OWNERSHIP_PROTECTED_START)
    protected_end = date.fromisoformat(BENEFICIAL_OWNERSHIP_PROTECTED_LAST_SIGNAL)
    if development_start <= filing_date <= development_end:
        return "DEVELOPMENT"
    if protected_start <= filing_date <= protected_end:
        return "PROTECTED"
    return None


def _decision_stage(decision_date: date) -> str | None:
    return _source_stage(decision_date)


def _rank_rows(
    rows: Iterable[BeneficialOwnershipIndexRow], *, stage: str, form_family: str
) -> tuple[BeneficialOwnershipIndexRow, ...]:
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                hashlib.sha256(
                    f"{row.accession_number}:{BENEFICIAL_OWNERSHIP_SCIENTIFIC_CONTRACT}:"
                    f"{stage}:{form_family}".encode("ascii")
                ).hexdigest(),
                row.accession_number,
            ),
        )
    )


def select_source_sample(
    rows: Iterable[BeneficialOwnershipIndexRow],
) -> tuple[BeneficialOwnershipIndexRow, ...]:
    grouped: dict[tuple[str, str], list[BeneficialOwnershipIndexRow]] = defaultdict(list)
    for row in rows:
        if row.form_class not in {"13D_INITIAL", "13G_INITIAL"}:
            continue
        filed = _as_date(row.filing_date)
        if filed is None:
            continue
        stage = _source_stage(filed)
        if stage is not None:
            grouped[(stage, row.form_class)].append(row)

    output: list[BeneficialOwnershipIndexRow] = []
    for stage in ("DEVELOPMENT", "PROTECTED"):
        limit = (
            BENEFICIAL_OWNERSHIP_DEVELOPMENT_SAMPLE_PER_FORM_FAMILY
            if stage == "DEVELOPMENT"
            else BENEFICIAL_OWNERSHIP_PROTECTED_SAMPLE_PER_FORM_FAMILY
        )
        for form_family in ("13D_INITIAL", "13G_INITIAL"):
            ranked = _rank_rows(grouped.get((stage, form_family), ()), stage=stage, form_family=form_family)
            output.extend(ranked[:limit])
    return tuple(sorted(output, key=lambda row: (row.filing_date, row.accession_number)))


class BeneficialOwnershipPredictorBuilder:
    """Build source-only initial 13D/13G predictor rows. No market outcomes are available here."""

    def __init__(
        self,
        settings: AtlasSettings,
        archive_client: SECEDGARArchiveClient,
        reference_provider: MassiveCIKPITReferenceProvider,
        *,
        progress_callback: Any | None = None,
    ) -> None:
        self.settings = settings
        self.source = BeneficialOwnershipSourceFeasibilityV2(
            settings, archive_client, reference_provider
        )
        self.derived_root = settings.resolved_path(settings.data.paths.derived)
        self.progress_callback = progress_callback

    def _progress(self, message: str) -> None:
        if self.progress_callback is not None:
            self.progress_callback(message)

    def _accepted_source_report(self) -> dict[str, Any]:
        path = self.derived_root / BENEFICIAL_OWNERSHIP_REPAIR_REPORT_RELATIVE
        if not path.is_file():
            raise BeneficialOwnershipPredictorError(
                f"accepted beneficial-ownership v2 source report is missing: {path}"
            )
        report = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise BeneficialOwnershipPredictorError("beneficial-ownership source report is not an object")
        exact = {
            "contract_version": BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_CONTRACT,
            "source_repair_fingerprint": BENEFICIAL_OWNERSHIP_ENTRY_SOURCE_REPAIR_FINGERPRINT,
            "status": BENEFICIAL_OWNERSHIP_ENTRY_SOURCE_REPAIR_STATUS,
        }
        for key, expected in exact.items():
            if report.get(key) != expected:
                raise BeneficialOwnershipPredictorError(
                    f"accepted beneficial-ownership source report {key} mismatch"
                )
        numeric = {
            "successful_indexes": BENEFICIAL_OWNERSHIP_ENTRY_QUARTER_INDEXES,
            "submission_success": BENEFICIAL_OWNERSHIP_ENTRY_SUBMISSION_SUCCESS,
            "unique_subject_ciks": BENEFICIAL_OWNERSHIP_ENTRY_UNIQUE_SUBJECT_CIKS,
            "unambiguous_common_stock_mappings": BENEFICIAL_OWNERSHIP_ENTRY_UNAMBIGUOUS_MAPPINGS,
        }
        for key, expected in numeric.items():
            if int(report.get(key, -1)) != expected:
                raise BeneficialOwnershipPredictorError(
                    f"accepted beneficial-ownership source report {key} mismatch"
                )
        if int(report.get("target_outcome_rows_read", -1)) != 0:
            raise BeneficialOwnershipPredictorError("source evidence was not outcome-blind")
        if int(report.get("protected_return_rows_read", -1)) != 0:
            raise BeneficialOwnershipPredictorError("source evidence consumed protected returns")
        if report.get("protected_holdout_consumed") is not False:
            raise BeneficialOwnershipPredictorError("source evidence consumed the protected holdout")
        return report

    def build(self) -> dict[str, Any]:
        if beneficial_ownership_scientific_fingerprint() != BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT:
            raise BeneficialOwnershipPredictorError("frozen scientific fingerprint drifted")
        source_report = self._accepted_source_report()

        discovery: list[BeneficialOwnershipIndexRow] = []
        for year, quarter in BENEFICIAL_OWNERSHIP_QUARTERS:
            document = self.source._cached_index(year, quarter)
            discovery.extend(parse_master_index(document.text))
        discovered, duplicate_associations = dedupe_discovery_v2(discovery)
        sample = select_source_sample(discovered)

        expected_sample = 2 * (
            BENEFICIAL_OWNERSHIP_DEVELOPMENT_SAMPLE_PER_FORM_FAMILY
            + BENEFICIAL_OWNERSHIP_PROTECTED_SAMPLE_PER_FORM_FAMILY
        )
        if len(sample) != expected_sample:
            raise BeneficialOwnershipPredictorError(
                f"source-only scientific sample is incomplete: {len(sample)} != {expected_sample}"
            )

        output: list[dict[str, Any]] = []
        diagnostics: Counter[str] = Counter()
        source_sample_counts = Counter(
            f"{_source_stage(_as_date(row.filing_date))}:{row.form_class}" for row in sample
        )
        candidate_direction = {spec.candidate_id: spec.direction for spec in BENEFICIAL_OWNERSHIP_HYPOTHESES}

        for index, row in enumerate(sample, start=1):
            selected_stage = _source_stage(_as_date(row.filing_date))
            try:
                document = self.source._cached_submission(row)
                metadata = parse_submission_metadata(document.text)
                if metadata.accession_number != row.accession_number:
                    diagnostics["accession_mismatch"] += 1
                    continue
                if metadata.form != row.form:
                    diagnostics["form_mismatch"] += 1
                    continue
                if metadata.filing_date != row.filing_date:
                    diagnostics["filing_date_mismatch"] += 1
                    continue
                subject_cik = authoritative_subject_cik(metadata)
                if subject_cik is None or metadata.acceptance_datetime is None:
                    diagnostics["chronology_or_subject_missing"] += 1
                    continue
                decision = _decision_session(metadata.acceptance_datetime)
                stage = _decision_stage(decision)
                if stage is None or stage != selected_stage:
                    diagnostics["decision_stage_boundary_censored"] += 1
                    continue
                percentages = extract_percent_of_class_values(document.text)
                percent = max(percentages) if percentages else None
                if percent is None:
                    diagnostics["percent_unparsed"] += 1
                    continue
                candidate_id = candidate_for(form_family=row.form_class, percent_of_class=percent)
                if candidate_id is None:
                    diagnostics["outside_frozen_percent_bins"] += 1
                    continue

                reference_rows = self.source._cached_reference(cik=subject_cik, as_of_date=decision)
                identity = _resolve_identity(
                    reference_rows, subject_cik=subject_cik, as_of_date=decision
                )
                if identity.get("status") != "UNAMBIGUOUS_PIT_INSTRUMENT":
                    diagnostics[str(identity.get("status") or "IDENTITY_UNKNOWN")] += 1
                    continue
                instruments = identity.get("instruments")
                if not isinstance(instruments, list) or len(instruments) != 1:
                    diagnostics["identity_cardinality_drift"] += 1
                    continue
                instrument = dict(instruments[0])
                ticker = str(instrument.get("ticker") or "").strip()
                instrument_id = str(instrument.get("instrument_id") or "").strip()
                if not ticker or not instrument_id:
                    diagnostics["identity_missing_ticker_or_id"] += 1
                    continue

                output.append(
                    {
                        "contract_version": BENEFICIAL_OWNERSHIP_PREDICTOR_CONTRACT,
                        "scientific_fingerprint": BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT,
                        "source_repair_fingerprint": BENEFICIAL_OWNERSHIP_ENTRY_SOURCE_REPAIR_FINGERPRINT,
                        "accession_number": row.accession_number,
                        "form": row.form,
                        "form_family": row.form_class,
                        "source_era": row.era,
                        "filing_date": row.filing_date,
                        "acceptance_datetime": metadata.acceptance_datetime,
                        "decision_session": decision.isoformat(),
                        "stage": stage,
                        "index_cik": row.index_cik,
                        "subject_cik": subject_cik,
                        "subject_name": metadata.subject_name,
                        "reported_percent_values": list(percentages),
                        "reported_percent_of_class": float(percent),
                        "candidate_id": candidate_id,
                        "direction": candidate_direction[candidate_id],
                        "instrument_id": instrument_id,
                        "ticker": ticker,
                        "identity_quality": instrument.get("identity_quality"),
                        "primary_exchange": instrument.get("primary_exchange"),
                        "security_type": instrument.get("security_type"),
                        "composite_figi": instrument.get("composite_figi"),
                        "share_class_figi": instrument.get("share_class_figi"),
                    }
                )
            except (BeneficialOwnershipFeasibilityError, OSError, ValueError, TypeError) as exc:
                diagnostics[f"row_error:{type(exc).__name__}"] += 1

            if index == 1 or index % 100 == 0 or index == len(sample):
                self._progress(
                    f"Beneficial-ownership predictor progress: {index}/{len(sample)} "
                    f"signals={len(output)} source_reads={sum(self.source.source_reads.values())}"
                )

        output.sort(
            key=lambda item: (
                str(item["stage"]),
                str(item["decision_session"]),
                str(item["candidate_id"]),
                str(item["instrument_id"]),
                str(item["accession_number"]),
            )
        )
        rows_text = "".join(_canonical_json(row) + "\n" for row in output)
        rows_path = self.derived_root / BENEFICIAL_OWNERSHIP_PREDICTOR_ROWS_RELATIVE
        report_path = self.derived_root / BENEFICIAL_OWNERSHIP_PREDICTOR_REPORT_RELATIVE
        rows_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(rows_path, rows_text)

        stage_counts = Counter(str(row["stage"]) for row in output)
        candidate_counts = Counter(str(row["candidate_id"]) for row in output)
        report = {
            "contract_version": BENEFICIAL_OWNERSHIP_PREDICTOR_CONTRACT,
            "scientific_contract": BENEFICIAL_OWNERSHIP_SCIENTIFIC_CONTRACT,
            "scientific_fingerprint": BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT,
            "source_repair_contract": BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_CONTRACT,
            "source_repair_fingerprint": BENEFICIAL_OWNERSHIP_ENTRY_SOURCE_REPAIR_FINGERPRINT,
            "source_repair_status": source_report.get("status"),
            "source_discovered_rows": len(discovered),
            "duplicate_accession_associations_collapsed": duplicate_associations,
            "source_sample_rows": len(sample),
            "source_sample_counts": dict(sorted(source_sample_counts.items())),
            "predictor_rows": len(output),
            "stage_counts": dict(sorted(stage_counts.items())),
            "candidate_counts": dict(sorted(candidate_counts.items())),
            "diagnostics": dict(sorted(diagnostics.items())),
            "provider_source_reads": int(sum(self.source.source_reads.values())),
            "provider_read_breakdown": dict(sorted(self.source.source_reads.items())),
            "cache_hits": dict(sorted(self.source.cache_hits.items())),
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "orders": 0,
            "paper": 0,
            "live": 0,
            "automation": 0,
            "predictor_rows_sha256": sha256_file(rows_path),
            "pass": bool(output),
        }
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["predictor_rows_path"] = str(rows_path)
        report["report_path"] = str(report_path)
        return report
