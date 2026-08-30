from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.providers.sec_xbrl import SECCompanyFactsDocument, SECXBRLCompanyFactsClient


XBRL_FEASIBILITY_CONTRACT = (
    "alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes"
)
XBRL_SOURCE_PHASE32_MERGE = "69f8aa81289934b71f2652482c747391917c15a3"
XBRL_MECHANISM = "PIT_SEC_XBRL_QUARTERLY_FUNDAMENTAL_PROFITABILITY_AND_ACCRUAL_QUALITY"
XBRL_ALPHA_HYPOTHESES_FROZEN = False
XBRL_TARGET_OUTCOME_READS_ALLOWED = False
XBRL_PROTECTED_OUTCOME_READS_ALLOWED = False
XBRL_PROVIDER_READS_ALLOWED = True
XBRL_PROVIDER_WRITES = 0
XBRL_BROKER_READS = 0
XBRL_BROKER_WRITES = 0
XBRL_ORDER_WRITES = 0
XBRL_PAPER_SUBMITS = 0
XBRL_LIVE_WRITES = 0
XBRL_AUTOMATION_WRITES = 0
XBRL_AUTOMATIC_BROKER_FAILOVER = False
XBRL_SOURCE_START = date(2016, 1, 1)
XBRL_SOURCE_CUTOFF = date(2026, 8, 11)
XBRL_SAMPLE_SIZE = 200
XBRL_MIN_SUCCESSFUL_DOCUMENTS = 160
XBRL_MIN_ACCRUAL_HISTORY_READY = 100
XBRL_MIN_PROFITABILITY_HISTORY_READY = 80
XBRL_MIN_PERIOD_ENDS_PER_GROUP = 8
XBRL_INPUT_RELATIVE = Path(
    "strategy_evaluation/phase32/predictor_v1/phase32_predictor_rows.jsonl"
)
XBRL_REPORT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/xbrl_feasibility_v1/source_census.json"
)


@dataclass(frozen=True, slots=True)
class XBRLConceptGroup:
    group_id: str
    tags: tuple[str, ...]


XBRL_CONCEPT_GROUPS = (
    XBRLConceptGroup("assets", ("Assets",)),
    XBRLConceptGroup("net_income", ("NetIncomeLoss",)),
    XBRLConceptGroup(
        "operating_cash_flow", ("NetCashProvidedByUsedInOperatingActivities",)
    ),
    XBRLConceptGroup(
        "revenue",
        (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ),
    ),
    XBRLConceptGroup("gross_profit", ("GrossProfit",)),
    XBRLConceptGroup(
        "cost_of_revenue", ("CostOfRevenue", "CostOfGoodsAndServicesSold")
    ),
)


class XBRLFeasibilityError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": XBRL_FEASIBILITY_CONTRACT,
        "source_phase32_merge": XBRL_SOURCE_PHASE32_MERGE,
        "mechanism": XBRL_MECHANISM,
        "source_start": XBRL_SOURCE_START.isoformat(),
        "source_cutoff": XBRL_SOURCE_CUTOFF.isoformat(),
        "sample_size": XBRL_SAMPLE_SIZE,
        "min_successful_documents": XBRL_MIN_SUCCESSFUL_DOCUMENTS,
        "min_accrual_history_ready": XBRL_MIN_ACCRUAL_HISTORY_READY,
        "min_profitability_history_ready": XBRL_MIN_PROFITABILITY_HISTORY_READY,
        "min_period_ends_per_group": XBRL_MIN_PERIOD_ENDS_PER_GROUP,
        "concept_groups": [asdict(group) for group in XBRL_CONCEPT_GROUPS],
        "sample_rule": "SHA256_ZERO_PADDED_CIK_ASCENDING_FROM_ACCEPTED_PHASE32_SOURCE_ONLY_ISSUER_INVENTORY",
        "source": "SECXBRLCompanyFactsClient:data.sec.gov/api/xbrl/companyfacts",
        "alpha_hypotheses_frozen": XBRL_ALPHA_HYPOTHESES_FROZEN,
        "target_outcome_reads_allowed": XBRL_TARGET_OUTCOME_READS_ALLOWED,
        "protected_outcome_reads_allowed": XBRL_PROTECTED_OUTCOME_READS_ALLOWED,
        "provider_reads_allowed": XBRL_PROVIDER_READS_ALLOWED,
        "external_mutation_authority": {
            "provider_writes": XBRL_PROVIDER_WRITES,
            "broker_reads": XBRL_BROKER_READS,
            "broker_writes": XBRL_BROKER_WRITES,
            "order_writes": XBRL_ORDER_WRITES,
            "paper_submits": XBRL_PAPER_SUBMITS,
            "live_writes": XBRL_LIVE_WRITES,
            "automation_writes": XBRL_AUTOMATION_WRITES,
            "automatic_broker_failover": XBRL_AUTOMATIC_BROKER_FAILOVER,
        },
    }


def xbrl_feasibility_fingerprint() -> str:
    return hashlib.sha256(_canonical_json(_fingerprint_payload()).encode("utf-8")).hexdigest()


def _normalize_cik(value: object) -> str:
    text = str(value or "").strip()
    if not text.isdigit():
        raise XBRLFeasibilityError(f"source inventory contains nonnumeric issuer_cik: {value!r}")
    return str(int(text)).zfill(10)


def _load_source_ciks(path: Path) -> tuple[str, ...]:
    if not path.is_file():
        raise XBRLFeasibilityError(
            f"accepted Phase32 predictor source inventory is missing: {path}"
        )
    values: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise XBRLFeasibilityError(f"source inventory row is not an object: line {line_number}")
        values.add(_normalize_cik(row.get("issuer_cik")))
    if len(values) < XBRL_SAMPLE_SIZE:
        raise XBRLFeasibilityError(
            f"source-only issuer inventory is too small for frozen feasibility sample: {len(values)}"
        )
    return tuple(sorted(values))


def _sample_ciks(ciks: Iterable[str]) -> tuple[str, ...]:
    ranked = sorted(
        ciks,
        key=lambda cik: (hashlib.sha256(cik.encode("ascii")).hexdigest(), cik),
    )
    return tuple(ranked[:XBRL_SAMPLE_SIZE])


def _parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _relevant_entries(document: SECCompanyFactsDocument) -> tuple[dict[str, Any], ...]:
    namespace = document.facts.get("us-gaap")
    if not isinstance(namespace, dict):
        return ()
    allowed_tags = {tag for group in XBRL_CONCEPT_GROUPS for tag in group.tags}
    rows: list[dict[str, Any]] = []
    for tag in sorted(allowed_tags):
        concept = namespace.get(tag)
        if not isinstance(concept, dict):
            continue
        units = concept.get("units")
        if not isinstance(units, dict):
            continue
        for unit, entries in sorted(units.items()):
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                filed = _parse_date(entry.get("filed"))
                if filed is None or filed < XBRL_SOURCE_START or filed > XBRL_SOURCE_CUTOFF:
                    continue
                form = str(entry.get("form") or "").strip()
                if form not in {"10-Q", "10-K"}:
                    continue
                accn = str(entry.get("accn") or "").strip()
                end = str(entry.get("end") or "").strip()
                if not accn or not end:
                    continue
                rows.append(
                    {
                        "tag": tag,
                        "unit": str(unit),
                        "start": entry.get("start"),
                        "end": end,
                        "filed": filed.isoformat(),
                        "form": form,
                        "accn": accn,
                        "fy": entry.get("fy"),
                        "fp": entry.get("fp"),
                        "frame": entry.get("frame"),
                        "val": entry.get("val"),
                    }
                )
    rows.sort(
        key=lambda row: (
            str(row["filed"]),
            str(row["accn"]),
            str(row["tag"]),
            str(row["unit"]),
            str(row["start"]),
            str(row["end"]),
            str(row["frame"]),
            str(row["val"]),
        )
    )
    return tuple(rows)


def _group_summary(entries: tuple[dict[str, Any], ...]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for group in XBRL_CONCEPT_GROUPS:
        selected = [row for row in entries if row["tag"] in group.tags]
        out[group.group_id] = {
            "entry_count": len(selected),
            "accession_count": len({str(row["accn"]) for row in selected}),
            "period_end_count": len({str(row["end"]) for row in selected}),
            "tags_observed": sorted({str(row["tag"]) for row in selected}),
            "units_observed": sorted({str(row["unit"]) for row in selected}),
            "first_filed": min((str(row["filed"]) for row in selected), default=None),
            "last_filed": max((str(row["filed"]) for row in selected), default=None),
        }
    return out


def _ready(summary: dict[str, dict[str, Any]], group_id: str) -> bool:
    return int(summary[group_id]["period_end_count"]) >= XBRL_MIN_PERIOD_ENDS_PER_GROUP


def _issuer_report(document: SECCompanyFactsDocument) -> dict[str, Any]:
    entries = _relevant_entries(document)
    summary = _group_summary(entries)
    accrual_ready = all(
        _ready(summary, group_id)
        for group_id in ("assets", "net_income", "operating_cash_flow")
    )
    profitability_ready = _ready(summary, "assets") and _ready(summary, "revenue") and (
        _ready(summary, "gross_profit") or _ready(summary, "cost_of_revenue")
    )
    relevant_text = "".join(_canonical_json(row) + "\n" for row in entries)
    return {
        "issuer_cik": document.issuer_cik,
        "entity_name": document.entity_name,
        "source_url": document.source_url,
        "relevant_source_sha256": hashlib.sha256(relevant_text.encode("utf-8")).hexdigest(),
        "relevant_fact_entries": len(entries),
        "concept_groups": summary,
        "accrual_history_ready": accrual_ready,
        "profitability_history_ready": profitability_ready,
    }


class XBRLFundamentalFeasibility:
    """Source-only census for a materially different SEC XBRL alpha mechanism."""

    def __init__(self, settings: AtlasSettings, sec_client: SECXBRLCompanyFactsClient) -> None:
        self.settings = settings
        self.sec_client = sec_client

    def run(self) -> dict[str, Any]:
        derived_root = self.settings.resolved_path(self.settings.data.paths.derived)
        source_path = derived_root / XBRL_INPUT_RELATIVE
        source_ciks = _load_source_ciks(source_path)
        sample_ciks = _sample_ciks(source_ciks)

        issuer_reports: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        for index, cik in enumerate(sample_ciks, start=1):
            try:
                document = self.sec_client.company_facts(cik=cik)
                issuer_reports.append(_issuer_report(document))
            except Exception as exc:  # census records source failures; final gates decide acceptance
                failures.append(
                    {
                        "issuer_cik": cik,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
            if index == 1 or index % 10 == 0 or index == len(sample_ciks):
                print(
                    f"XBRL source census progress: {index}/{len(sample_ciks)} "
                    f"success={len(issuer_reports)} failures={len(failures)}"
                )

        accrual_ready = sum(bool(row["accrual_history_ready"]) for row in issuer_reports)
        profitability_ready = sum(bool(row["profitability_history_ready"]) for row in issuer_reports)
        gates = {
            "sample_size_exact": len(sample_ciks) == XBRL_SAMPLE_SIZE,
            "successful_documents_min": len(issuer_reports) >= XBRL_MIN_SUCCESSFUL_DOCUMENTS,
            "accrual_history_ready_min": accrual_ready >= XBRL_MIN_ACCRUAL_HISTORY_READY,
            "profitability_history_ready_min": profitability_ready
            >= XBRL_MIN_PROFITABILITY_HISTORY_READY,
        }
        group_presence = Counter()
        for row in issuer_reports:
            for group_id, values in row["concept_groups"].items():
                if int(values["period_end_count"]) >= XBRL_MIN_PERIOD_ENDS_PER_GROUP:
                    group_presence[group_id] += 1

        report = {
            "contract_version": XBRL_FEASIBILITY_CONTRACT,
            "feasibility_fingerprint": xbrl_feasibility_fingerprint(),
            "source_phase32_merge": XBRL_SOURCE_PHASE32_MERGE,
            "mechanism": XBRL_MECHANISM,
            "status": "FEASIBILITY_PASS" if all(gates.values()) else "FEASIBILITY_FAIL",
            "pass": all(gates.values()),
            "alpha_hypotheses_frozen": False,
            "performance_evaluated": False,
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
            "automatic_broker_failover": False,
            "source_inventory_path": str(source_path),
            "source_inventory_sha256": sha256_file(source_path),
            "source_inventory_unique_ciks": len(source_ciks),
            "sample_rule": "SHA256_ZERO_PADDED_CIK_ASCENDING",
            "sample_size": len(sample_ciks),
            "sample_ciks": list(sample_ciks),
            "successful_documents": len(issuer_reports),
            "failed_documents": len(failures),
            "accrual_history_ready": accrual_ready,
            "profitability_history_ready": profitability_ready,
            "group_history_ready_counts": dict(sorted(group_presence.items())),
            "gates": gates,
            "issuer_reports": issuer_reports,
            "failures": failures,
            "next_scientific_action": (
                "If feasibility passes, independently audit PIT accession/acceptance-time reconstruction "
                "for original 10-Q/10-K facts, then freeze a finite hypothesis family before any market outcomes."
            ),
        }

        report_path = derived_root / XBRL_REPORT_RELATIVE
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(report_path)
        return report
