from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.recurrent_successor_dynamic_exit_v1_contract import (
    RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT_FINGERPRINT,
)


RUN_FINGERPRINT = "560b35765e82b2ab5fb59f8b00cc641f28112232bf89a994fdb0637f069a2b5b"


def read_closeout(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("summary must be a JSON object")
    if payload.get("status") != "COMPLETE_DYNAMIC_EXIT_V1_SELECTOR_DIAGNOSTIC":
        raise ValueError("unexpected dynamic-exit status")
    if payload.get("contract_fingerprint") != RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT_FINGERPRINT:
        raise ValueError("dynamic-exit contract fingerprint drifted")
    if payload.get("run_fingerprint") != RUN_FINGERPRINT:
        raise ValueError("dynamic-exit run fingerprint drifted")
    expected = payload.get("report_fingerprint")
    unsealed = dict(payload)
    unsealed.pop("report_fingerprint", None)
    observed = hashlib.sha256(
        json.dumps(unsealed, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    if expected != observed:
        raise ValueError("dynamic-exit report fingerprint does not match")
    if int(payload["selected_cases"]) + int(payload["abstained_cases"]) != int(payload["usable_cases"]):
        raise ValueError("selected + abstained does not reconcile to usable cases")
    reasons = payload.get("abstain_reasons")
    if not isinstance(reasons, dict) or sum(int(x) for x in reasons.values()) != int(payload["abstained_cases"]):
        raise ValueError("abstain reasons do not reconcile")
    years = payload.get("year_summary")
    if not isinstance(years, list) or sum(int(x["cases"]) for x in years) != int(payload["usable_cases"]):
        raise ValueError("yearly case counts do not reconcile")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read only the retained Dynamic Exit V1 report; no replay or provider calls."
    )
    default = (
        PROJECT_ROOT / "data/research/recurrent_successor_dynamic_exit_v1"
        / RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT_FINGERPRINT[:16]
        / RUN_FINGERPRINT[:16] / "dynamic_exit_v1_summary.json"
    )
    parser.add_argument("--report", type=Path, default=default)
    args = parser.parse_args(argv)
    try:
        report = read_closeout(args.report)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"READ-ONLY CLOSEOUT BLOCKED: {exc}")
        return 3

    print("ATLAS Dynamic Exit V1 — Retained Report Closeout")
    print(f"  report: {args.report}")
    print(f"  run fingerprint: {RUN_FINGERPRINT}")
    print(f"  report fingerprint: {report['report_fingerprint']}")
    print(f"  selected / usable: {report['selected_cases']:,} / {report['usable_cases']:,}")
    print(f"  abstained: {report['abstained_cases']:,}")
    print("  abstain reasons:")
    for reason, count in sorted(report["abstain_reasons"].items()):
        print(f"    {reason}: {count:,}")
    print("  selected fallback levels:")
    for level, count in sorted(report["selected_fallback_level_counts"].items()):
        print(f"    level {level}: {count:,}")
    print("  annual abstention causes:")
    for item in report["year_summary"]:
        print(f"    {item['year']}: {item['abstain_reasons']}")
    print("  provider reads: 0; stock-source scans: 0; portfolio return: not computed")
    print("  disposition: diagnostic complete / no dynamic-exit promotion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
