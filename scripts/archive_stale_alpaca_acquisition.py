from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_acquisition import AlpacaBackfillAcquirer


def main() -> None:
    settings = load_settings()
    acquirer = AlpacaBackfillAcquirer(settings)
    _, current_fingerprint, _ = acquirer.build_plan()
    root = acquirer.acquisition_root
    report_path = acquirer.report_path

    print("ATLAS Alpaca Gate 3 Stale-State Archive")
    print("  safety: production canonical history will not be modified")
    print(f"  current inventory fingerprint: {current_fingerprint}")

    if not report_path.is_file():
        print("  prior acquisition report:      absent")
        print("  result:                        NOTHING TO ARCHIVE")
        return

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    prior_fingerprint = str(payload.get("inventory_fingerprint") or "")
    print(f"  prior inventory fingerprint:   {prior_fingerprint or '<missing>'}")
    if prior_fingerprint == current_fingerprint:
        print("  result:                        CURRENT STATE; NOTHING TO ARCHIVE")
        return

    if not prior_fingerprint:
        raise SystemExit("Prior acquisition report has no inventory fingerprint; refusing automatic archive")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive_root = root / "archive" / f"{stamp}_{prior_fingerprint[:16]}"
    archive_root.mkdir(parents=True, exist_ok=False)

    moved: list[tuple[Path, Path]] = []
    for source in (
        acquirer.unit_manifest_root,
        acquirer.observed_summary_path,
        acquirer.report_path,
    ):
        if not source.exists():
            continue
        destination = archive_root / source.name
        shutil.move(str(source), str(destination))
        moved.append((source, destination))

    manifest = {
        "archived_at_utc": datetime.now(UTC).isoformat(),
        "canonical_data_modified": False,
        "prior_inventory_fingerprint": prior_fingerprint,
        "current_inventory_fingerprint": current_fingerprint,
        "moved": [
            {"source": str(source), "destination": str(destination)}
            for source, destination in moved
        ],
    }
    manifest_path = archive_root / "archive_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"  archived items:                {len(moved)}")
    print(f"  archive:                       {archive_root}")
    print(f"  archive manifest:              {manifest_path}")
    print("  canonical data modified:       False")
    print("  result:                        STALE GATE 3 STATE ARCHIVED")


if __name__ == "__main__":
    main()
