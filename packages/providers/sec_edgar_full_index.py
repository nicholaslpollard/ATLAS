from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import PurePosixPath
from typing import Iterable

from packages.core.exceptions import ProviderError


SEC_MASTER_INDEX_HEADER = "CIK|Company Name|Form Type|Date Filed|Filename"
SEC_MASTER_INDEX_MAX_ROWS = 2_000_000


@dataclass(frozen=True, slots=True)
class SECQuarterMasterIndexRow:
    cik: str
    company_name: str
    form_type: str
    filing_date: date
    filename: str


def normalize_sec_cik(value: object) -> str:
    text = str(value or "").strip()
    if not text or not text.isdigit():
        raise ProviderError(f"SEC master-index CIK is invalid: {value!r}")
    if len(text) > 10:
        raise ProviderError(f"SEC master-index CIK exceeds ten digits: {value!r}")
    return text.zfill(10)


def _validate_archive_filename(value: object) -> str:
    text = str(value or "").strip().lstrip("/")
    parts = PurePosixPath(text).parts
    if len(parts) != 4 or tuple(parts[:2]) != ("edgar", "data"):
        raise ProviderError(f"SEC master-index filename is outside edgar/data: {value!r}")
    if not parts[2].isdigit():
        raise ProviderError(f"SEC master-index filename CIK directory is invalid: {value!r}")
    basename = parts[3]
    import re

    if not re.fullmatch(r"\d{10}-\d{2}-\d{6}\.txt", basename):
        raise ProviderError(f"SEC master-index filename accession is invalid: {value!r}")
    return "/".join(parts)


def parse_sec_quarter_master_index(text: str) -> tuple[SECQuarterMasterIndexRow, ...]:
    lines = text.splitlines()
    header_index = next(
        (index for index, line in enumerate(lines) if line.strip() == SEC_MASTER_INDEX_HEADER),
        None,
    )
    if header_index is None:
        raise ProviderError("SEC master-index column header was not found")

    rows: list[SECQuarterMasterIndexRow] = []
    for raw in lines[header_index + 1 :]:
        line = raw.strip()
        if not line or set(line) <= {"-"}:
            continue
        parts = line.split("|")
        if len(parts) != 5:
            raise ProviderError(f"SEC master-index row does not have five columns: {line[:200]!r}")
        cik_raw, company_raw, form_raw, filed_raw, filename_raw = parts
        company = company_raw.strip()
        form_type = form_raw.strip()
        if not company or not form_type:
            raise ProviderError("SEC master-index row has blank company/form")
        try:
            filed = date.fromisoformat(filed_raw.strip())
        except ValueError as exc:
            raise ProviderError(
                f"SEC master-index filing date is not YYYY-MM-DD: {filed_raw!r}"
            ) from exc
        rows.append(
            SECQuarterMasterIndexRow(
                cik=normalize_sec_cik(cik_raw),
                company_name=company,
                form_type=form_type,
                filing_date=filed,
                filename=_validate_archive_filename(filename_raw),
            )
        )
        if len(rows) > SEC_MASTER_INDEX_MAX_ROWS:
            raise ProviderError(
                f"SEC master-index exceeded bounded parsed row count: {SEC_MASTER_INDEX_MAX_ROWS}"
            )
    if not rows:
        raise ProviderError("SEC master-index contained no filing rows")
    return tuple(rows)


def filter_sec_master_index_rows(
    rows: Iterable[SECQuarterMasterIndexRow],
    *,
    ciks: set[str],
    forms: set[str],
    start_date: date,
    end_date: date,
) -> tuple[SECQuarterMasterIndexRow, ...]:
    if start_date > end_date:
        raise ValueError("start_date must be <= end_date")
    normalized_ciks = {normalize_sec_cik(value) for value in ciks}
    if not normalized_ciks:
        raise ValueError("ciks cannot be empty")
    normalized_forms = {str(value).strip() for value in forms if str(value).strip()}
    if not normalized_forms:
        raise ValueError("forms cannot be empty")

    selected = [
        row
        for row in rows
        if row.cik in normalized_ciks
        and row.form_type in normalized_forms
        and start_date <= row.filing_date <= end_date
    ]
    selected.sort(
        key=lambda row: (
            row.filing_date,
            row.form_type,
            row.cik,
            row.filename,
            row.company_name,
        )
    )
    return tuple(selected)
