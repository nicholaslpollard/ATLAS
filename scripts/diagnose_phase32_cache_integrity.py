from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase32_predictor_acquisition import PHASE32_EVIDENCE_RELATIVE
from packages.core.settings import load_settings


def main() -> int:
    settings = load_settings()
    provider_root = settings.resolved_path(settings.data.paths.provider)
    evidence_root = provider_root / PHASE32_EVIDENCE_RELATIVE

    print("ATLAS Phase 32 — Read-Only Cache Integrity Diagnostic")
    print(f"Evidence root: {evidence_root}")
    print("Scope: local cache parse/integrity only; no network, outcomes, broker, or trading access")
    print()

    if not evidence_root.is_dir():
        print("Result: NOT DIAGNOSABLE")
        print("Reason: Phase32 evidence root does not exist")
        return 2

    json_files = sorted(evidence_root.rglob("*.json"))
    jsonl_files = sorted(evidence_root.rglob("*.jsonl"))
    temp_files = sorted(evidence_root.rglob("*.tmp"))

    problems: list[tuple[Path, str]] = []
    empty_json_files: list[Path] = []
    parsed_json = 0
    parsed_jsonl = 0
    jsonl_rows = 0

    for path in json_files:
        try:
            text = path.read_text(encoding="utf-8")
            if not text.strip():
                empty_json_files.append(path)
                problems.append((path, "empty JSON file"))
                continue
            value = json.loads(text)
            if not isinstance(value, dict):
                problems.append((path, f"JSON root is {type(value).__name__}, expected object"))
                continue
            parsed_json += 1
        except Exception as exc:  # diagnostic must surface exact local path/error
            problems.append((path, f"{type(exc).__name__}: {exc}"))

    for path in jsonl_files:
        try:
            rows = 0
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(
                        f"line {line_number} root is {type(value).__name__}, expected object"
                    )
                rows += 1
            parsed_jsonl += 1
            jsonl_rows += rows
        except Exception as exc:  # diagnostic must surface exact local path/error
            problems.append((path, f"{type(exc).__name__}: {exc}"))

    print(f"JSON files scanned: {len(json_files)}")
    print(f"Valid JSON files: {parsed_json}")
    print(f"JSONL files scanned: {len(jsonl_files)}")
    print(f"Valid JSONL files: {parsed_jsonl}")
    print(f"JSONL rows parsed: {jsonl_rows}")
    print(f"Stale sibling temp files observed: {len(temp_files)}")
    print(f"Integrity problems: {len(problems)}")

    if temp_files:
        print("\nStale temp files (read-only observation):")
        for path in temp_files[:20]:
            print(f"- {path} ({path.stat().st_size} bytes)")
        if len(temp_files) > 20:
            print(f"- ... {len(temp_files) - 20} more")

    if problems:
        print("\nMalformed/invalid cache files:")
        for path, reason in problems[:50]:
            try:
                size = path.stat().st_size
            except OSError:
                size = -1
            print(f"- {path} ({size} bytes): {reason}")
        if len(problems) > 50:
            print(f"- ... {len(problems) - 50} more")
        print("\nResult: CACHE_INTEGRITY_FAIL")
        print(
            "Do not delete or rewrite anything yet. Return this output so the exact corruption "
            "can be tied to the crash and repaired without weakening source or scientific rules."
        )
        return 1

    print("\nResult: CACHE_PARSE_INTEGRITY_PASS")
    print(
        "No malformed local JSON/JSONL cache was found. The JSON decode failure must then be "
        "localized to a non-cache parse path before the acquisition is rerun."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
