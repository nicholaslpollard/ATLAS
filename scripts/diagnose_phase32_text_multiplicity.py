from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase32_predictor_acquisition import PHASE32_EVIDENCE_RELATIVE
from packages.core.settings import load_settings


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"row {line_number} is not a JSON object")
        rows.append(value)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Phase32 diagnostic for multiple Massive 8-K Text rows sharing an "
            "accession/issuer/date. No network access or market outcomes are used."
        )
    )
    parser.add_argument("--accession", required=True)
    parser.add_argument("--cik", required=True)
    parser.add_argument("--filing-date", required=True)
    args = parser.parse_args()

    cik = str(args.cik).strip().zfill(10)
    accession = str(args.accession).strip()
    filing_date = str(args.filing_date).strip()

    settings = load_settings()
    provider_root = settings.resolved_path(settings.data.paths.provider)
    cache_path = (
        provider_root
        / PHASE32_EVIDENCE_RELATIVE
        / "massive_text"
        / cik
        / f"{filing_date}.jsonl"
    )

    print("ATLAS Phase32 Massive Text multiplicity diagnostic")
    print("Mode: READ-ONLY / LOCAL CACHE ONLY / NO MARKET OUTCOMES / NO NETWORK")
    print(f"Cache: {cache_path}")

    if not cache_path.is_file():
        print("Result: cache file not found")
        return 2

    rows = _load_jsonl(cache_path)
    matches = [
        row
        for row in rows
        if str(row.get("accession_number") or "").strip() == accession
        and str(row.get("cik") or "").strip().zfill(10) == cik
        and str(row.get("filing_date") or "").strip() == filing_date
    ]

    print(f"Matching rows: {len(matches)}")
    if not matches:
        print("Result: no matching cached rows")
        return 2

    for index, row in enumerate(matches, start=1):
        items_text = str(row.get("items_text") or "")
        print(f"Row {index}:")
        print(f"  ticker={row.get('ticker')!r}")
        print(f"  accession_number={row.get('accession_number')!r}")
        print(f"  cik={row.get('cik')!r}")
        print(f"  filing_date={row.get('filing_date')!r}")
        print(f"  form_type={row.get('form_type')!r}")
        print(f"  filing_url={row.get('filing_url')!r}")
        print(f"  items_text_length={len(items_text)}")
        print(f"  items_text_sha256={_sha256_text(items_text)}")
        print(f"  canonical_row_sha256={_sha256_text(_canonical_json(row))}")

    fields = sorted({key for row in matches for key in row})
    differing_fields = [
        field
        for field in fields
        if len({_canonical_json(row.get(field)) for row in matches}) > 1
    ]
    non_ticker_differing_fields = [field for field in differing_fields if field != "ticker"]

    print("Comparison:")
    print(f"  tickers={sorted({str(row.get('ticker') or '') for row in matches})}")
    print(f"  differing_fields={differing_fields}")
    print(f"  non_ticker_differing_fields={non_ticker_differing_fields}")
    print(
        "  identical_items_text="
        f"{len({_sha256_text(str(row.get('items_text') or '')) for row in matches}) == 1}"
    )
    print(
        "  identical_filing_url="
        f"{len({str(row.get('filing_url') or '') for row in matches}) == 1}"
    )
    print(
        "  identical_non_ticker_record="
        f"{len({_canonical_json({k: v for k, v in row.items() if k != 'ticker'}) for row in matches}) == 1}"
    )
    print("Result: diagnostic complete; no files were modified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
