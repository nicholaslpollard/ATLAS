from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.providers.sec_xbrl import SECCompanyFactsDocument, SECXBRLCompanyFactsClient


EARNINGS_INNOVATION_FEASIBILITY_CONTRACT = (
    "alpha-gate-sec-earnings-innovation-feasibility-v1-diluted-eps-source-only-no-market-outcomes"
)
EARNINGS_INNOVATION_FEASIBILITY_FINGERPRINT = (
    "c32e4aa83b25cdc23476098ffc30bd48908123d047d75f18f0d45b2acaffcd0d"
)
EARNINGS_INNOVATION_SOURCE_FINRA_MERGE = "715d8df8c07a58f10deeade14877757a6dea36a6"
EARNINGS_INNOVATION_MECHANISM = (
    "PIT_SEC_XBRL_DILUTED_EPS_SEASONAL_EARNINGS_INNOVATION_POST_PERIODIC_FILING_DRIFT"
)
EARNINGS_INNOVATION_SOURCE_START = date(2016, 1, 1)
EARNINGS_INNOVATION_SOURCE_CUTOFF = date(2026, 8, 11)
EARNINGS_INNOVATION_SAMPLE_SIZE = 300
EARNINGS_INNOVATION_SAMPLE_RULE = (
    "SHA256_CIK_PLUS_FEASIBILITY_CONTRACT_ASCENDING_FROM_ACCEPTED_PHASE32_SOURCE_ONLY_ISSUER_INVENTORY"
)
EARNINGS_INNOVATION_EPS_CONCEPT = "EarningsPerShareDiluted"
EARNINGS_INNOVATION_EPS_UNIT = "USD/shares"
EARNINGS_INNOVATION_ALLOWED_FORMS = ("10-Q", "10-K")
EARNINGS_INNOVATION_DIRECT_QUARTER_DURATION_DAYS = (70, 110)
EARNINGS_INNOVATION_HISTORY_READY_MIN_DIRECT_QUARTERS = 12
EARNINGS_INNOVATION_SUE_BASELINE_READY_MIN_DIRECT_QUARTERS = 16
EARNINGS_INNOVATION_MIN_SUCCESSFUL_DOCUMENTS = 270
EARNINGS_INNOVATION_MIN_EPS_DOCUMENTS = 210
EARNINGS_INNOVATION_MIN_HISTORY_READY_ISSUERS = 180
EARNINGS_INNOVATION_MIN_SUE_BASELINE_READY_ISSUERS = 120
EARNINGS_INNOVATION_MIN_DIRECT_QUARTER_OBSERVATIONS = 2500
EARNINGS_INNOVATION_MIN_CALENDAR_YEARS_OBSERVED = 8
EARNINGS_INNOVATION_MAX_SAME_ACCESSION_CONTEXT_CONFLICTS = 0
EARNINGS_INNOVATION_ANNOUNCEMENT_TIMING_CLAIM = "NOT_ESTABLISHED_AT_FEASIBILITY_GATE"
EARNINGS_INNOVATION_ALPHA_HYPOTHESES_FROZEN = False
EARNINGS_INNOVATION_TARGET_OUTCOME_READS_ALLOWED = False
EARNINGS_INNOVATION_PROTECTED_OUTCOME_READS_ALLOWED = False
EARNINGS_INNOVATION_PROVIDER_READS_ALLOWED = True
EARNINGS_INNOVATION_PROVIDER_WRITES = 0
EARNINGS_INNOVATION_BROKER_READS = 0
EARNINGS_INNOVATION_BROKER_WRITES = 0
EARNINGS_INNOVATION_ORDER_WRITES = 0
EARNINGS_INNOVATION_PAPER_SUBMITS = 0
EARNINGS_INNOVATION_LIVE_WRITES = 0
EARNINGS_INNOVATION_AUTOMATION_WRITES = 0
EARNINGS_INNOVATION_AUTOMATIC_BROKER_FAILOVER = False
EARNINGS_INNOVATION_PHASE33_SIGNAL_TO_TRADE_AUTHORITY = False

EARNINGS_INNOVATION_INPUT_RELATIVE = Path(
    "strategy_evaluation/phase32/predictor_v1/phase32_predictor_rows.jsonl"
)
EARNINGS_INNOVATION_REPORT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/sec_earnings_innovation_feasibility_v1/source_census.json"
)


class EarningsInnovationFeasibilityError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": EARNINGS_INNOVATION_FEASIBILITY_CONTRACT,
        "source_finra_merge": EARNINGS_INNOVATION_SOURCE_FINRA_MERGE,
        "mechanism": EARNINGS_INNOVATION_MECHANISM,
        "source_start": EARNINGS_INNOVATION_SOURCE_START.isoformat(),
        "source_cutoff": EARNINGS_INNOVATION_SOURCE_CUTOFF.isoformat(),
        "sample_size": EARNINGS_INNOVATION_SAMPLE_SIZE,
        "sample_rule": EARNINGS_INNOVATION_SAMPLE_RULE,
        "concept": EARNINGS_INNOVATION_EPS_CONCEPT,
        "unit": EARNINGS_INNOVATION_EPS_UNIT,
        "allowed_forms": list(EARNINGS_INNOVATION_ALLOWED_FORMS),
        "direct_quarter_duration_days": list(EARNINGS_INNOVATION_DIRECT_QUARTER_DURATION_DAYS),
        "history_ready_min_direct_quarters": EARNINGS_INNOVATION_HISTORY_READY_MIN_DIRECT_QUARTERS,
        "sue_baseline_ready_min_direct_quarters": (
            EARNINGS_INNOVATION_SUE_BASELINE_READY_MIN_DIRECT_QUARTERS
        ),
        "min_successful_documents": EARNINGS_INNOVATION_MIN_SUCCESSFUL_DOCUMENTS,
        "min_eps_documents": EARNINGS_INNOVATION_MIN_EPS_DOCUMENTS,
        "min_history_ready_issuers": EARNINGS_INNOVATION_MIN_HISTORY_READY_ISSUERS,
        "min_sue_baseline_ready_issuers": EARNINGS_INNOVATION_MIN_SUE_BASELINE_READY_ISSUERS,
        "min_direct_quarter_observations": EARNINGS_INNOVATION_MIN_DIRECT_QUARTER_OBSERVATIONS,
        "min_calendar_years_observed": EARNINGS_INNOVATION_MIN_CALENDAR_YEARS_OBSERVED,
        "max_same_accession_context_conflicts": (
            EARNINGS_INNOVATION_MAX_SAME_ACCESSION_CONTEXT_CONFLICTS
        ),
        "source": "SECXBRLCompanyFactsClient:data.sec.gov/api/xbrl/companyfacts",
        "announcement_timing_claim": EARNINGS_INNOVATION_ANNOUNCEMENT_TIMING_CLAIM,
        "alpha_hypotheses_frozen": EARNINGS_INNOVATION_ALPHA_HYPOTHESES_FROZEN,
        "target_outcome_reads_allowed": EARNINGS_INNOVATION_TARGET_OUTCOME_READS_ALLOWED,
        "protected_outcome_reads_allowed": EARNINGS_INNOVATION_PROTECTED_OUTCOME_READS_ALLOWED,
        "provider_reads_allowed": EARNINGS_INNOVATION_PROVIDER_READS_ALLOWED,
        "provider_writes": EARNINGS_INNOVATION_PROVIDER_WRITES,
        "broker_reads": EARNINGS_INNOVATION_BROKER_READS,
        "broker_writes": EARNINGS_INNOVATION_BROKER_WRITES,
        "order_writes": EARNINGS_INNOVATION_ORDER_WRITES,
        "paper_submits": EARNINGS_INNOVATION_PAPER_SUBMITS,
        "live_writes": EARNINGS_INNOVATION_LIVE_WRITES,
        "automation_writes": EARNINGS_INNOVATION_AUTOMATION_WRITES,
        "automatic_broker_failover": EARNINGS_INNOVATION_AUTOMATIC_BROKER_FAILOVER,
        "phase33_signal_to_trade_authority": EARNINGS_INNOVATION_PHASE33_SIGNAL_TO_TRADE_AUTHORITY,
    }


def earnings_innovation_feasibility_fingerprint() -> str:
    return hashlib.sha256(_canonical_json(_fingerprint_payload()).encode("utf-8")).hexdigest()


def _normalize_cik(value: object) -> str:
    text = str(value or "").strip()
    if not text.isdigit():
        raise EarningsInnovationFeasibilityError(f"source inventory contains nonnumeric issuer_cik: {value!r}")
    return str(int(text)).zfill(10)


def _load_source_ciks(path: Path) -> tuple[str, ...]:
    if not path.is_file():
        raise EarningsInnovationFeasibilityError(
            f"accepted Phase32 source-only issuer inventory is missing: {path}"
        )
    values: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise EarningsInnovationFeasibilityError(
                f"source inventory row is not an object: line {line_number}"
            )
        values.add(_normalize_cik(row.get("issuer_cik")))
    if len(values) < EARNINGS_INNOVATION_SAMPLE_SIZE:
        raise EarningsInnovationFeasibilityError(
            "source-only issuer inventory is too small for the frozen earnings-innovation sample: "
            f"{len(values)}"
        )
    return tuple(sorted(values))


def _sample_ciks(ciks: Iterable[str]) -> tuple[str, ...]:
    ranked = sorted(
        ciks,
        key=lambda cik: (
            hashlib.sha256(
                f"{cik}:{EARNINGS_INNOVATION_FEASIBILITY_CONTRACT}".encode("ascii")
            ).hexdigest(),
            cik,
        ),
    )
    return tuple(ranked[:EARNINGS_INNOVATION_SAMPLE_SIZE])


def _parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == text else None


def _as_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _duration_days(row: dict[str, Any]) -> int | None:
    start = _parse_date(row.get("start"))
    end = _parse_date(row.get("end"))
    if start is None or end is None or end < start:
        return None
    return (end - start).days + 1


def _extract_eps_entries(document: SECCompanyFactsDocument) -> tuple[dict[str, Any], ...]:
    namespace = document.facts.get("us-gaap")
    if not isinstance(namespace, dict):
        return ()
    concept = namespace.get(EARNINGS_INNOVATION_EPS_CONCEPT)
    if not isinstance(concept, dict):
        return ()
    units = concept.get("units")
    if not isinstance(units, dict):
        return ()
    entries = units.get(EARNINGS_INNOVATION_EPS_UNIT)
    if not isinstance(entries, list):
        return ()

    rows: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        form = str(entry.get("form") or "").strip()
        if form not in EARNINGS_INNOVATION_ALLOWED_FORMS:
            continue
        filed = _parse_date(entry.get("filed"))
        end = _parse_date(entry.get("end"))
        accession = str(entry.get("accn") or "").strip()
        value = _as_float(entry.get("val"))
        if (
            filed is None
            or filed < EARNINGS_INNOVATION_SOURCE_START
            or filed > EARNINGS_INNOVATION_SOURCE_CUTOFF
            or end is None
            or not accession
            or value is None
        ):
            continue
        rows.append(
            {
                "unit": EARNINGS_INNOVATION_EPS_UNIT,
                "start": entry.get("start"),
                "end": end.isoformat(),
                "filed": filed.isoformat(),
                "form": form,
                "accn": accession,
                "fy": entry.get("fy"),
                "fp": entry.get("fp"),
                "frame": entry.get("frame"),
                "val": value,
            }
        )
    rows.sort(
        key=lambda row: (
            str(row["filed"]),
            str(row["accn"]),
            str(row["start"]),
            str(row["end"]),
            str(row["form"]),
            str(row["fy"]),
            str(row["fp"]),
            str(row["frame"]),
            str(row["val"]),
        )
    )
    return tuple(rows)


def _same_accession_context_conflicts(entries: Iterable[dict[str, Any]]) -> int:
    contexts: defaultdict[tuple[str, ...], set[float]] = defaultdict(set)
    for row in entries:
        key = (
            str(row.get("accn") or ""),
            str(row.get("unit") or ""),
            str(row.get("start") or ""),
            str(row.get("end") or ""),
            str(row.get("form") or ""),
            str(row.get("fy") or ""),
            str(row.get("fp") or ""),
            str(row.get("frame") or ""),
        )
        value = _as_float(row.get("val"))
        if value is not None:
            contexts[key].add(value)
    return sum(1 for values in contexts.values() if len(values) > 1)


def _issuer_report(document: SECCompanyFactsDocument) -> dict[str, Any]:
    entries = _extract_eps_entries(document)
    lower, upper = EARNINGS_INNOVATION_DIRECT_QUARTER_DURATION_DAYS
    direct_rows = [
        row
        for row in entries
        if (days := _duration_days(row)) is not None and lower <= days <= upper
    ]
    direct_periods = sorted({str(row["end"]) for row in direct_rows})
    years = sorted(
        {
            parsed.year
            for row in direct_rows
            if (parsed := _parse_date(row.get("end"))) is not None
        }
    )
    direct_count = len(direct_periods)
    return {
        "issuer_cik": document.issuer_cik,
        "entity_name": document.entity_name,
        "source_url": document.source_url,
        "source_sha256": document.source_sha256,
        "eps_entry_count": len(entries),
        "eps_accession_count": len({str(row["accn"]) for row in entries}),
        "eps_period_end_count": len({str(row["end"]) for row in entries}),
        "direct_quarter_period_end_count": direct_count,
        "direct_quarter_first_end": direct_periods[0] if direct_periods else None,
        "direct_quarter_last_end": direct_periods[-1] if direct_periods else None,
        "calendar_years_observed": years,
        "same_accession_context_conflicts": _same_accession_context_conflicts(entries),
        "eps_history_ready": (
            direct_count >= EARNINGS_INNOVATION_HISTORY_READY_MIN_DIRECT_QUARTERS
        ),
        "sue_baseline_ready": (
            direct_count >= EARNINGS_INNOVATION_SUE_BASELINE_READY_MIN_DIRECT_QUARTERS
        ),
    }


class SECEarningsInnovationFeasibility:
    """Source-only census for diluted-EPS earnings innovation; no market outcomes."""

    def __init__(self, settings: AtlasSettings, sec_client: SECXBRLCompanyFactsClient) -> None:
        self.settings = settings
        self.sec_client = sec_client

    def run(self) -> dict[str, Any]:
        if (
            earnings_innovation_feasibility_fingerprint()
            != EARNINGS_INNOVATION_FEASIBILITY_FINGERPRINT
        ):
            raise EarningsInnovationFeasibilityError(
                "frozen earnings-innovation feasibility fingerprint drifted"
            )

        derived_root = self.settings.resolved_path(self.settings.data.paths.derived)
        source_path = derived_root / EARNINGS_INNOVATION_INPUT_RELATIVE
        source_ciks = _load_source_ciks(source_path)
        sample_ciks = _sample_ciks(source_ciks)

        issuer_reports: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        for index, cik in enumerate(sample_ciks, start=1):
            try:
                issuer_reports.append(_issuer_report(self.sec_client.company_facts(cik=cik)))
            except Exception as exc:
                failures.append(
                    {
                        "issuer_cik": cik,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
            if index == 1 or index % 10 == 0 or index == len(sample_ciks):
                print(
                    "SEC earnings-innovation source census progress: "
                    f"{index}/{len(sample_ciks)} success={len(issuer_reports)} "
                    f"failures={len(failures)}"
                )

        eps_documents = sum(int(row["eps_entry_count"] > 0) for row in issuer_reports)
        history_ready = sum(bool(row["eps_history_ready"]) for row in issuer_reports)
        sue_ready = sum(bool(row["sue_baseline_ready"]) for row in issuer_reports)
        direct_observations = sum(
            int(row["direct_quarter_period_end_count"]) for row in issuer_reports
        )
        observed_years = sorted(
            {
                int(year)
                for row in issuer_reports
                for year in row["calendar_years_observed"]
            }
        )
        context_conflicts = sum(
            int(row["same_accession_context_conflicts"]) for row in issuer_reports
        )
        gates = {
            "sample_size_exact": len(sample_ciks) == EARNINGS_INNOVATION_SAMPLE_SIZE,
            "successful_documents_min": (
                len(issuer_reports) >= EARNINGS_INNOVATION_MIN_SUCCESSFUL_DOCUMENTS
            ),
            "eps_documents_min": eps_documents >= EARNINGS_INNOVATION_MIN_EPS_DOCUMENTS,
            "history_ready_issuers_min": (
                history_ready >= EARNINGS_INNOVATION_MIN_HISTORY_READY_ISSUERS
            ),
            "sue_baseline_ready_issuers_min": (
                sue_ready >= EARNINGS_INNOVATION_MIN_SUE_BASELINE_READY_ISSUERS
            ),
            "direct_quarter_observations_min": (
                direct_observations
                >= EARNINGS_INNOVATION_MIN_DIRECT_QUARTER_OBSERVATIONS
            ),
            "calendar_years_observed_min": (
                len(observed_years) >= EARNINGS_INNOVATION_MIN_CALENDAR_YEARS_OBSERVED
            ),
            "same_accession_context_conflicts_max": (
                context_conflicts
                <= EARNINGS_INNOVATION_MAX_SAME_ACCESSION_CONTEXT_CONFLICTS
            ),
        }
        passed = all(gates.values())
        report_path = derived_root / EARNINGS_INNOVATION_REPORT_RELATIVE
        report = {
            "contract_version": EARNINGS_INNOVATION_FEASIBILITY_CONTRACT,
            "feasibility_fingerprint": EARNINGS_INNOVATION_FEASIBILITY_FINGERPRINT,
            "source_finra_merge": EARNINGS_INNOVATION_SOURCE_FINRA_MERGE,
            "mechanism": EARNINGS_INNOVATION_MECHANISM,
            "status": "FEASIBILITY_PASS" if passed else "FEASIBILITY_FAIL",
            "source_inventory_unique_ciks": len(source_ciks),
            "sample_size": len(sample_ciks),
            "sample_ciks": list(sample_ciks),
            "successful_documents": len(issuer_reports),
            "failed_documents": len(failures),
            "eps_documents": eps_documents,
            "history_ready_issuers": history_ready,
            "sue_baseline_ready_issuers": sue_ready,
            "direct_quarter_observations": direct_observations,
            "calendar_years_observed": observed_years,
            "same_accession_context_conflicts": context_conflicts,
            "issuer_reports": issuer_reports,
            "failures": failures,
            "gates": gates,
            "announcement_timing_claim": EARNINGS_INNOVATION_ANNOUNCEMENT_TIMING_CLAIM,
            "alpha_hypotheses_frozen": EARNINGS_INNOVATION_ALPHA_HYPOTHESES_FROZEN,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_reads_performed": len(sample_ciks),
            "provider_writes_performed": 0,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
            "automation_writes_performed": 0,
            "phase33_signal_to_trade_authority": False,
            "next_scientific_action": (
                "Freeze and run a dedicated source-only PIT original-accession and SEC-acceptance "
                "chronology audit before defining any earnings-innovation hypothesis or reading "
                "market outcomes."
                if passed
                else "Preserve this source-only negative result; do not weaken the frozen source "
                "gates or open market outcomes."
            ),
            "report_path": str(report_path),
            "pass": passed,
        }
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
