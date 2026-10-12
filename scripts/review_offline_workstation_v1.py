from __future__ import annotations

"""One provider-free review of storage bindings and retained metadata locations."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.exceptions import ConfigurationError
from packages.core.settings import load_settings
from packages.data.offline_workstation_review_v1 import build_offline_workstation_review


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save-report", action="store_true", help="Save one new inventory JSON under data/research/offline_workstation_review_v1; original artifacts remain read-only.")
    args = parser.parse_args(argv)
    print("ATLAS OFFLINE WORKSTATION REVIEW V1", flush=True)
    print("  Metadata only; zero provider/broker requests, raw-data scans, and simulations.", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        report = build_offline_workstation_review(settings)
        storage = report["storage"]
        print(f"  secondary storage: {storage['status']} / {storage['external_root']}", flush=True)
        for row in storage["bindings"]:
            print(f"    {row['name']}: {row['status']}", flush=True)
        for row in report["volumes"]:
            free = row.get("free_bytes")
            value = "unavailable" if free is None else f"{free / 1024**3:.2f} GiB free"
            print(f"  {row['name']}: {value}", flush=True)
        for group in report["artifact_groups"]:
            print(f"  {group['name']}: {group['status']} / {len(group['files'])} metadata files", flush=True)
            for row in group["files"]:
                headers = row.get("reported_headers", {})
                print(f"    {Path(row['path']).name}: {row['inspection']} / reported_status={headers.get('status', 'not recorded')}", flush=True)
            if group.get("missing_patterns"):
                print(f"    missing: {', '.join(group['missing_patterns'])}", flush=True)
            if group.get("candidate_set_truncated"):
                print("    candidate list truncated; no active artifact selected", flush=True)
        if args.save_report:
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            output = settings.resolved_path(f"data/research/offline_workstation_review_v1/{stamp}.json")
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x", encoding="utf-8") as stream:
                json.dump(report, stream, indent=2, sort_keys=True)
                stream.write("\n")
            print(f"  saved report: {output}", flush=True)
        print(f"  COMPLETE: {report['status']}; inventory does not grant source or strategy acceptance.", flush=True)
        return 0
    except (ConfigurationError, OSError, ValueError) as exc:
        print(f"OFFLINE REVIEW STOPPED: {type(exc).__name__}", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
