from __future__ import annotations

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


TARGET_ACCESSION = "0000003545-23-000037"
TARGET_CIK = "0000003545"
TARGET_FILING_DATE = "2023-12-14"
TARGET_KEY = f"{TARGET_ACCESSION}|{TARGET_CIK}|{TARGET_FILING_DATE}"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value: object, *, newline: bool) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text + ("\n" if newline else "")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON artifact is not an object: {path}")
    return value


def _find_filing_entity(path: Path) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise RuntimeError(f"filing-entity row is not an object: {path}:{line_number}")
        if value.get("filing_entity_key") == TARGET_KEY:
            matches.append(value)
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one target filing-entity row, found {len(matches)}")
    return matches[0]


def main() -> int:
    settings = load_settings()
    provider_root = settings.resolved_path(settings.data.paths.provider)
    evidence_root = provider_root / PHASE32_EVIDENCE_RELATIVE
    sec_path = evidence_root / "sec_submissions" / TARGET_CIK / f"{TARGET_ACCESSION}.json"
    filing_entity_path = evidence_root / "candidate_filing_entity_records.jsonl"

    print("ATLAS Phase 32 — Read-Only SEC Source-Record Hash Diagnostic")
    print(f"Target filing entity: {TARGET_KEY}")
    print(f"SEC cache: {sec_path}")
    print(f"Filing-entity evidence: {filing_entity_path}")
    print("Scope: local cached SEC record + frozen filing-entity evidence only")
    print("Network / market outcomes / broker / orders / PAPER / LIVE: FORBIDDEN / DISABLED")
    print()

    sec = _load_json(sec_path)
    entity = _find_filing_entity(filing_entity_path)

    source_record_json = sec.get("source_record_json")
    if not isinstance(source_record_json, str):
        raise RuntimeError("SEC cache source_record_json is not a string")
    stored_sha = str(sec.get("source_record_sha256") or "")
    entity_sha = str(entity.get("sec_source_record_sha256") or "")
    exact_sha = _sha256_text(source_record_json)

    print(f"Stored SEC source_record_sha256: {stored_sha}")
    print(f"Filing-entity sec_source_record_sha256: {entity_sha}")
    print(f"SHA-256 of exact cached source_record_json string: {exact_sha}")
    print(f"source_record_json characters: {len(source_record_json)}")
    print(f"source_record_json UTF-8 bytes: {len(source_record_json.encode('utf-8'))}")
    print(f"ends_with_LF: {source_record_json.endswith(chr(10))}")
    print(f"ends_with_CRLF: {source_record_json.endswith(chr(13) + chr(10))}")
    print(f"trailing_newline_count: {len(source_record_json) - len(source_record_json.rstrip(chr(10) + chr(13)))}")
    print(f"source_record_json repr: {source_record_json!r}")
    print()

    try:
        parsed = json.loads(source_record_json)
    except json.JSONDecodeError as exc:
        print(f"source_record_json parse: FAIL: {exc}")
        return 2
    if not isinstance(parsed, dict):
        print("source_record_json parse: FAIL: parsed value is not an object")
        return 2

    canonical_no_newline = _canonical_json(parsed, newline=False)
    canonical_with_newline = _canonical_json(parsed, newline=True)
    canonical_no_newline_sha = _sha256_text(canonical_no_newline)
    canonical_with_newline_sha = _sha256_text(canonical_with_newline)
    raw_outer_reconstruction = {
        "accessionNumber": sec.get("accession_number"),
        "issuerCIK": sec.get("issuer_cik"),
        "filingDate": sec.get("filing_date"),
        "acceptanceDateTime": parsed.get("acceptanceDateTime"),
        "form": sec.get("form"),
        "items": parsed.get("items"),
        "primaryDocument": sec.get("primary_document"),
        "sourceUrl": sec.get("source_url"),
    }
    reconstructed_with_newline = _canonical_json(raw_outer_reconstruction, newline=True)
    reconstructed_sha = _sha256_text(reconstructed_with_newline)

    print("Canonical variants:")
    print(f"- parsed canonical, no newline: {canonical_no_newline_sha}")
    print(f"- parsed canonical, one LF:     {canonical_with_newline_sha}")
    print(f"- reconstructed outer fields:   {reconstructed_sha}")
    print(f"- exact string equals canonical no-newline: {source_record_json == canonical_no_newline}")
    print(f"- exact string equals canonical one-LF:     {source_record_json == canonical_with_newline}")
    print(f"- parsed object equals outer reconstruction: {parsed == raw_outer_reconstruction}")
    print()

    print("SEC outer record fields:")
    for field in (
        "accession_number",
        "issuer_cik",
        "filing_date",
        "acceptance_datetime",
        "form",
        "item_codes",
        "primary_document",
        "source_url",
    ):
        print(f"- {field}: {sec.get(field)!r}")
    print()

    print("Parsed source_record_json fields:")
    for field in sorted(parsed):
        print(f"- {field}: {parsed.get(field)!r}")
    print()

    matches: list[str] = []
    if stored_sha == exact_sha:
        matches.append("exact_cached_string")
    if stored_sha == canonical_no_newline_sha:
        matches.append("canonical_without_newline")
    if stored_sha == canonical_with_newline_sha:
        matches.append("canonical_with_one_LF")
    if stored_sha == reconstructed_sha:
        matches.append("outer_field_reconstruction")

    print(f"Stored SHA matches variants: {matches if matches else 'NONE'}")
    print(f"Filing-entity SHA equals stored SEC SHA: {entity_sha == stored_sha}")
    print(f"Filing-entity SHA equals exact cached-string SHA: {entity_sha == exact_sha}")

    if stored_sha == exact_sha and entity_sha == exact_sha:
        print("Result: TARGET_HASH_IS_INTERNALLY_CONSISTENT")
    elif entity_sha == stored_sha and stored_sha != exact_sha:
        print("Result: STALE_OR_INCONSISTENT_SEC_CACHE_HASH_PROPAGATED_INTO_FILING_EVIDENCE")
    elif entity_sha != stored_sha:
        print("Result: FILING_ENTITY_SEC_HASH_DIFFERS_FROM_CURRENT_SEC_CACHE")
    else:
        print("Result: UNCLASSIFIED_SEC_SOURCE_HASH_MISMATCH")
    print("No files were modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
