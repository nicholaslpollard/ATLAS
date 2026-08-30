from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file


PHASE32_SEMANTIC_V2_SOURCE_CENSUS_VERSION = (
    "phase32-semantic-v2-source-census-v1-no-market-outcomes"
)
PHASE32_SEMANTIC_V2_ACCEPTED_FINGERPRINT = (
    "eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566"
)
PHASE32_SEMANTIC_V2_REPORT_RELATIVE = Path(
    "strategy_evaluation/phase32/semantic_v2/phase32_8k_semantic_feasibility_v2.json"
)
PHASE32_SEMANTIC_V2_EVIDENCE_RELATIVE = Path(
    "phase32_sec_8k_semantic_feasibility/v2"
)
PHASE32_SEMANTIC_V2_CENSUS_RELATIVE = Path(
    "strategy_evaluation/phase32/semantic_v2/phase32_semantic_v2_source_census.json"
)


class Phase32SemanticSourceCensusError(RuntimeError):
    pass


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Phase32SemanticSourceCensusError(
                f"expected JSON object row in {path}"
            )
        rows.append(value)
    return rows


def _taxonomy_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("primary_category") or ""),
        str(row.get("secondary_category") or ""),
        str(row.get("tertiary_category") or ""),
    )


def _group_summary(
    keys: list[tuple[str, ...]],
    row_counts: Counter[tuple[str, ...]],
    accessions: dict[tuple[str, ...], set[str]],
    ciks: dict[tuple[str, ...], set[str]],
    windows: dict[tuple[str, ...], set[str]],
    mapped_rows: Counter[tuple[str, ...]],
    unmapped_rows: Counter[tuple[str, ...]],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for key in sorted(keys):
        result.append(
            {
                "category": list(key),
                "disclosure_rows": int(row_counts[key]),
                "unique_accessions": len(accessions[key]),
                "unique_ciks": len(ciks[key]),
                "windows_present": sorted(windows[key]),
                "ticker_mapped_rows": int(mapped_rows[key]),
                "ticker_unmapped_rows": int(unmapped_rows[key]),
            }
        )
    return result


def build_phase32_semantic_v2_source_census(settings: AtlasSettings) -> dict[str, object]:
    derived_root = settings.resolved_path(settings.data.paths.derived)
    provider_root = settings.resolved_path(settings.data.paths.provider)
    source_report_path = derived_root / PHASE32_SEMANTIC_V2_REPORT_RELATIVE
    evidence_root = provider_root / PHASE32_SEMANTIC_V2_EVIDENCE_RELATIVE

    if not source_report_path.is_file():
        raise Phase32SemanticSourceCensusError(
            f"accepted semantic V2 report not found: {source_report_path}"
        )
    source_report = json.loads(source_report_path.read_text(encoding="utf-8"))
    if not isinstance(source_report, dict):
        raise Phase32SemanticSourceCensusError("semantic V2 report is not a JSON object")
    if source_report.get("phase32_semantic_v2_fingerprint") != PHASE32_SEMANTIC_V2_ACCEPTED_FINGERPRINT:
        raise Phase32SemanticSourceCensusError("semantic V2 fingerprint mismatch")
    if source_report.get("pass") is not True:
        raise Phase32SemanticSourceCensusError("semantic V2 source gate is not PASS")
    for key in (
        "target_outcome_rows_read",
        "protected_candidate_rows_read",
        "protected_return_rows_read",
        "provider_writes",
        "broker_reads",
        "broker_writes",
        "order_writes",
        "paper_submits",
        "live_writes",
        "automation_writes",
    ):
        if int(source_report.get(key, -1)) != 0:
            raise Phase32SemanticSourceCensusError(
                f"semantic V2 zero-authority invariant violated: {key}"
            )

    taxonomy_path = evidence_root / "taxonomy.jsonl"
    if not taxonomy_path.is_file():
        raise Phase32SemanticSourceCensusError(f"taxonomy evidence missing: {taxonomy_path}")
    if sha256_file(taxonomy_path) != str(source_report.get("taxonomy_sha256") or ""):
        raise Phase32SemanticSourceCensusError("taxonomy evidence hash drifted")
    taxonomy_rows = _load_jsonl(taxonomy_path)
    taxonomy_by_key = {_taxonomy_key(row): row for row in taxonomy_rows}
    if len(taxonomy_by_key) != len(taxonomy_rows):
        raise Phase32SemanticSourceCensusError("taxonomy contains duplicate category triples")

    tertiary_counts: Counter[tuple[str, ...]] = Counter()
    tertiary_accessions: dict[tuple[str, ...], set[str]] = defaultdict(set)
    tertiary_ciks: dict[tuple[str, ...], set[str]] = defaultdict(set)
    tertiary_windows: dict[tuple[str, ...], set[str]] = defaultdict(set)
    tertiary_mapped: Counter[tuple[str, ...]] = Counter()
    tertiary_unmapped: Counter[tuple[str, ...]] = Counter()

    primary_counts: Counter[tuple[str, ...]] = Counter()
    primary_accessions: dict[tuple[str, ...], set[str]] = defaultdict(set)
    primary_ciks: dict[tuple[str, ...], set[str]] = defaultdict(set)
    primary_windows: dict[tuple[str, ...], set[str]] = defaultdict(set)
    primary_mapped: Counter[tuple[str, ...]] = Counter()
    primary_unmapped: Counter[tuple[str, ...]] = Counter()

    secondary_counts: Counter[tuple[str, ...]] = Counter()
    secondary_accessions: dict[tuple[str, ...], set[str]] = defaultdict(set)
    secondary_ciks: dict[tuple[str, ...], set[str]] = defaultdict(set)
    secondary_windows: dict[tuple[str, ...], set[str]] = defaultdict(set)
    secondary_mapped: Counter[tuple[str, ...]] = Counter()
    secondary_unmapped: Counter[tuple[str, ...]] = Counter()

    total_rows = 0
    total_mapped_rows = 0
    total_unmapped_rows = 0
    all_accessions: set[str] = set()
    all_ciks: set[str] = set()
    observed_keys: set[tuple[str, str, str]] = set()
    window_summaries: list[dict[str, object]] = []

    windows = source_report.get("windows")
    if not isinstance(windows, list) or not windows:
        raise Phase32SemanticSourceCensusError("semantic V2 report has no windows")

    for window in windows:
        if not isinstance(window, dict):
            raise Phase32SemanticSourceCensusError("semantic V2 window is not an object")
        label = str(window.get("label") or "")
        path = evidence_root / "massive_disclosures" / f"{label}.jsonl"
        if not path.is_file():
            raise Phase32SemanticSourceCensusError(f"disclosure evidence missing: {path}")
        if sha256_file(path) != str(window.get("disclosure_sha256") or ""):
            raise Phase32SemanticSourceCensusError(
                f"disclosure evidence hash drifted for {label}"
            )
        rows = _load_jsonl(path)
        if len(rows) != int(window.get("disclosure_rows", -1)):
            raise Phase32SemanticSourceCensusError(
                f"disclosure row-count mismatch for {label}"
            )

        window_accessions: set[str] = set()
        window_ciks: set[str] = set()
        window_mapped = 0
        for row in rows:
            taxonomy_key = _taxonomy_key(row)
            if taxonomy_key not in taxonomy_by_key:
                raise Phase32SemanticSourceCensusError(
                    f"observed disclosure category absent from taxonomy: {taxonomy_key}"
                )
            observed_keys.add(taxonomy_key)
            accession = str(row.get("accession_number") or "")
            cik = str(row.get("cik") or "")
            tickers = row.get("tickers") or []
            mapped = any(
                isinstance(ticker, str) and ticker.strip() for ticker in tickers
            )
            if accession:
                all_accessions.add(accession)
                window_accessions.add(accession)
            if cik:
                all_ciks.add(cik)
                window_ciks.add(cik)

            primary_key = (taxonomy_key[0],)
            secondary_key = taxonomy_key[:2]
            for group_key, counts, accession_sets, cik_sets, window_sets, mapped_counts, unmapped_counts in (
                (
                    primary_key,
                    primary_counts,
                    primary_accessions,
                    primary_ciks,
                    primary_windows,
                    primary_mapped,
                    primary_unmapped,
                ),
                (
                    secondary_key,
                    secondary_counts,
                    secondary_accessions,
                    secondary_ciks,
                    secondary_windows,
                    secondary_mapped,
                    secondary_unmapped,
                ),
                (
                    taxonomy_key,
                    tertiary_counts,
                    tertiary_accessions,
                    tertiary_ciks,
                    tertiary_windows,
                    tertiary_mapped,
                    tertiary_unmapped,
                ),
            ):
                counts[group_key] += 1
                if accession:
                    accession_sets[group_key].add(accession)
                if cik:
                    cik_sets[group_key].add(cik)
                window_sets[group_key].add(label)
                if mapped:
                    mapped_counts[group_key] += 1
                else:
                    unmapped_counts[group_key] += 1

            total_rows += 1
            if mapped:
                total_mapped_rows += 1
                window_mapped += 1
            else:
                total_unmapped_rows += 1

        window_summaries.append(
            {
                "label": label,
                "disclosure_rows": len(rows),
                "unique_accessions": len(window_accessions),
                "unique_ciks": len(window_ciks),
                "ticker_mapped_rows": window_mapped,
                "ticker_unmapped_rows": len(rows) - window_mapped,
            }
        )

    if total_rows != int(source_report.get("total_disclosure_rows", -1)):
        raise Phase32SemanticSourceCensusError(
            "total disclosure rows do not match accepted semantic V2 report"
        )

    tertiary_rows: list[dict[str, object]] = []
    for key in sorted(taxonomy_by_key):
        taxonomy_row = taxonomy_by_key[key]
        tertiary_rows.append(
            {
                "primary_category": key[0],
                "secondary_category": key[1],
                "tertiary_category": key[2],
                "taxonomy_version": str(taxonomy_row.get("taxonomy") or ""),
                "description": str(taxonomy_row.get("description") or ""),
                "observed_disclosure_rows": int(tertiary_counts[key]),
                "observed_unique_accessions": len(tertiary_accessions[key]),
                "observed_unique_ciks": len(tertiary_ciks[key]),
                "observed_windows": sorted(tertiary_windows[key]),
                "ticker_mapped_rows": int(tertiary_mapped[key]),
                "ticker_unmapped_rows": int(tertiary_unmapped[key]),
            }
        )

    census: dict[str, object] = {
        "contract_version": PHASE32_SEMANTIC_V2_SOURCE_CENSUS_VERSION,
        "accepted_semantic_v2_fingerprint": PHASE32_SEMANTIC_V2_ACCEPTED_FINGERPRINT,
        "source_report_path": str(source_report_path),
        "source_report_pass": True,
        "taxonomy_versions": list(source_report.get("taxonomy_versions") or []),
        "taxonomy_rows": len(taxonomy_rows),
        "observed_taxonomy_rows": len(observed_keys),
        "unobserved_taxonomy_rows_in_probe_windows": len(taxonomy_rows) - len(observed_keys),
        "total_disclosure_rows": total_rows,
        "unique_accessions": len(all_accessions),
        "unique_ciks": len(all_ciks),
        "ticker_mapped_rows": total_mapped_rows,
        "ticker_unmapped_rows": total_unmapped_rows,
        "windows": window_summaries,
        "primary_categories": _group_summary(
            list(primary_counts),
            primary_counts,
            primary_accessions,
            primary_ciks,
            primary_windows,
            primary_mapped,
            primary_unmapped,
        ),
        "secondary_categories": _group_summary(
            list(secondary_counts),
            secondary_counts,
            secondary_accessions,
            secondary_ciks,
            secondary_windows,
            secondary_mapped,
            secondary_unmapped,
        ),
        "taxonomy_categories": tertiary_rows,
        "target_outcome_rows_read": 0,
        "protected_candidate_rows_read": 0,
        "protected_return_rows_read": 0,
        "network_calls": 0,
        "provider_writes": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "orders": 0,
        "paper_submits": 0,
        "live_writes": 0,
    }

    output_path = derived_root / PHASE32_SEMANTIC_V2_CENSUS_RELATIVE
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output_path, json.dumps(census, indent=2, sort_keys=True) + "\n")
    census["report_path"] = str(output_path)
    return census
