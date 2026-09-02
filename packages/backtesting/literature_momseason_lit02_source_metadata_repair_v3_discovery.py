from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Mapping

from packages.core.atomic_io import atomic_write_text
from packages.providers.sec_edgar_archive import sec_quarter_master_index_url
from packages.providers.sec_edgar_full_index import (
    SECQuarterMasterIndexRow,
    filter_sec_master_index_rows,
    normalize_sec_cik,
    parse_sec_quarter_master_index,
)

from .literature_momseason_lit02_source_metadata import _fingerprint, _normalize_cik
from .literature_momseason_lit02_source_metadata_repair_v2 import (
    _report_fingerprint as _unused_v2_report_fingerprint,
    _select_latest_ready,
)
from .literature_momseason_lit02_source_metadata_repair_v2_certified import (
    parse_explicit_sec_ticker_change_v2_certified,
)
from .literature_momseason_lit02_source_metadata_repair_v3 import (
    LIT02_REPAIR_V3_SEC_ALLOWED_FORMS,
    LIT02_REPAIR_V3_SEC_FORWARD_DAYS,
    LIT02_REPAIR_V3_SEC_LOOKBACK_DAYS,
    LIT02_REPAIR_V3_SEC_MAX_CANDIDATE_FILINGS,
    _report_fingerprint_v3,
    lit02_repair_v3_source_expansion_fingerprint,
)
from .literature_momseason_lit02_source_metadata_repair_v3_certified import (
    LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION,
    parse_sec_final_transaction_amendment_v3_certified,
)
from .literature_momseason_lit02_source_metadata_repair_v3_freeze import (
    LIT02_SOURCE_METADATA_REPAIR_V3_FREEZE_CONTRACT,
    MomSeasonLIT02SourceMetadataRepairV3Frozen,
    _contains_contingent_consideration,
    lit02_repair_v3_freeze_fingerprint,
    lit02_repair_v3_freeze_payload,
)
from .literature_momseason_source import canonical_json


LIT02_REPAIR_V3_DISCOVERY_CONTRACT = (
    "lit02-repair-v3-official-quarterly-master-index-subject-cik-discovery-v1"
)
LIT02_REPAIR_V3_DISCOVERY_FREEZE_CONTRACT = (
    "lit02-repair-v3-source-parser-subject-index-freeze-v2-pre-provider-read"
)
LIT02_REPAIR_V3_MAX_QUARTERS = 32

_SUBJECT_BLOCK = re.compile(
    r"(?is)(?:^|\n)\s*SUBJECT\s+COMPANY:\s*(?P<body>.*?)(?="
    r"(?:\n\s*(?:FILED\s+BY|REPORTING[- ]OWNER|ISSUER|SUBJECT\s+COMPANY):)|"
    r"</SEC-HEADER>|\Z)"
)
_SUBJECT_SGML_BLOCK = re.compile(
    r"(?is)<SUBJECT-COMPANY>(?P<body>.*?)(?=</SUBJECT-COMPANY>|<FILED-BY>|</SEC-HEADER>|\Z)"
)
_CIK_COLON = re.compile(r"(?im)^\s*CENTRAL\s+INDEX\s+KEY:\s*(?P<cik>\d{1,10})\s*$")
_CIK_SGML = re.compile(r"(?is)<CIK>\s*(?P<cik>\d{1,10})")


def extract_sec_subject_ciks(text: str) -> tuple[str, ...]:
    header_end = text.find("</SEC-HEADER>")
    header = text[: header_end + len("</SEC-HEADER>")] if header_end >= 0 else text[:250_000]
    values: set[str] = set()
    for pattern in (_SUBJECT_BLOCK, _SUBJECT_SGML_BLOCK):
        for match in pattern.finditer(header):
            body = match.group("body")
            for cik_pattern in (_CIK_COLON, _CIK_SGML):
                for cik_match in cik_pattern.finditer(body):
                    values.add(normalize_sec_cik(cik_match.group("cik")))
    return tuple(sorted(values))


def _quarter(value: date) -> tuple[int, int]:
    return value.year, ((value.month - 1) // 3) + 1


def quarters_covering(start_date: date, end_date: date) -> tuple[tuple[int, int], ...]:
    if start_date > end_date:
        raise ValueError("start_date must be <= end_date")
    year, quarter = _quarter(start_date)
    end_year, end_quarter = _quarter(end_date)
    values: list[tuple[int, int]] = []
    while (year, quarter) <= (end_year, end_quarter):
        values.append((year, quarter))
        if len(values) > LIT02_REPAIR_V3_MAX_QUARTERS:
            raise RuntimeError("LIT-02 repair-v3 quarterly SEC discovery exceeded frozen quarter bound")
        quarter += 1
        if quarter == 5:
            year += 1
            quarter = 1
    return tuple(values)


def lit02_repair_v3_discovery_freeze_payload() -> dict[str, object]:
    return {
        "freeze_contract": LIT02_REPAIR_V3_DISCOVERY_FREEZE_CONTRACT,
        "discovery_contract": LIT02_REPAIR_V3_DISCOVERY_CONTRACT,
        "prior_source_parser_freeze_contract": LIT02_SOURCE_METADATA_REPAIR_V3_FREEZE_CONTRACT,
        "prior_source_parser_freeze_fingerprint": lit02_repair_v3_freeze_fingerprint(),
        "prior_source_parser_freeze": lit02_repair_v3_freeze_payload(),
        "source_expansion_fingerprint": lit02_repair_v3_source_expansion_fingerprint(),
        "official_discovery_source": "SEC quarterly master.idx via /Archives/edgar/full-index",
        "discovery_index_fields": ["CIK", "Company Name", "Form Type", "Date Filed", "Filename"],
        "discovery_forms": sorted(LIT02_REPAIR_V3_SEC_ALLOWED_FORMS),
        "discovery_rule": (
            "for each repair-v2 unresolved target CIK and frozen endpoint, select only official SEC "
            "quarterly master-index rows whose index CIK equals the normalized target CIK, form is "
            "one of the two frozen repair-v3 forms, and filing date is within the frozen 370-day "
            "lookback / 10-day forward metadata window"
        ),
        "archive_path_rule": (
            "fetch the complete-submission filename exactly as supplied by the official SEC master "
            "index; never derive an archive CIK/path from the accession prefix or filer CIK"
        ),
        "subject_verification_rule": (
            "before parsing transaction facts, the complete submission SEC header must contain the "
            "normalized target CIK inside a SUBJECT COMPANY block; missing or mismatched subject "
            "identity fails closed"
        ),
        "max_quarters": LIT02_REPAIR_V3_MAX_QUARTERS,
        "max_case_candidate_filings": LIT02_REPAIR_V3_SEC_MAX_CANDIDATE_FILINGS,
        "economic_paths_changed": False,
        "required_source_coverage": 1.0,
        "economic_outcome_values_allowed": False,
        "new_price_or_return_reads_allowed": False,
        "protected_reads_allowed": False,
        "ticker_specific_exceptions_allowed": False,
        "phase33_authority": False,
    }


def lit02_repair_v3_discovery_freeze_fingerprint() -> str:
    return _fingerprint(lit02_repair_v3_discovery_freeze_payload())


class MomSeasonLIT02SourceMetadataRepairV3SubjectIndexed(
    MomSeasonLIT02SourceMetadataRepairV3Frozen
):
    """Repair-v3 using official SEC quarterly subject-company archive discovery."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._v3_quarter_index_cache: dict[tuple[int, int], tuple[SECQuarterMasterIndexRow, ...]] = {}
        self._v3_quarter_index_sha: dict[tuple[int, int], str] = {}

    def _quarter_rows(self, year: int, quarter: int) -> tuple[SECQuarterMasterIndexRow, ...]:
        key = (year, quarter)
        cached = self._v3_quarter_index_cache.get(key)
        if cached is not None:
            return cached
        _submissions, archive = self._ensure_sec_clients()
        self._sec_reads += 1
        document = archive.quarter_master_index(year=year, quarter=quarter)
        rows = parse_sec_quarter_master_index(document.text)
        self._v3_quarter_index_cache[key] = rows
        self._v3_quarter_index_sha[key] = document.source_sha256
        return rows

    def _sec_candidate_filings_v3_indexed(
        self,
        *,
        cik: str,
        endpoint_session: date,
    ) -> list[dict[str, object]]:
        target_cik = normalize_sec_cik(cik)
        start_date = endpoint_session - timedelta(days=LIT02_REPAIR_V3_SEC_LOOKBACK_DAYS)
        end_date = endpoint_session + timedelta(days=LIT02_REPAIR_V3_SEC_FORWARD_DAYS)
        selected: dict[str, dict[str, object]] = {}
        for year, quarter in quarters_covering(start_date, end_date):
            rows = filter_sec_master_index_rows(
                self._quarter_rows(year, quarter),
                ciks={target_cik},
                forms=set(LIT02_REPAIR_V3_SEC_ALLOWED_FORMS),
                start_date=start_date,
                end_date=end_date,
            )
            index_url = sec_quarter_master_index_url(year=year, quarter=quarter)
            index_sha = self._v3_quarter_index_sha[(year, quarter)]
            for row in rows:
                accession = Path(row.filename).name.removesuffix(".txt")
                selected[accession] = {
                    "accession_number": accession,
                    "filing_date": row.filing_date.isoformat(),
                    "form": row.form_type,
                    "items": [],
                    "primary_document": None,
                    "official_archive_filename": row.filename,
                    "master_index_cik": row.cik,
                    "master_index_company_name": row.company_name,
                    "master_index_source_url": index_url,
                    "master_index_source_sha256": index_sha,
                }
        ordered = sorted(
            selected.values(),
            key=lambda item: (str(item["filing_date"]), str(item["accession_number"])),
        )
        if len(ordered) > LIT02_REPAIR_V3_SEC_MAX_CANDIDATE_FILINGS:
            raise RuntimeError(
                "LIT-02 repair-v3 official master-index discovery exceeded bounded candidate count: "
                f"{len(ordered)} > {LIT02_REPAIR_V3_SEC_MAX_CANDIDATE_FILINGS}"
            )
        return ordered

    def _sec_resolution_v3(
        self,
        *,
        identity: Mapping[str, object],
        endpoint_session: date,
        historical_ticker: str,
    ) -> tuple[dict[str, object] | None, list[dict[str, object]], list[str]]:
        cik = str(identity.get("cik") or "").strip()
        if not cik:
            return None, [], ["CIK_UNAVAILABLE_FOR_SEC_FINAL_TRANSACTION_SOURCE"]
        target_cik = normalize_sec_cik(cik)
        try:
            filings = self._sec_candidate_filings_v3_indexed(
                cik=target_cik,
                endpoint_session=endpoint_session,
            )
        except RuntimeError as exc:
            return None, [], [str(exc)]

        evidence_rows: list[dict[str, object]] = []
        ready_candidates: list[dict[str, object]] = []
        incomplete_reasons: list[str] = []
        for filing in filings:
            filename = str(filing["official_archive_filename"])
            document = self._sec_get_submission(filename)
            subject_ciks = extract_sec_subject_ciks(document.text)
            if target_cik not in subject_ciks:
                evidence_rows.append(
                    {
                        **filing,
                        "submission_source_url": document.source_url,
                        "submission_source_sha256": document.source_sha256,
                        "subject_ciks": list(subject_ciks),
                        "subject_identity_verified": False,
                        "discovery_contract": LIT02_REPAIR_V3_DISCOVERY_CONTRACT,
                        "discovery_freeze_fingerprint": (
                            lit02_repair_v3_discovery_freeze_fingerprint()
                        ),
                        "ticker_change_candidate": None,
                        "terminal_candidate": None,
                    }
                )
                incomplete_reasons.append(
                    "SEC_FINAL_TRANSACTION_SUBJECT_CIK_MISSING_OR_MISMATCHED_V3"
                )
                continue

            ticker_candidate = parse_explicit_sec_ticker_change_v2_certified(
                document.text,
                endpoint_session=endpoint_session,
                historical_ticker=historical_ticker,
            )
            terminal_candidate = parse_sec_final_transaction_amendment_v3_certified(
                document.text,
                form=str(filing["form"]),
                endpoint_session=endpoint_session,
                historical_ticker=historical_ticker,
            )
            evidence_rows.append(
                {
                    **filing,
                    "submission_source_url": document.source_url,
                    "submission_source_sha256": document.source_sha256,
                    "subject_ciks": list(subject_ciks),
                    "subject_identity_verified": True,
                    "discovery_contract": LIT02_REPAIR_V3_DISCOVERY_CONTRACT,
                    "discovery_freeze_fingerprint": (
                        lit02_repair_v3_discovery_freeze_fingerprint()
                    ),
                    "ticker_change_candidate": ticker_candidate,
                    "terminal_candidate": terminal_candidate,
                }
            )
            for candidate in (ticker_candidate, terminal_candidate):
                if not isinstance(candidate, Mapping):
                    continue
                status = str(candidate.get("status") or "")
                if status == "READY":
                    ready_candidates.append(
                        {
                            **dict(candidate),
                            "source_url": document.source_url,
                            "source_sha256": document.source_sha256,
                            "accession_number": filing["accession_number"],
                            "filing_date": filing["filing_date"],
                            "form": filing["form"],
                            "subject_ciks": list(subject_ciks),
                            "subject_identity_verified": True,
                            "discovery_freeze_fingerprint": (
                                lit02_repair_v3_discovery_freeze_fingerprint()
                            ),
                        }
                    )
                elif status in {"INCOMPLETE", "CONFLICT"}:
                    incomplete_reasons.append(str(candidate.get("reason") or status))

        candidate, conflict = _select_latest_ready(ready_candidates)
        if conflict:
            return None, evidence_rows, [conflict]
        if candidate is None:
            return (
                None,
                evidence_rows,
                sorted(
                    set(
                        incomplete_reasons
                        or [
                            "NO_ADMISSIBLE_OFFICIAL_SEC_FINAL_TRANSACTION_AMENDMENT_EVIDENCE_V3"
                        ]
                    )
                ),
            )

        if candidate.get("path_id") == "TERMINAL_CASH":
            combined = " ".join(
                [
                    str(candidate.get("matched_excerpt") or ""),
                    *(
                        [str(value) for value in candidate.get("definition_excerpts") or []]
                        if isinstance(candidate.get("definition_excerpts"), list)
                        else []
                    ),
                ]
            )
            if _contains_contingent_consideration(combined):
                return None, evidence_rows, ["CONTINGENT_CONSIDERATION_NOT_SUPPORTED_V3"]

        path_id = str(candidate.get("path_id") or "")
        if path_id == "TICKER_CONTINUITY":
            successor_ticker = str(candidate.get("new_ticker") or "")
            consistent, successor_identity, reason = self._verify_successor_identity(
                successor_ticker=successor_ticker,
                endpoint_session=endpoint_session,
                predecessor=identity,
            )
            if not consistent:
                return None, evidence_rows, [reason]
            candidate["successor_identity"] = successor_identity
        elif path_id in {"TERMINAL_STOCK", "TERMINAL_MIXED"}:
            successor_ticker = str(candidate.get("successor_ticker") or "")
            if not successor_ticker:
                return None, evidence_rows, ["SUCCESSOR_TICKER_IDENTITY_REQUIRED"]
            overview = self._massive_overview(successor_ticker, endpoint_session)
            if overview is None:
                return None, evidence_rows, ["SUCCESSOR_TICKER_OVERVIEW_NOT_FOUND"]
            candidate["successor_identity"] = {
                "ticker": successor_ticker,
                "composite_figi": (
                    str(overview.get("composite_figi") or "").strip().upper() or None
                ),
                "cik": _normalize_cik(overview.get("cik")),
                "primary_exchange": overview.get("primary_exchange"),
                "security_type": overview.get("type"),
            }
        candidate["repair_v3_parser_certification"] = (
            LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION
        )
        candidate["discovery_freeze_fingerprint"] = (
            lit02_repair_v3_discovery_freeze_fingerprint()
        )
        return candidate, evidence_rows, []

    def _load_cached_case(self, case: Mapping[str, object]) -> dict[str, object] | None:
        result = super()._load_cached_case(case)
        if result is None:
            return None
        if result.get("repair_v3_discovery_freeze_fingerprint") != (
            lit02_repair_v3_discovery_freeze_fingerprint()
        ):
            return None
        return result

    def _write_case(self, case: Mapping[str, object], result: Mapping[str, object]) -> None:
        final_result = dict(result)
        final_result["repair_v3_discovery_contract"] = LIT02_REPAIR_V3_DISCOVERY_CONTRACT
        final_result["repair_v3_discovery_freeze_contract"] = (
            LIT02_REPAIR_V3_DISCOVERY_FREEZE_CONTRACT
        )
        final_result["repair_v3_discovery_freeze_fingerprint"] = (
            lit02_repair_v3_discovery_freeze_fingerprint()
        )
        super()._write_case(case, final_result)

    def run(self, *, force: bool = False) -> dict[str, object]:
        final_freeze = lit02_repair_v3_discovery_freeze_fingerprint()
        print(
            "[LIT-02][REPAIR-V3][DISCOVERY] official SEC quarterly master-index subject-CIK "
            f"discovery | freeze={final_freeze} | provider reads have not started"
        )
        report = super().run(force=force)
        persisted = json.loads(self.report_path().read_text(encoding="utf-8"))
        persisted["repair_v3_discovery_contract"] = LIT02_REPAIR_V3_DISCOVERY_CONTRACT
        persisted["repair_v3_discovery_freeze_contract"] = (
            LIT02_REPAIR_V3_DISCOVERY_FREEZE_CONTRACT
        )
        persisted["repair_v3_discovery_freeze_fingerprint"] = final_freeze
        persisted["repair_v3_discovery_source"] = "official SEC quarterly master.idx"
        persisted["repair_v3_discovery_quarters_read"] = len(self._v3_quarter_index_cache)
        persisted["repair_v3_subject_identity_verification_required"] = True
        persisted["report_fingerprint"] = _report_fingerprint_v3(persisted)
        atomic_write_text(self.report_path(), canonical_json(persisted) + "\n")
        output = dict(persisted)
        output["report_path"] = str(self.report_path())
        return output


assert lit02_repair_v3_discovery_freeze_payload()["required_source_coverage"] == 1.0
assert lit02_repair_v3_discovery_freeze_payload()["economic_outcome_values_allowed"] is False
assert lit02_repair_v3_discovery_freeze_payload()["new_price_or_return_reads_allowed"] is False
assert lit02_repair_v3_discovery_freeze_payload()["protected_reads_allowed"] is False
