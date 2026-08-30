from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from packages.core.exceptions import ProviderError
from packages.providers.sec_edgar import (
    SECEDGARClient,
    _canonical_json,
    _find_accession,
    _normalize_cik,
    _parse_acceptance,
    _select_declared_shard_candidates,
    _validate_accession,
    _validate_filing_date,
    sec_company_submissions_url,
    sec_submission_shard_url,
)


XBRL_PIT_ALLOWED_FORMS = ("10-Q", "10-K")


@dataclass(frozen=True, slots=True)
class SECOriginalFilingMetadata:
    accession_number: str
    issuer_cik: str
    filing_date: str
    acceptance_datetime: str
    form: str
    primary_document: str | None
    source_url: str
    source_record_json: str
    source_record_sha256: str


def _record_from_row(
    *,
    row: dict[str, object],
    issuer_cik: str,
    expected_accession: str,
    expected_filing_date: str,
    allowed_forms: tuple[str, ...],
    source_url: str,
) -> SECOriginalFilingMetadata:
    accession = _validate_accession(str(row.get("accessionNumber") or ""))
    if accession != expected_accession:
        raise ProviderError("SEC submissions accession does not match requested accession")
    form = str(row.get("form") or "").strip()
    if form not in allowed_forms:
        raise ProviderError(
            f"SEC submissions accession {accession} is outside allowed original forms: form={form!r}"
        )
    filing_date = _validate_filing_date(row.get("filingDate"))
    if filing_date != expected_filing_date:
        raise ProviderError(
            f"SEC submissions accession {accession} filingDate does not match requested date: "
            f"{filing_date} != {expected_filing_date}"
        )
    acceptance_datetime = _parse_acceptance(row.get("acceptanceDateTime"))
    primary_document = str(row.get("primaryDocument") or "").strip() or None
    source_record = {
        "accessionNumber": accession,
        "issuerCIK": issuer_cik,
        "filingDate": filing_date,
        "acceptanceDateTime": str(row.get("acceptanceDateTime") or "").strip(),
        "form": form,
        "primaryDocument": primary_document,
        "sourceUrl": source_url,
    }
    source_record_json = _canonical_json(source_record)
    return SECOriginalFilingMetadata(
        accession_number=accession,
        issuer_cik=issuer_cik,
        filing_date=filing_date,
        acceptance_datetime=acceptance_datetime,
        form=form,
        primary_document=primary_document,
        source_url=source_url,
        source_record_json=source_record_json,
        source_record_sha256=hashlib.sha256(source_record_json.encode("utf-8")).hexdigest(),
    )


class SECXBRLPITMetadataClient(SECEDGARClient):
    """Read-only original 10-Q/10-K metadata lookup for XBRL PIT reconstruction.

    This class deliberately inherits the accepted SEC EDGAR HTTP/fair-access seam.
    It broadens only the form validator from Phase32's exact 8-K helper to the
    explicitly allowed original 10-Q/10-K forms needed by the XBRL source audit.
    Amendment forms remain excluded.
    """

    def filing_metadata(
        self,
        *,
        cik: object,
        accession_number: str,
        filing_date: str,
        allowed_forms: tuple[str, ...] = XBRL_PIT_ALLOWED_FORMS,
    ) -> SECOriginalFilingMetadata:
        if not allowed_forms or any(form not in XBRL_PIT_ALLOWED_FORMS for form in allowed_forms):
            raise ProviderError("SEC XBRL PIT metadata allowed_forms exceeded original 10-Q/10-K scope")
        issuer_cik = _normalize_cik(cik)
        expected_accession = _validate_accession(accession_number)
        expected_filing_date = _validate_filing_date(filing_date, field="requested filing date")
        root_url = sec_company_submissions_url(cik=issuer_cik)
        root, _ = self.get_json(root_url)
        filings = root.get("filings")
        if not isinstance(filings, dict):
            raise ProviderError("SEC company submissions response is missing filings object")

        row = _find_accession(filings.get("recent"), expected_accession)
        if row is not None:
            return _record_from_row(
                row=row,
                issuer_cik=issuer_cik,
                expected_accession=expected_accession,
                expected_filing_date=expected_filing_date,
                allowed_forms=allowed_forms,
                source_url=root_url,
            )

        candidates = _select_declared_shard_candidates(
            filings.get("files"), filing_date=expected_filing_date
        )
        if not candidates:
            raise ProviderError(
                "SEC submissions metadata does not cover requested XBRL accession/date within "
                f"the bounded declared-shard rollover rule: {expected_accession} / {expected_filing_date}"
            )
        for item in candidates:
            shard_url = sec_submission_shard_url(item.get("name"))
            shard, _ = self.get_json(shard_url)
            row = _find_accession(shard, expected_accession)
            if row is None and isinstance(shard.get("filings"), dict):
                row = _find_accession(shard["filings"].get("recent"), expected_accession)
            if row is not None:
                return _record_from_row(
                    row=row,
                    issuer_cik=issuer_cik,
                    expected_accession=expected_accession,
                    expected_filing_date=expected_filing_date,
                    allowed_forms=allowed_forms,
                    source_url=shard_url,
                )
        raise ProviderError(
            f"SEC submissions metadata did not contain requested XBRL accession {expected_accession}"
        )
