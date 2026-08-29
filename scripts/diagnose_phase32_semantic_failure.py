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

    print("ATLAS Phase 32 — Semantic Source Failure Diagnostic")
    print(f"Report: {report_path}")
    print(f"Fingerprint: {report.get('phase32_semantic_feasibility_fingerprint')}")
    print(f"Pass: {report.get('pass')}")
    print(f"Failed checks: {', '.join(failed_checks) if failed_checks else 'NONE'}")
    print("Market outcomes read: 0 (diagnostic is local source evidence only)")

    failure_count = 0
    for window in report.get("windows") or []:
        if not isinstance(window, dict):
            continue
        label = str(window.get("label") or "")
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
            print()
            print(f"[{failure_count}] window={label} accession={accession}")
            print(f"  cik={sample.get('cik')} filing_date={sample.get('filing_date')}")
            print(f"  ticker_aligned={ticker_ok}")
            print(f"  disclosure_tickers={sample.get('disclosure_tickers')}")
            print(f"  index_tickers={sample.get('index_tickers')}")

            text_path = evidence_root / "massive_text" / label / f"{accession}.json"
            text_row: dict[str, Any] = {}
            if text_path.is_file():
                loaded = json.loads(text_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    text_row = loaded
            print(f"  text_ticker={text_row.get('ticker')!r}")
            print(f"  supporting_text_grounded={grounding_ok}")

            if not grounding_ok:
                disclosure_path = evidence_root / "massive_disclosures" / f"{label}.jsonl"
                disclosure_rows = _load_jsonl(disclosure_path) if disclosure_path.is_file() else []
                rows = [
                    row
                    for row in disclosure_rows
                    if str(row.get("accession_number") or "") == accession
                ]
                items_text = text_row.get("items_text")
                norm_items = _normalize(items_text)
                print(f"  items_text_length={len(str(items_text or ''))} normalized_length={len(norm_items)}")
                for idx, row in enumerate(rows, start=1):
                    supporting = row.get("supporting_text")
                    norm_support = _normalize(supporting)
                    exact_grounded = bool(norm_support) and norm_support in norm_items
                    support_tokens = set(norm_support.split())
                    item_tokens = set(norm_items.split())
                    token_coverage = (
                        len(support_tokens & item_tokens) / len(support_tokens)
                        if support_tokens
                        else 0.0
                    )
                    if exact_grounded:
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
                    print(f"    supporting_length={len(str(supporting or ''))} normalized_length={len(norm_support)}")
                    print(f"    support_token_coverage_in_items={token_coverage:.3f}")
                    print(f"    supporting_text={_clip(supporting)!r}")
                    print(f"    items_text_prefix={_clip(items_text)!r}")

    print()
    print(f"Failing sampled accessions: {failure_count}")
    print("No correction is authorized from this diagnostic alone; use the evidence above to identify the source/contract cause first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
