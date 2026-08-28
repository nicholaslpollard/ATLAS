from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable

from .phase31_source_quality import (
    PHASE31_QUARANTINE_REASON,
    Phase31SourceQualityError,
    classify_form4_source_quality,
)


PHASE31_HISTORICAL_SOURCE_QUALITY_CONTRACT_VERSION = (
    "phase31-form4-historical-source-quality-v1-chronology-required-code-global-accession-quarantine"
)
PHASE31_HISTORICAL_QUARANTINE_REASON = "SOURCE_ACCESSION_FAILS_HISTORICAL_ADMISSIBILITY"
PHASE31_MISSING_TRANSACTION_CODE_REASON = "SOURCE_TRANSACTION_ROW_MISSING_TRANSACTION_CODE"


@dataclass(frozen=True, slots=True)
class Phase31HistoricalSourceQualityClassification:
    authoritative_rows: tuple[dict[str, Any], ...]
    quarantined_rows: tuple[dict[str, Any], ...]
    chronology_seed_rows: tuple[dict[str, Any], ...]
    missing_transaction_code_seed_rows: tuple[dict[str, Any], ...]
    contaminated_accessions: tuple[str, ...]
    accession_reasons: tuple[tuple[str, tuple[str, ...]], ...]


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sort_key(row: dict[str, Any]) -> tuple[object, ...]:
    return (
        str(row.get("filing_date") or ""),
        str(row.get("accession_number") or ""),
        str(row.get("owner_cik") or ""),
        str(row.get("record_type") or ""),
        str(row.get("transaction_date") or ""),
        str(row.get("transaction_code") or ""),
        str(row.get("security_title") or ""),
        _canonical_json(row),
    )


def _transaction_code_missing(row: dict[str, Any]) -> bool:
    if row.get("record_type") != "transaction":
        return False
    code = row.get("transaction_code")
    return not isinstance(code, str) or not code.strip()


def required_transaction_code_violation_count(rows: Iterable[dict[str, Any]]) -> int:
    return sum(1 for row in rows if _transaction_code_missing(row))


def classify_form4_historical_source_quality(
    rows: Iterable[dict[str, Any]],
) -> Phase31HistoricalSourceQualityClassification:
    """Apply generic, outcome-free historical Form-4 source admissibility.

    The accepted target-window chronology repair remains a separate frozen artifact.
    For the larger historical corpus, an accession is quarantined globally if either:
    1) any transaction has impossible transaction_date > filing_date chronology, or
    2) any transaction lacks the transaction_code required to classify P/S hypotheses.
    The entire accession is then excluded from authoritative historical construction.

    Raw provider rows are copied without correction, imputation, ticker normalization,
    accession-specific exceptions, or performance-dependent decisions.
    """
    materialized = tuple(dict(row) for row in rows)
    chronology = classify_form4_source_quality(materialized)

    contaminated = set(chronology.contaminated_accessions)
    reasons: dict[str, set[str]] = {
        accession: {PHASE31_QUARANTINE_REASON}
        for accession in chronology.contaminated_accessions
    }
    missing_code_rows: list[dict[str, Any]] = []

    for row in materialized:
        if not _transaction_code_missing(row):
            continue
        accession = row.get("accession_number")
        if not isinstance(accession, str) or not accession.strip():
            raise Phase31SourceQualityError(
                "transaction-code-defective Form-4 row is missing accession_number; "
                "cannot quarantine safely"
            )
        contaminated.add(accession)
        reasons.setdefault(accession, set()).add(PHASE31_MISSING_TRANSACTION_CODE_REASON)
        missing_code_rows.append(row)

    authoritative: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for row in materialized:
        accession = row.get("accession_number")
        if isinstance(accession, str) and accession in contaminated:
            quarantined.append(row)
        else:
            authoritative.append(row)

    return Phase31HistoricalSourceQualityClassification(
        authoritative_rows=tuple(sorted(authoritative, key=_sort_key)),
        quarantined_rows=tuple(sorted(quarantined, key=_sort_key)),
        chronology_seed_rows=tuple(sorted(chronology.violating_seed_rows, key=_sort_key)),
        missing_transaction_code_seed_rows=tuple(sorted(missing_code_rows, key=_sort_key)),
        contaminated_accessions=tuple(sorted(contaminated)),
        accession_reasons=tuple(
            (accession, tuple(sorted(values)))
            for accession, values in sorted(reasons.items())
        ),
    )
