from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase32_predictor_acquisition import PHASE32_EVIDENCE_RELATIVE
from packages.core.settings import load_settings
from packages.providers.sec_edgar import SECEDGARClient, sec_company_submissions_url


TARGET_ACCESSION = "0001564708-23-000471"
TARGET_FILING_DATE = date(2023, 10, 5)


def _normalize_cik(value: object) -> str | None:
    text = str(value or "").strip()
    if not text.isdigit():
        return None
    return str(int(text)).zfill(10)


def _read_matching_jsonl(directory: Path) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    if not directory.is_dir():
        return matches
    for path in sorted(directory.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict) and str(row.get("accession_number") or "").strip() == TARGET_ACCESSION:
                matches.append(row)
    return matches


def _recent_rows(recent: object) -> list[dict[str, object]]:
    if not isinstance(recent, dict):
        return []
    accessions = recent.get("accessionNumber")
    if not isinstance(accessions, list):
        return []
    fields = (
        "accessionNumber",
        "filingDate",
        "acceptanceDateTime",
        "form",
        "items",
        "primaryDocument",
    )
    rows: list[dict[str, object]] = []
    for index in range(len(accessions)):
        row: dict[str, object] = {}
        for field in fields:
            values = recent.get(field)
            row[field] = values[index] if isinstance(values, list) and index < len(values) else ""
        rows.append(row)
    return rows


def _range_distance(item: dict[str, object]) -> tuple[int, str]:
    start_text = str(item.get("filingFrom") or "")
    end_text = str(item.get("filingTo") or "")
    try:
        start = date.fromisoformat(start_text)
        end = date.fromisoformat(end_text)
    except ValueError:
        return (10**9, str(item.get("name") or ""))
    if start <= TARGET_FILING_DATE <= end:
        distance = 0
    elif TARGET_FILING_DATE < start:
        distance = (start - TARGET_FILING_DATE).days
    else:
        distance = (TARGET_FILING_DATE - end).days
    return (distance, str(item.get("name") or ""))


def _compact_source_row(row: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "accession_number",
        "cik",
        "filing_date",
        "form_type",
        "ticker",
        "tickers",
        "primary_category",
        "secondary_category",
        "tertiary_category",
        "filing_url",
    )
    return {key: row.get(key) for key in keys if key in row}


def _inspect_sec_root(client: SECEDGARClient, cik: str, *, role: str) -> dict[str, Any]:
    url = sec_company_submissions_url(cik=cik)
    root, _ = client.get_json(url)
    filings = root.get("filings") if isinstance(root, dict) else None
    if not isinstance(filings, dict):
        raise RuntimeError(f"SEC root for CIK {cik} is missing filings object")

    recent_rows = _recent_rows(filings.get("recent"))
    exact_recent = [
        row
        for row in recent_rows
        if str(row.get("accessionNumber") or "").strip() == TARGET_ACCESSION
    ]
    recent_dates = sorted(
        str(row.get("filingDate") or "")
        for row in recent_rows
        if str(row.get("filingDate") or "").strip()
    )

    files_raw = filings.get("files")
    declared_files = [dict(item) for item in files_raw if isinstance(item, dict)] if isinstance(files_raw, list) else []
    covering = [
        item
        for item in declared_files
        if str(item.get("filingFrom") or "")
        and str(item.get("filingTo") or "")
        and str(item.get("filingFrom")) <= TARGET_FILING_DATE.isoformat() <= str(item.get("filingTo"))
    ]
    nearest = sorted(declared_files, key=_range_distance)[:5]

    print()
    print(f"SEC root inspection — {role}: CIK {cik}")
    print(f"URL: {url}")
    print(f"Name: {root.get('name')!r}")
    print(f"Entity type: {root.get('entityType')!r}")
    print(f"Exact accession in filings.recent: {bool(exact_recent)}")
    if exact_recent:
        for row in exact_recent:
            print(f"  recent row: {json.dumps(row, sort_keys=True, ensure_ascii=False)}")
    if recent_dates:
        print(f"Recent filing-date span: {recent_dates[0]} .. {recent_dates[-1]}")
    else:
        print("Recent filing-date span: none")
    print(f"Declared historical shard files: {len(declared_files)}")
    print(f"Declared shards covering {TARGET_FILING_DATE}: {len(covering)}")
    for item in covering:
        print(
            "  covering: "
            f"{item.get('name')} {item.get('filingFrom')}..{item.get('filingTo')}"
        )
    print("Nearest declared shard ranges:")
    for item in nearest:
        print(
            "  nearest: "
            f"{item.get('name')} {item.get('filingFrom')}..{item.get('filingTo')} "
            f"distance_days={_range_distance(item)[0]}"
        )

    return {
        "role": role,
        "cik": cik,
        "exact_recent": bool(exact_recent),
        "covering_shards": len(covering),
    }


def main() -> int:
    settings = load_settings()
    provider_root = settings.resolved_path(settings.data.paths.provider)
    evidence_root = provider_root / PHASE32_EVIDENCE_RELATIVE

    print("ATLAS Phase 32 — SEC Submissions Coverage-Gap Diagnostic")
    print(f"Target accession: {TARGET_ACCESSION}")
    print(f"Target filing date: {TARGET_FILING_DATE}")
    print(f"Evidence root: {evidence_root}")
    print("Scope: local source lineage + official SEC submissions metadata only")
    print("Stock/SPY/options outcomes / broker / orders / PAPER / LIVE: FORBIDDEN / DISABLED")

    index_rows = _read_matching_jsonl(evidence_root / "massive_index")
    disclosure_rows = _read_matching_jsonl(evidence_root / "massive_disclosures")

    print()
    print(f"Local Massive index matches: {len(index_rows)}")
    for row in index_rows:
        print(f"  {json.dumps(_compact_source_row(row), sort_keys=True, ensure_ascii=False)}")
    print(f"Local Massive disclosure matches: {len(disclosure_rows)}")
    for row in disclosure_rows:
        print(f"  {json.dumps(_compact_source_row(row), sort_keys=True, ensure_ascii=False)}")

    issuer_ciks = sorted(
        {
            cik
            for row in disclosure_rows + index_rows
            for cik in [_normalize_cik(row.get("cik"))]
            if cik is not None
        }
    )
    accession_owner_cik = TARGET_ACCESSION[:10]
    print(f"Observed filing CIKs from local source rows: {issuer_ciks}")
    print(f"Accession-owner CIK encoded in accession: {accession_owner_cik}")

    if not issuer_ciks:
        print("Result: LOCAL_SOURCE_LINEAGE_MISSING")
        print("No local source row for the target accession was found; stop and diagnose acquisition cache lineage.")
        return 2

    client = SECEDGARClient()
    results: list[dict[str, Any]] = []
    for cik in issuer_ciks:
        results.append(_inspect_sec_root(client, cik, role="observed filing CIK"))
    if accession_owner_cik not in issuer_ciks:
        results.append(_inspect_sec_root(client, accession_owner_cik, role="accession-owner diagnostic CIK"))

    observed_results = [row for row in results if row["role"] == "observed filing CIK"]
    if any(row["exact_recent"] or row["covering_shards"] for row in observed_results):
        print()
        print("Result: SEC_COVERAGE_PRESENT_FOR_AT_LEAST_ONE_OBSERVED_CIK")
        print(
            "The official root metadata exposes a recent exact accession or a date-covering shard for at least "
            "one observed filing CIK. Compare this with the acquisition-selected issuer CIK before changing logic."
        )
        return 0

    owner_result = next((row for row in results if row["cik"] == accession_owner_cik), None)
    print()
    if owner_result and owner_result["exact_recent"]:
        print("Result: ACCESSION_OWNER_HAS_EXACT_RECENT_BUT_OBSERVED_CIK_ROOTS_DO_NOT_COVER_DATE")
        print(
            "This points to a filing-entity / SEC-submissions issuer-scope distinction, not a missing filing. "
            "Do not broaden the source rule yet; use this evidence to repair the exact reconciliation invariant."
        )
    elif owner_result and owner_result["covering_shards"]:
        print("Result: ACCESSION_OWNER_HAS_DATE_COVERAGE_BUT_OBSERVED_CIK_ROOTS_DO_NOT")
        print(
            "This points to a filing-entity / SEC-submissions issuer-scope distinction. Do not broaden the "
            "source rule until the accession-owner shard is inspected under a bounded diagnostic."
        )
    else:
        print("Result: SEC_ROOT_METADATA_HAS_NO_DECLARED_COVERAGE_FOR_TARGET_DATE")
        print(
            "Neither observed filing-CIK roots nor the accession-owner diagnostic root expose the target accession "
            "in recent metadata or a declared historical shard covering the filing date. Diagnose SEC root/shard "
            "metadata semantics before changing the accepted source contract."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
