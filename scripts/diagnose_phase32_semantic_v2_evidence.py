from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings


REPORT_RELATIVE = Path(
    "strategy_evaluation/phase32/semantic_v1/phase32_8k_semantic_feasibility.json"
)
EVIDENCE_RELATIVE = Path("phase32_sec_8k_semantic_feasibility/v1")


def _normalize(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _tokens(value: object) -> list[str]:
    return _normalize(value).split()


def _ordered_coverage(needle: list[str], haystack: list[str]) -> float:
    if not needle:
        return 0.0
    cursor = 0
    matched = 0
    for token in haystack:
        if cursor < len(needle) and token == needle[cursor]:
            cursor += 1
            matched += 1
    return matched / len(needle)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _sample_accessions(rows: list[dict[str, Any]], index_accessions: set[str], limit: int = 6) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for row in rows:
        accession = str(row.get("accession_number") or "")
        if accession and accession in index_accessions and accession not in seen:
            seen.add(accession)
            ordered.append(accession)
    if len(ordered) <= limit:
        return ordered
    half = limit // 2
    return ordered[:half] + ordered[-half:]


def main() -> int:
    settings = load_settings()
    derived_root = settings.resolved_path(settings.data.paths.derived)
    provider_root = settings.resolved_path(settings.data.paths.provider)
    report_path = derived_root / REPORT_RELATIVE
    evidence_root = provider_root / EVIDENCE_RELATIVE

    if not report_path.is_file():
        print(f"report not found: {report_path}")
        return 2

    report = json.loads(report_path.read_text(encoding="utf-8"))
    print("ATLAS Phase 32 — Semantic V2 Evidence Diagnostic")
    print(f"Source V1 fingerprint: {report.get('phase32_semantic_feasibility_fingerprint')}")
    print("Market outcomes read: 0")
    print()

    taxonomy_path = evidence_root / "taxonomy.jsonl"
    taxonomy_rows = _load_jsonl(taxonomy_path)
    taxonomy_keys = {
        (
            str(row.get("primary_category") or ""),
            str(row.get("secondary_category") or ""),
            str(row.get("tertiary_category") or ""),
        )
        for row in taxonomy_rows
    }
    print(f"taxonomy_rows={len(taxonomy_rows)} taxonomy_keys={len(taxonomy_keys)}")

    total_sampled = 0
    exact_cik = 0
    exact_taxonomy = 0
    nonblank_support = 0
    full_ordered_support = 0
    ticker_classes: Counter[str] = Counter()

    for window in report.get("windows") or []:
        if not isinstance(window, dict):
            continue
        label = str(window.get("label") or "")
        index_rows = _load_jsonl(evidence_root / "massive_index" / f"{label}.jsonl")
        disclosure_rows = _load_jsonl(evidence_root / "massive_disclosures" / f"{label}.jsonl")
        index_by_accession: dict[str, list[dict[str, Any]]] = {}
        for row in index_rows:
            accession = str(row.get("accession_number") or "")
            if accession:
                index_by_accession.setdefault(accession, []).append(row)
        samples = _sample_accessions(disclosure_rows, set(index_by_accession))
        print(
            f"window={label} index={len(index_rows)} disclosures={len(disclosure_rows)} "
            f"overlap={sum(1 for r in disclosure_rows if str(r.get('accession_number') or '') in index_by_accession)} "
            f"v2_samples={len(samples)}"
        )
        for accession in samples:
            total_sampled += 1
            drows = [r for r in disclosure_rows if str(r.get("accession_number") or "") == accession]
            irows = index_by_accession.get(accession, [])
            ciks = {str(r.get("cik") or "").zfill(10) for r in drows + irows if str(r.get("cik") or "").strip()}
            cik_ok = len(ciks) == 1
            exact_cik += int(cik_ok)
            taxonomy_ok = all(
                (
                    str(r.get("primary_category") or ""),
                    str(r.get("secondary_category") or ""),
                    str(r.get("tertiary_category") or ""),
                ) in taxonomy_keys
                for r in drows
            )
            exact_taxonomy += int(taxonomy_ok)
            support_ok = all(bool(_normalize(r.get("supporting_text"))) for r in drows)
            nonblank_support += int(support_ok)

            text_path = evidence_root / "massive_text" / label / f"{accession}.json"
            text_row: dict[str, Any] = {}
            if text_path.is_file():
                value = json.loads(text_path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    text_row = value
            ordered_rows = []
            for r in drows:
                support_tokens = _tokens(r.get("supporting_text"))
                item_tokens = _tokens(text_row.get("items_text"))
                ordered_rows.append(_ordered_coverage(support_tokens, item_tokens))
            ordered_ok = bool(ordered_rows) and all(v == 1.0 for v in ordered_rows)
            full_ordered_support += int(ordered_ok)

            dtickers = {str(t) for r in drows for t in (r.get("tickers") or []) if isinstance(t, str) and t.strip()}
            itickers = {str(r.get("ticker")) for r in irows if isinstance(r.get("ticker"), str) and str(r.get("ticker")).strip()}
            tticker = text_row.get("ticker") if isinstance(text_row.get("ticker"), str) and str(text_row.get("ticker")).strip() else None
            if not dtickers and not itickers and tticker is None:
                tclass = "ALL_UNMAPPED"
            elif dtickers & itickers:
                tclass = "DISCLOSURE_INDEX_OVERLAP"
            elif tticker is not None and tticker in dtickers:
                tclass = "DISCLOSURE_TEXT_AGREE_INDEX_DIFFERS"
            elif tticker is not None and tticker in itickers:
                tclass = "INDEX_TEXT_AGREE_DISCLOSURE_DIFFERS"
            else:
                tclass = "OTHER_MAPPED_DISAGREEMENT"
            ticker_classes[tclass] += 1
            print(
                f"  {accession} cik_ok={cik_ok} taxonomy_ok={taxonomy_ok} support_nonblank={support_ok} "
                f"ordered_all_1={ordered_ok} ticker_relation={tclass}"
            )

    print()
    print("SUMMARY")
    print(f"total_sampled_accessions={total_sampled}")
    print(f"exact_cik_identity={exact_cik}/{total_sampled}")
    print(f"taxonomy_membership={exact_taxonomy}/{total_sampled}")
    print(f"nonblank_supporting_text={nonblank_support}/{total_sampled}")
    print(f"all_support_rows_full_ordered_subsequence_of_items_text={full_ordered_support}/{total_sampled}")
    for key in sorted(ticker_classes):
        print(f"ticker_relation[{key}]={ticker_classes[key]}")
    print("This diagnostic is source-only and grants no alpha/trading authority.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
