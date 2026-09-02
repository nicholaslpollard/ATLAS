from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Mapping

from packages.core.atomic_io import atomic_write_text
from packages.core.exceptions import ProviderError
from packages.core.settings import AtlasSettings
from packages.providers.sec_edgar import (
    SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP,
    sec_company_submissions_url,
)
from packages.providers.sec_edgar_archive import (
    SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES,
)

from .literature_momseason_lit02_source_feasibility import (
    LIT02_SOURCE_FEASIBILITY_STORAGE_ROOT,
)
from .literature_momseason_lit02_source_metadata import (
    LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
    LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT,
    LIT02_REQUIRED_SOURCE_COVERAGE,
    LIT02_SOURCE_METADATA_IDENTITY_CACHE,
    _declared_shard_urls,
    _fingerprint,
    _normalize_cik,
    _submission_rows,
)
from .literature_momseason_lit02_source_metadata_repair_v2 import (
    LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT,
    LIT02_SOURCE_METADATA_REPAIR_V2_REPORT,
    LIT02_SOURCE_METADATA_REPAIR_V2_STATUS_INCOMPLETE,
    LIT02_SOURCE_METADATA_REPAIR_V2_STORAGE_ROOT,
    _candidate_core,
    _select_latest_ready,
)
from .literature_momseason_lit02_source_metadata_repair_v2_certified import (
    LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION,
    MomSeasonLIT02SourceMetadataRepairV2Certified,
    parse_explicit_sec_ticker_change_v2_certified,
    parse_sec_terminal_transaction_v2_certified,
)
from .literature_momseason_lit02_source_metadata_repair_v2_diagnostic import (
    LIT02_REPAIR_V2_RESIDUAL_DIAGNOSTIC_REPORT,
    LIT02_REPAIR_V2_RESIDUAL_DIAGNOSTIC_STATUS,
)
from .literature_momseason_source import canonical_json


LIT02_SOURCE_METADATA_REPAIR_V3_CONTRACT = (
    "lit02-source-metadata-repair-v3-official-sec-final-transaction-amendments-no-prices"
)
LIT02_SOURCE_METADATA_REPAIR_V3_STATUS_READY = (
    "LIT02_DELISTING_AWARE_SOURCE_COVERAGE_READY"
)
LIT02_SOURCE_METADATA_REPAIR_V3_STATUS_INCOMPLETE = (
    "LIT02_DELISTING_AWARE_SOURCE_COVERAGE_INCOMPLETE"
)
LIT02_SOURCE_METADATA_REPAIR_V3_STORAGE_ROOT = "m3"
LIT02_SOURCE_METADATA_REPAIR_V3_REPORT = "r3.json"

# Accepted exact target-machine repair-v2 evidence and cached residual diagnostic.
LIT02_ACCEPTED_REPAIR_V2_CLASSIFICATION_FINGERPRINT = (
    "6d11081f7acf39783a9c6b2fde8119a1f19f9b8b3b87be0ab3fac59a8381faa2"
)
LIT02_ACCEPTED_REPAIR_V2_REPORT_FINGERPRINT = (
    "dca474d2d88c09f904c33e33659fbb88e4cdadcecd9d40666971b4482a1c657e"
)
LIT02_ACCEPTED_REPAIR_V2_RESIDUAL_DIAGNOSTIC_FINGERPRINT = (
    "90ed1f6ca7b433567d6a063f8ebead9c3789181f659c9175bb592ea8fe70b091"
)
LIT02_ACCEPTED_REPAIR_V2_CASES = 199
LIT02_ACCEPTED_REPAIR_V2_RESOLVED = 96
LIT02_ACCEPTED_REPAIR_V2_UNRESOLVED = 103

# This repair does not broaden the economic paths. It broadens only the official-SEC
# filing classes searched for explicit executed transaction facts. These two amendment
# forms can contain final results of third-party tender offers and Rule 13e-3 going-private
# transactions. Pre-transaction/proxy/registration/delisting-only forms remain excluded.
LIT02_REPAIR_V3_SEC_ALLOWED_FORMS = frozenset({"SC TO-T/A", "SC 13E3/A"})
LIT02_REPAIR_V3_SEC_EXPLICITLY_EXCLUDED_FORMS = frozenset(
    {
        "SC TO-C",
        "SC TO-T",
        "SC TO-I",
        "SC TO-I/A",
        "SC 13E3",
        "PREM14A",
        "DEFM14A",
        "S-4",
        "S-4/A",
        "F-4",
        "F-4/A",
        "424B3",
        "425",
        "25-NSE",
        "15-12B",
        "15-12G",
    }
)
LIT02_REPAIR_V3_SEC_LOOKBACK_DAYS = 370
LIT02_REPAIR_V3_SEC_FORWARD_DAYS = 10
LIT02_REPAIR_V3_SEC_MAX_CANDIDATE_FILINGS = 32


def lit02_repair_v3_source_expansion_payload() -> dict[str, object]:
    return {
        "contract_version": LIT02_SOURCE_METADATA_REPAIR_V3_CONTRACT,
        "accepted_source_policy_fingerprint": LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT,
        "accepted_feasibility_plan_fingerprint": LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
        "accepted_repair_v2_classification_fingerprint": (
            LIT02_ACCEPTED_REPAIR_V2_CLASSIFICATION_FINGERPRINT
        ),
        "accepted_repair_v2_report_fingerprint": LIT02_ACCEPTED_REPAIR_V2_REPORT_FINGERPRINT,
        "accepted_repair_v2_residual_diagnostic_fingerprint": (
            LIT02_ACCEPTED_REPAIR_V2_RESIDUAL_DIAGNOSTIC_FINGERPRINT
        ),
        "base_cases": LIT02_ACCEPTED_REPAIR_V2_CASES,
        "base_resolved_cases_immutable": LIT02_ACCEPTED_REPAIR_V2_RESOLVED,
        "base_unresolved_cases_eligible": LIT02_ACCEPTED_REPAIR_V2_UNRESOLVED,
        "sec_allowed_forms": sorted(LIT02_REPAIR_V3_SEC_ALLOWED_FORMS),
        "sec_explicitly_excluded_forms": sorted(
            LIT02_REPAIR_V3_SEC_EXPLICITLY_EXCLUDED_FORMS
        ),
        "sec_lookback_days": LIT02_REPAIR_V3_SEC_LOOKBACK_DAYS,
        "sec_forward_days": LIT02_REPAIR_V3_SEC_FORWARD_DAYS,
        "sec_max_candidate_filings": LIT02_REPAIR_V3_SEC_MAX_CANDIDATE_FILINGS,
        "parser_certification": LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION,
        "classification_rule": (
            "an added-form filing is admissible only when the already-certified contextual parser "
            "finds an explicit executed transaction/ticker-change fact on or before the frozen "
            "endpoint; a tender-offer result, proxy term, registration statement, delisting notice, "
            "or proposed consideration alone is never terminal-return authority"
        ),
        "economic_paths_changed": False,
        "required_source_coverage": LIT02_REQUIRED_SOURCE_COVERAGE,
        "economic_outcome_values_allowed": False,
        "new_price_or_return_reads_allowed": False,
        "protected_reads_allowed": False,
        "ticker_specific_exceptions_allowed": False,
    }


def lit02_repair_v3_source_expansion_fingerprint() -> str:
    return _fingerprint(lit02_repair_v3_source_expansion_payload())


def _filtered_sec_rows_v3(
    rows: list[dict[str, object]],
    *,
    start_date: date,
    end_date: date,
) -> list[dict[str, object]]:
    unique: dict[str, dict[str, object]] = {}
    for row in rows:
        accession = str(row.get("accessionNumber") or "").strip()
        form = str(row.get("form") or "").strip()
        filing_text = str(row.get("filingDate") or "").strip()
        if not accession or form not in LIT02_REPAIR_V3_SEC_ALLOWED_FORMS:
            continue
        try:
            filing_date = date.fromisoformat(filing_text)
        except ValueError:
            continue
        if not (start_date <= filing_date <= end_date):
            continue
        unique[accession] = {
            "accession_number": accession,
            "filing_date": filing_date.isoformat(),
            "form": form,
            "items": [],
            "primary_document": str(row.get("primaryDocument") or "").strip() or None,
        }
    ordered = sorted(
        unique.values(),
        key=lambda item: (str(item["filing_date"]), str(item["accession_number"])),
    )
    if len(ordered) > LIT02_REPAIR_V3_SEC_MAX_CANDIDATE_FILINGS:
        raise RuntimeError(
            "LIT-02 repair-v3 SEC source lookup exceeded bounded candidate filing count: "
            f"{len(ordered)} > {LIT02_REPAIR_V3_SEC_MAX_CANDIDATE_FILINGS}"
        )
    return ordered


def _report_fingerprint_v3(report: Mapping[str, object]) -> str:
    return _fingerprint(
        {
            key: value
            for key, value in report.items()
            if key
            not in {
                "source_metadata_provider_reads",
                "massive_source_metadata_reads",
                "sec_source_metadata_reads",
                "cached_case_manifests_reused",
            }
        }
    )


class MomSeasonLIT02SourceMetadataRepairV3(
    MomSeasonLIT02SourceMetadataRepairV2Certified
):
    """Outcome-free repair over only the accepted repair-v2 unresolved cases."""

    def __init__(self, settings: AtlasSettings, **kwargs: object) -> None:
        super().__init__(settings, **kwargs)
        self.v2_root = self.root
        self.root = self.feasibility_root / LIT02_SOURCE_METADATA_REPAIR_V3_STORAGE_ROOT

    def identity_cache_path(self) -> Path:
        # Identity evidence remains the accepted first-pass cache under development/l2/m/.
        return self.v1_root / LIT02_SOURCE_METADATA_IDENTITY_CACHE

    def report_path(self) -> Path:
        return self.root / LIT02_SOURCE_METADATA_REPAIR_V3_REPORT

    def case_path(self, case_id: str) -> Path:
        key = hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:12]
        return self.root / f"{key}.json"

    def _v2_case_path(self, case_id: str) -> Path:
        key = hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:12]
        return self.v2_root / f"{key}.json"

    def _require_v2_state(self) -> str:
        source_path = self.v2_root / LIT02_SOURCE_METADATA_REPAIR_V2_REPORT
        diagnostic_path = self.v2_root / LIT02_REPAIR_V2_RESIDUAL_DIAGNOSTIC_REPORT
        identity_path = self.identity_cache_path()
        if not source_path.is_file() or not diagnostic_path.is_file() or not identity_path.is_file():
            raise RuntimeError(
                "LIT-02 accepted repair-v2 report, residual diagnostic, and identity cache are required"
            )
        source = json.loads(source_path.read_text(encoding="utf-8"))
        diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
        identity = json.loads(identity_path.read_text(encoding="utf-8"))

        if source.get("status") != LIT02_SOURCE_METADATA_REPAIR_V2_STATUS_INCOMPLETE:
            raise RuntimeError("LIT-02 repair-v3 requires accepted incomplete repair-v2 state")
        if source.get("contract_version") != LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT:
            raise RuntimeError("LIT-02 repair-v3 repair-v2 contract mismatch")
        if (
            source.get("classification_fingerprint")
            != LIT02_ACCEPTED_REPAIR_V2_CLASSIFICATION_FINGERPRINT
        ):
            raise RuntimeError("LIT-02 repair-v3 repair-v2 classification fingerprint mismatch")
        if source.get("report_fingerprint") != LIT02_ACCEPTED_REPAIR_V2_REPORT_FINGERPRINT:
            raise RuntimeError("LIT-02 repair-v3 repair-v2 report fingerprint mismatch")
        if int(source.get("feasibility_cases") or 0) != LIT02_ACCEPTED_REPAIR_V2_CASES:
            raise RuntimeError("LIT-02 repair-v3 repair-v2 case count mismatch")
        if int(source.get("resolved_cases") or 0) != LIT02_ACCEPTED_REPAIR_V2_RESOLVED:
            raise RuntimeError("LIT-02 repair-v3 repair-v2 resolved count mismatch")
        if int(source.get("unresolved_cases") or 0) != LIT02_ACCEPTED_REPAIR_V2_UNRESOLVED:
            raise RuntimeError("LIT-02 repair-v3 repair-v2 unresolved count mismatch")
        if bool(source.get("lit02_economic_design_unblocked")):
            raise RuntimeError("LIT-02 repair-v3 refuses already-unblocked economic design")

        if diagnostic.get("status") != LIT02_REPAIR_V2_RESIDUAL_DIAGNOSTIC_STATUS:
            raise RuntimeError("LIT-02 repair-v3 residual diagnostic status mismatch")
        if (
            diagnostic.get("diagnostic_fingerprint")
            != LIT02_ACCEPTED_REPAIR_V2_RESIDUAL_DIAGNOSTIC_FINGERPRINT
        ):
            raise RuntimeError("LIT-02 repair-v3 residual diagnostic fingerprint mismatch")

        for field in (
            "economic_outcome_values_read",
            "new_price_or_return_provider_reads",
            "protected_return_rows_read",
            "broker_reads_performed",
            "broker_writes_performed",
            "order_writes_performed",
            "paper_submits_performed",
            "live_writes_performed",
        ):
            if int(source.get(field) or 0) != 0:
                raise RuntimeError(f"LIT-02 repair-v3 base safety field is nonzero: {field}")
        if bool(source.get("protected_holdout_consumed")):
            raise RuntimeError("LIT-02 repair-v3 refuses consumed protected holdout")

        fingerprint = str(identity.get("identity_evidence_fingerprint") or "")
        if not fingerprint:
            raise RuntimeError("LIT-02 repair-v3 accepted identity fingerprint missing")
        return fingerprint

    def _load_v2_case(self, case: Mapping[str, object]) -> dict[str, object]:
        case_id = str(case.get("case_id") or "")
        path = self._v2_case_path(case_id)
        if not path.is_file():
            raise RuntimeError(f"LIT-02 accepted repair-v2 case manifest missing: {case_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("contract_version") != LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT:
            raise RuntimeError(f"LIT-02 accepted repair-v2 case contract mismatch: {case_id}")
        result = payload.get("result")
        if not isinstance(result, Mapping):
            raise RuntimeError(f"LIT-02 accepted repair-v2 case result invalid: {case_id}")
        return dict(result)

    def _load_cached_case(self, case: Mapping[str, object]) -> dict[str, object] | None:
        path = self.case_path(str(case.get("case_id") or ""))
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("contract_version") != LIT02_SOURCE_METADATA_REPAIR_V3_CONTRACT
            or payload.get("source_policy_fingerprint")
            != LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT
            or payload.get("feasibility_plan_fingerprint")
            != LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT
            or payload.get("base_repair_v2_classification_fingerprint")
            != LIT02_ACCEPTED_REPAIR_V2_CLASSIFICATION_FINGERPRINT
            or payload.get("base_repair_v2_report_fingerprint")
            != LIT02_ACCEPTED_REPAIR_V2_REPORT_FINGERPRINT
            or payload.get("base_repair_v2_residual_diagnostic_fingerprint")
            != LIT02_ACCEPTED_REPAIR_V2_RESIDUAL_DIAGNOSTIC_FINGERPRINT
            or payload.get("source_expansion_fingerprint")
            != lit02_repair_v3_source_expansion_fingerprint()
            or payload.get("case_input_fingerprint") != _fingerprint(dict(case))
            or not isinstance(payload.get("result"), Mapping)
        ):
            return None
        return dict(payload["result"])

    def _write_case(self, case: Mapping[str, object], result: Mapping[str, object]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.case_path(str(case["case_id"])),
            canonical_json(
                {
                    "contract_version": LIT02_SOURCE_METADATA_REPAIR_V3_CONTRACT,
                    "source_policy_fingerprint": LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT,
                    "feasibility_plan_fingerprint": LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
                    "base_repair_v2_classification_fingerprint": (
                        LIT02_ACCEPTED_REPAIR_V2_CLASSIFICATION_FINGERPRINT
                    ),
                    "base_repair_v2_report_fingerprint": LIT02_ACCEPTED_REPAIR_V2_REPORT_FINGERPRINT,
                    "base_repair_v2_residual_diagnostic_fingerprint": (
                        LIT02_ACCEPTED_REPAIR_V2_RESIDUAL_DIAGNOSTIC_FINGERPRINT
                    ),
                    "source_expansion_fingerprint": lit02_repair_v3_source_expansion_fingerprint(),
                    "case_id": case["case_id"],
                    "case_input_fingerprint": _fingerprint(dict(case)),
                    "result": dict(result),
                    "economic_outcome_values_read": 0,
                    "new_price_or_return_provider_reads": 0,
                    "protected_return_rows_read": 0,
                    "protected_holdout_consumed": False,
                }
            )
            + "\n",
        )

    def _sec_candidate_filings_v3(
        self,
        *,
        cik: str,
        endpoint_session: date,
    ) -> tuple[list[dict[str, object]], str]:
        start_date = endpoint_session - timedelta(days=LIT02_REPAIR_V3_SEC_LOOKBACK_DAYS)
        end_date = endpoint_session + timedelta(days=LIT02_REPAIR_V3_SEC_FORWARD_DAYS)
        root_url = sec_company_submissions_url(cik=cik)
        try:
            payload, root_text = self._sec_get_json(root_url)
        except ProviderError as exc:
            if "404" in str(exc):
                return [], "SEC_COMPANY_SUBMISSIONS_NOT_FOUND"
            raise
        rows = _submission_rows(payload)
        shard_urls = _declared_shard_urls(
            payload,
            start_date=start_date,
            end_date=end_date,
        )
        if len(shard_urls) > SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP:
            raise RuntimeError("LIT-02 repair-v3 SEC declared-shard bound changed")
        for shard_url in shard_urls:
            shard_payload, _ = self._sec_get_json(shard_url)
            rows.extend(_submission_rows(shard_payload))
        return (
            _filtered_sec_rows_v3(rows, start_date=start_date, end_date=end_date),
            hashlib.sha256(root_text.encode("utf-8")).hexdigest(),
        )

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
        try:
            filings, submissions_sha = self._sec_candidate_filings_v3(
                cik=cik,
                endpoint_session=endpoint_session,
            )
        except RuntimeError as exc:
            return None, [], [str(exc)]

        evidence_rows: list[dict[str, object]] = []
        ready_candidates: list[dict[str, object]] = []
        incomplete_reasons: list[str] = []
        for filing in filings:
            accession = str(filing["accession_number"])
            if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
                incomplete_reasons.append("SEC_ACCESSION_FORMAT_INVALID")
                continue
            filename = f"edgar/data/{int(cik)}/{accession}.txt"
            document = self._sec_get_submission(filename)
            ticker_candidate = parse_explicit_sec_ticker_change_v2_certified(
                document.text,
                endpoint_session=endpoint_session,
                historical_ticker=historical_ticker,
            )
            terminal_candidate = parse_sec_terminal_transaction_v2_certified(
                document.text,
                endpoint_session=endpoint_session,
                historical_ticker=historical_ticker,
            )
            evidence_rows.append(
                {
                    **filing,
                    "submission_source_url": document.source_url,
                    "submission_source_sha256": document.source_sha256,
                    "company_submissions_sha256": submissions_sha,
                    "ticker_change_candidate": ticker_candidate,
                    "terminal_candidate": terminal_candidate,
                    "source_expansion_fingerprint": (
                        lit02_repair_v3_source_expansion_fingerprint()
                    ),
                    "parser_certification": (
                        LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION
                    ),
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
                            "accession_number": accession,
                            "filing_date": filing["filing_date"],
                            "form": filing["form"],
                            "source_expansion_fingerprint": (
                                lit02_repair_v3_source_expansion_fingerprint()
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
        candidate["source_expansion_fingerprint"] = (
            lit02_repair_v3_source_expansion_fingerprint()
        )
        return candidate, evidence_rows, []

    def _retry_instrument_v3(
        self,
        *,
        v2_instrument: Mapping[str, object],
        endpoint_session: date,
        historical_ticker: str,
    ) -> dict[str, object]:
        if v2_instrument.get("resolution_status") == "RESOLVED":
            return dict(v2_instrument)
        identity = v2_instrument.get("identity")
        if not isinstance(identity, Mapping):
            return dict(v2_instrument)

        sec_candidate, sec_evidence, sec_reasons = self._sec_resolution_v3(
            identity=identity,
            endpoint_session=endpoint_session,
            historical_ticker=historical_ticker,
        )
        if sec_candidate is not None:
            return {
                "instrument_id": v2_instrument.get("instrument_id"),
                "identity": dict(identity),
                "resolution_status": "RESOLVED",
                "path_id": sec_candidate.get("path_id"),
                "classification": sec_candidate,
                "unresolved_reasons": [],
                "massive_evidence": v2_instrument.get("massive_evidence"),
                "sec_evidence": sec_evidence,
                "repair_version": LIT02_SOURCE_METADATA_REPAIR_V3_CONTRACT,
                "source_repair_v3_action": "V2_UNRESOLVED_RESOLVED_BY_ADDED_OFFICIAL_SEC_FORM",
            }

        prior = {
            str(value)
            for value in (v2_instrument.get("unresolved_reasons") or [])
            if str(value)
        }
        prior.update(sec_reasons)
        return {
            "instrument_id": v2_instrument.get("instrument_id"),
            "identity": dict(identity),
            "resolution_status": "UNRESOLVED",
            "path_id": None,
            "classification": None,
            "unresolved_reasons": sorted(prior or {"SOURCE_UNRESOLVED_V3"}),
            "massive_evidence": v2_instrument.get("massive_evidence"),
            "sec_evidence": sec_evidence,
            "repair_version": LIT02_SOURCE_METADATA_REPAIR_V3_CONTRACT,
            "source_repair_v3_action": "V2_UNRESOLVED_RETRIED_WITH_ADDED_OFFICIAL_SEC_FORMS",
        }

    def run(self, *, force: bool = False) -> dict[str, object]:
        cases, _ = self._load_and_require_plan()
        identity_fingerprint = self._require_v2_state()
        expansion_fingerprint = lit02_repair_v3_source_expansion_fingerprint()

        results: list[dict[str, object]] = []
        cached_cases = 0
        retried_cases = 0
        reused_v2_resolved = 0
        started = time.monotonic()
        total = len(cases)

        print(
            "[LIT-02][REPAIR-V3] started | "
            f"cases={total} | base_resolved={LIT02_ACCEPTED_REPAIR_V2_RESOLVED} | "
            f"base_unresolved={LIT02_ACCEPTED_REPAIR_V2_UNRESOLVED} | "
            f"lookback={LIT02_REPAIR_V3_SEC_LOOKBACK_DAYS}d | "
            f"forms={sorted(LIT02_REPAIR_V3_SEC_ALLOWED_FORMS)}"
        )
        print(
            "[LIT-02][REPAIR-V3] same frozen return paths | certified parser unchanged | "
            "economic outcomes disabled | protected reads disabled | "
            f"SEC submission ceiling={SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES}"
        )
        print(
            "[LIT-02][REPAIR-V3] source-expansion-fingerprint="
            f"{expansion_fingerprint}"
        )

        for index, case in enumerate(cases, start=1):
            endpoint = date.fromisoformat(str(case["endpoint_session"]))
            ticker = str(case["historical_ticker"])
            cached = None if force else self._load_cached_case(case)
            if cached is not None:
                result = cached
                cached_cases += 1
                mode = "cache"
            else:
                v2_result = self._load_v2_case(case)
                if v2_result.get("resolution_status") == "RESOLVED":
                    result = dict(v2_result)
                    result["source_repair_v3_action"] = "V2_RESOLVED_REUSED_IMMUTABLY"
                    reused_v2_resolved += 1
                    mode = "v2-reuse"
                else:
                    instrument_results = [
                        self._retry_instrument_v3(
                            v2_instrument=dict(item),
                            endpoint_session=endpoint,
                            historical_ticker=ticker,
                        )
                        for item in (v2_result.get("instrument_results") or [])
                        if isinstance(item, Mapping)
                    ]
                    result = self._aggregate_case(case, instrument_results)
                    result["source_repair_v3_action"] = (
                        "V2_UNRESOLVED_RETRIED_WITH_ADDED_OFFICIAL_SEC_FORMS"
                    )
                    retried_cases += 1
                    mode = "repair-v3"
                self._write_case(case, result)
            results.append(result)

            elapsed = time.monotonic() - started
            rate = index / elapsed if elapsed > 0 else 0.0
            remaining = (total - index) / rate if rate > 0 else 0.0
            print(
                f"[LIT-02][REPAIR-V3] case {index}/{total} {(index / total) * 100.0:.1f}% "
                f"| elapsed={elapsed:.1f}s ETA={remaining:.1f}s | {endpoint} {ticker} "
                f"| mode={mode} | status={result.get('resolution_status')} "
                f"| path={result.get('path_id') or 'SOURCE_UNRESOLVED'} | "
                f"provider_reads={self.provider_reads}"
            )

        total_resolved = sum(
            1 for item in results if item.get("resolution_status") == "RESOLVED"
        )
        path_counts = Counter(
            str(item.get("path_id") or "SOURCE_UNRESOLVED") for item in results
        )
        reason_counts: Counter[str] = Counter()
        for item in results:
            if item.get("resolution_status") == "RESOLVED":
                continue
            for reason in item.get("unresolved_reasons") or []:
                reason_counts[str(reason)] += 1

        coverage = total_resolved / total if total else 0.0
        ready = total > 0 and coverage >= LIT02_REQUIRED_SOURCE_COVERAGE
        classification_fingerprint = _fingerprint(
            sorted(
                (
                    {
                        "case_id": item.get("case_id"),
                        "resolution_status": item.get("resolution_status"),
                        "path_id": item.get("path_id"),
                        "classification": item.get("classification"),
                        "unresolved_reasons": item.get("unresolved_reasons"),
                    }
                    for item in results
                ),
                key=lambda item: str(item.get("case_id") or ""),
            )
        )

        report: dict[str, object] = {
            "status": (
                LIT02_SOURCE_METADATA_REPAIR_V3_STATUS_READY
                if ready
                else LIT02_SOURCE_METADATA_REPAIR_V3_STATUS_INCOMPLETE
            ),
            "contract_version": LIT02_SOURCE_METADATA_REPAIR_V3_CONTRACT,
            "source_policy_fingerprint": LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT,
            "feasibility_plan_fingerprint": LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
            "base_repair_v2_classification_fingerprint": (
                LIT02_ACCEPTED_REPAIR_V2_CLASSIFICATION_FINGERPRINT
            ),
            "base_repair_v2_report_fingerprint": LIT02_ACCEPTED_REPAIR_V2_REPORT_FINGERPRINT,
            "base_repair_v2_residual_diagnostic_fingerprint": (
                LIT02_ACCEPTED_REPAIR_V2_RESIDUAL_DIAGNOSTIC_FINGERPRINT
            ),
            "source_expansion_fingerprint": expansion_fingerprint,
            "identity_evidence_fingerprint": identity_fingerprint,
            "parser_certification": LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION,
            "feasibility_cases": total,
            "base_resolved_cases": LIT02_ACCEPTED_REPAIR_V2_RESOLVED,
            "base_unresolved_cases": LIT02_ACCEPTED_REPAIR_V2_UNRESOLVED,
            "resolved_cases": total_resolved,
            "unresolved_cases": total - total_resolved,
            "newly_resolved_cases": total_resolved - LIT02_ACCEPTED_REPAIR_V2_RESOLVED,
            "source_coverage": coverage,
            "required_source_coverage": LIT02_REQUIRED_SOURCE_COVERAGE,
            "path_counts": dict(sorted(path_counts.items())),
            "unresolved_reason_counts": dict(sorted(reason_counts.items())),
            "classification_fingerprint": classification_fingerprint,
            "repair_v3_sec_lookback_days": LIT02_REPAIR_V3_SEC_LOOKBACK_DAYS,
            "repair_v3_sec_forward_days": LIT02_REPAIR_V3_SEC_FORWARD_DAYS,
            "repair_v3_sec_allowed_forms": sorted(LIT02_REPAIR_V3_SEC_ALLOWED_FORMS),
            "repair_v3_sec_explicitly_excluded_forms": sorted(
                LIT02_REPAIR_V3_SEC_EXPLICITLY_EXCLUDED_FORMS
            ),
            "source_metadata_provider_reads": self.provider_reads,
            "massive_source_metadata_reads": self._massive_reads,
            "sec_source_metadata_reads": self._sec_reads,
            "cached_case_manifests_reused": cached_cases,
            "v2_resolved_cases_reused": reused_v2_resolved,
            "v2_unresolved_cases_retried": retried_cases,
            "economic_outcome_values_read": 0,
            "new_price_or_return_provider_reads": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
            "phase33_signal_to_trade_authority": False,
            "production_authority": False,
            "lit02_economic_design_unblocked": ready,
            "fresh_confirmatory_reuse_of_lit01_2021_09_to_2026_04": False,
            "next_action": (
                "Freeze a fresh/non-reused LIT-02 economic-development design before any economic outcome read."
                if ready
                else (
                    "Source coverage remains below the frozen 100% gate after the prospectively frozen "
                    "official-SEC final-transaction amendment expansion. Do not read price/return outcomes. "
                    "Close LIT-02 as source-infeasible unless a separate general, outcome-independent source "
                    "mechanism is frozen before any further provider read."
                )
            ),
        }
        report["report_fingerprint"] = _report_fingerprint_v3(report)
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path(), canonical_json(report) + "\n")
        output = dict(report)
        output["report_path"] = str(self.report_path())
        return output


assert LIT02_REQUIRED_SOURCE_COVERAGE == 1.0
assert LIT02_REPAIR_V3_SEC_ALLOWED_FORMS == frozenset({"SC TO-T/A", "SC 13E3/A"})
assert not (
    LIT02_REPAIR_V3_SEC_ALLOWED_FORMS & LIT02_REPAIR_V3_SEC_EXPLICITLY_EXCLUDED_FORMS
)
