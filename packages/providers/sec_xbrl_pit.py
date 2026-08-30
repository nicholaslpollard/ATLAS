from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

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
    """Read-only original 10-Q/10-K metadata lookup for XBRL PIT reconstruction."""

    @staticmethod
    def _validated_forms(allowed_forms: tuple[str, ...]) -> tuple[str, ...]:
        if not allowed_forms or any(form not in XBRL_PIT_ALLOWED_FORMS for form in allowed_forms):
            raise ProviderError(
                "SEC XBRL PIT metadata allowed original forms exceeded exact 10-Q/10-K scope"
            )
        return allowed_forms

    def filing_metadata_many(
        self,
        *,
        cik: object,
        requests: Iterable[Mapping[str, object]],
        allowed_forms: tuple[str, ...] = XBRL_PIT_ALLOWED_FORMS,
    ) -> tuple[SECOriginalFilingMetadata, ...]:
        """Resolve many exact accessions with one root submissions read per issuer."""
        allowed = self._validated_forms(allowed_forms)
        issuer_cik = _normalize_cik(cik)
        normalized: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for request in requests:
            accession = _validate_accession(str(request.get("accession_number") or ""))
            filing_date = _validate_filing_date(
                request.get("filing_date"), field="requested filing date"
            )
            expected_form = str(request.get("form") or "").strip()
            if expected_form not in allowed:
                raise ProviderError(
                    f"SEC XBRL PIT requested accession {accession} has disallowed form {expected_form!r}"
                )
            if accession in seen:
                raise ProviderError(f"SEC XBRL PIT batch contains duplicate accession {accession}")
            seen.add(accession)
            normalized.append((accession, filing_date, expected_form))
        if not normalized:
            return ()

        root_url = sec_company_submissions_url(cik=issuer_cik)
        root, _ = self.get_json(root_url)
        filings = root.get("filings")
        if not isinstance(filings, dict):
            raise ProviderError("SEC company submissions response is missing filings object")

        resolved: dict[str, SECOriginalFilingMetadata] = {}
        unresolved: list[tuple[str, str, str, tuple[str, ...]]] = []
        for accession, filing_date, expected_form in normalized:
            row = _find_accession(filings.get("recent"), accession)
            if row is not None:
                record = _record_from_row(
                    row=row,
                    issuer_cik=issuer_cik,
                    expected_accession=accession,
                    expected_filing_date=filing_date,
                    allowed_forms=allowed,
                    source_url=root_url,
                )
                if record.form != expected_form:
                    raise ProviderError(
                        f"SEC submissions accession {accession} form mismatch: {record.form!r} != {expected_form!r}"
                    )
                resolved[accession] = record
                continue
            candidates = _select_declared_shard_candidates(
                filings.get("files"), filing_date=filing_date
            )
            if not candidates:
                raise ProviderError(
                    "SEC submissions metadata does not cover requested XBRL accession/date within "
                    f"the bounded declared-shard rollover rule: {accession} / {filing_date}"
                )
            unresolved.append(
                (
                    accession,
                    filing_date,
                    expected_form,
                    tuple(sec_submission_shard_url(item.get("name")) for item in candidates),
                )
            )

        shard_documents: dict[str, dict[str, Any]] = {}
        for _, _, _, shard_urls in unresolved:
            for shard_url in shard_urls:
                if shard_url not in shard_documents:
                    shard, _ = self.get_json(shard_url)
                    shard_documents[shard_url] = shard

        for accession, filing_date, expected_form, shard_urls in unresolved:
            record: SECOriginalFilingMetadata | None = None
            for shard_url in shard_urls:
                shard = shard_documents[shard_url]
                row = _find_accession(shard, accession)
                if row is None and isinstance(shard.get("filings"), dict):
                    row = _find_accession(shard["filings"].get("recent"), accession)
                if row is None:
                    continue
                record = _record_from_row(
                    row=row,
                    issuer_cik=issuer_cik,
                    expected_accession=accession,
                    expected_filing_date=filing_date,
                    allowed_forms=allowed,
                    source_url=shard_url,
                )
                if record.form != expected_form:
                    raise ProviderError(
                        f"SEC submissions accession {accession} form mismatch: {record.form!r} != {expected_form!r}"
                    )
                break
            if record is None:
                raise ProviderError(
                    f"SEC submissions metadata did not contain requested XBRL accession {accession}"
                )
            resolved[accession] = record
        return tuple(resolved[accession] for accession, _, _ in normalized)

    def filing_metadata(
        self,
        *,
        cik: object,
        accession_number: str,
        filing_date: str,
        allowed_forms: tuple[str, ...] = XBRL_PIT_ALLOWED_FORMS,
    ) -> SECOriginalFilingMetadata:
        allowed = self._validated_forms(allowed_forms)
        if len(allowed) == 1:
            return self.filing_metadata_many(
                cik=cik,
                requests=(
                    {
                        "accession_number": accession_number,
                        "filing_date": filing_date,
                        "form": allowed[0],
                    },
                ),
                allowed_forms=allowed,
            )[0]

        issuer_cik = _normalize_cik(cik)
        expected_accession = _validate_accession(accession_number)
        expected_filing_date = _validate_filing_date(
            filing_date, field="requested filing date"
        )
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
                allowed_forms=allowed,
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
                    allowed_forms=allowed,
                    source_url=shard_url,
                )
        raise ProviderError(
            f"SEC submissions metadata did not contain requested XBRL accession {expected_accession}"
        )
