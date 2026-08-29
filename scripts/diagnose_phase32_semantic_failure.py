from __future__ import annotations

import json
import re
import sys
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
    text = str(value or "").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _clip(value: object, limit: int = 360) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "..."


def _ordered_subsequence_coverage(needle: str, haystack: str) -> float:
    needle_tokens = needle.split()
    haystack_tokens = haystack.split()
    if not needle_tokens:
        return 0.0
    matched = 0
    position = 0
    for token in needle_tokens:
        while position < len(haystack_tokens) and haystack_tokens[position] != token:
            position += 1
        if position >= len(haystack_tokens):
            break
        matched += 1
        position += 1
    return matched / len(needle_tokens)


def _ticker_relation(
    disclosure_tickers: set[str], index_tickers: set[str], text_ticker: str | None
) -> str:
    if not disclosure_tickers and not index_tickers and not text_ticker:
        return "ALL_UNMAPPED"
    if disclosure_tickers & index_tickers:
        return "DISCLOSURE_INDEX_OVERLAP"
    if text_ticker and text_ticker in disclosure_tickers and index_tickers:
        return "DISCLOSURE_TEXT_AGREE_INDEX_DIFFERS"
    if text_ticker and text_ticker in disclosure_tickers and not index_tickers:
        return "DISCLOSURE_TEXT_AGREE_INDEX_UNMAPPED"
    if not disclosure_tickers and not text_ticker and index_tickers:
        return "INDEX_ONLY_MAPPING"
    if disclosure_tickers and not index_tickers and not text_ticker:
        return "DISCLOSURE_ONLY_MAPPING"
    return "MIXED_MAPPING"


def main() -> int:
    settings = load_settings()
    derived_root = settings.resolved_path(settings.data.paths.derived)
    provider_root = settings.resolved_path(settings.data.paths.provider)
    report_path = derived_root / REPORT_RELATIVE
    evidence_root = provider_root / EVIDENCE_RELATIVE

    if not report_path.is_file():
        print(f"Phase32 semantic diagnostic: report not found: {report_path}")
        return 2

    report = json.loads(report_path.read_text(encoding="utf-8"))
    checks = report.get("checks") or {}
    failed_checks = [name for name, passed in checks.items() if not passed]

    print("ATLAS Phase 32 — Semantic Source Failure Diagnostic V2")
    print(f"Report: {report_path}")
    print(f"Fingerprint: {report.get('phase32_semantic_feasibility_fingerprint')}")
    print(f"Pass: {report.get('pass')}")
    print(f"Failed checks: {', '.join(failed_checks) if failed_checks else 'NONE'}")
    print("Market outcomes read: 0 (diagnostic is local source evidence only)")
    print()
    print("WINDOW COVERAGE FROM RETAINED V1 EVIDENCE")
    for window in report.get("windows") or []:
        if not isinstance(window, dict):
            continue
        print(
            "  %s %s..%s: index=%s disclosures=%s overlap=%s samples=%s v1_covered_flag=%s"
            % (
                window.get("label"),
                window.get("start_date"),
                window.get("end_date"),
                window.get("index_rows"),
                window.get("disclosure_rows"),
                window.get("original_8k_overlap_rows"),
                len(window.get("sampled_accessions") or []),
                window.get("covered_by_safe_history"),
            )
        )

    failure_count = 0
    relation_counts: dict[str, int] = {}
    ordered_coverages: list[float] = []

    for window in report.get("windows") or []:
        if not isinstance(window, dict):
            continue
        label = str(window.get("label") or "")
        disclosure_path = evidence_root / "massive_disclosures" / f"{label}.jsonl"
        index_path = evidence_root / "massive_index" / f"{label}.jsonl"
        disclosure_rows_all = _load_jsonl(disclosure_path) if disclosure_path.is_file() else []
        index_rows_all = _load_jsonl(index_path) if index_path.is_file() else []

        samples = window.get("sample_reports") or []
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            ticker_ok = bool(sample.get("ticker_aligned"))
            grounding_ok = bool(sample.get("supporting_text_grounded_in_items_text"))
            if ticker_ok and grounding_ok:
                continue

            failure_count += 1
            accession = str(sample.get("accession_number") or "")
            disclosure_rows = [
                row
                for row in disclosure_rows_all
                if str(row.get("accession_number") or "") == accession
            ]
            index_rows = [
                row
                for row in index_rows_all
                if str(row.get("accession_number") or "") == accession
            ]

            text_path = evidence_root / "massive_text" / label / f"{accession}.json"
            text_row: dict[str, Any] = {}
            if text_path.is_file():
                loaded = json.loads(text_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    text_row = loaded

            disclosure_tickers = {
                str(ticker)
                for row in disclosure_rows
                for ticker in (row.get("tickers") or [])
                if isinstance(ticker, str) and ticker.strip()
            }
            index_tickers = {
                str(row.get("ticker"))
                for row in index_rows
                if isinstance(row.get("ticker"), str) and str(row.get("ticker")).strip()
            }
            text_ticker_value = text_row.get("ticker")
            text_ticker = (
                str(text_ticker_value)
                if isinstance(text_ticker_value, str) and text_ticker_value.strip()
                else None
            )
            relation = _ticker_relation(disclosure_tickers, index_tickers, text_ticker)
            relation_counts[relation] = relation_counts.get(relation, 0) + 1

            disclosure_ciks = {
                str(row.get("cik") or "") for row in disclosure_rows if row.get("cik") is not None
            }
            index_ciks = {
                str(row.get("cik") or "") for row in index_rows if row.get("cik") is not None
            }
            text_cik = str(text_row.get("cik") or "")
            sample_cik = str(sample.get("cik") or "")
            cik_values = {value.zfill(10) for value in disclosure_ciks | index_ciks | {text_cik, sample_cik} if value}

            print()
            print(f"[{failure_count}] window={label} accession={accession}")
            print(f"  cik={sample.get('cik')} filing_date={sample.get('filing_date')}")
            print(f"  cik_identity_values={sorted(cik_values)} exact_cik_identity={len(cik_values) == 1}")
            print(f"  sec_reconciled={sample.get('sec_accession_form_filing_date_acceptance_reconciled')}")
            print(f"  ticker_aligned_v1={ticker_ok}")
            print(f"  disclosure_tickers={sorted(disclosure_tickers)}")
            print(f"  index_tickers={sorted(index_tickers)}")
            print(f"  text_ticker={text_ticker!r}")
            print(f"  ticker_relation={relation}")
            print(f"  supporting_text_grounded_v1={grounding_ok}")

            if not grounding_ok:
                items_text = text_row.get("items_text")
                norm_items = _normalize(items_text)
                print(
                    f"  items_text_length={len(str(items_text or ''))} "
                    f"normalized_length={len(norm_items)}"
                )
                for idx, row in enumerate(disclosure_rows, start=1):
                    supporting = row.get("supporting_text")
                    norm_support = _normalize(supporting)
                    exact_grounded = bool(norm_support) and norm_support in norm_items
                    support_token_set = set(norm_support.split())
                    item_token_set = set(norm_items.split())
                    token_coverage = (
                        len(support_token_set & item_token_set) / len(support_token_set)
                        if support_token_set
                        else 0.0
                    )
                    ordered_coverage = _ordered_subsequence_coverage(norm_support, norm_items)
                    if not exact_grounded:
                        ordered_coverages.append(ordered_coverage)
                    else:
                        continue
                    print(
                        "  disclosure[%d] category=%s/%s/%s"
                        % (
                            idx,
                            row.get("primary_category"),
                            row.get("secondary_category"),
                            row.get("tertiary_category"),
                        )
                    )
                    print(
                        f"    supporting_length={len(str(supporting or ''))} "
                        f"normalized_length={len(norm_support)}"
                    )
                    print(f"    support_unique_token_coverage_in_items={token_coverage:.3f}")
                    print(f"    support_ordered_token_coverage_in_items={ordered_coverage:.3f}")
                    print(f"    supporting_text={_clip(supporting)!r}")
                    print(f"    items_text_prefix={_clip(items_text)!r}")

    print()
    print("DIAGNOSTIC SUMMARY")
    print(f"  failing_sampled_accessions={failure_count}")
    for relation, count in sorted(relation_counts.items()):
        print(f"  ticker_relation[{relation}]={count}")
    if ordered_coverages:
        print(f"  nonexact_support_rows={len(ordered_coverages)}")
        print(f"  min_ordered_token_coverage={min(ordered_coverages):.3f}")
        print(f"  mean_ordered_token_coverage={sum(ordered_coverages) / len(ordered_coverages):.3f}")
        print(f"  full_ordered_subsequence_rows={sum(value == 1.0 for value in ordered_coverages)}")
    print(
        "No correction is authorized from this diagnostic alone. This output is intended to "
        "separate source-scope, ticker-mapping, and history-coverage causes before V2 is frozen."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
