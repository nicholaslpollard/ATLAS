from __future__ import annotations

import argparse
import heapq
import json
import os
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings


@dataclass(frozen=True)
class Bucket:
    files: int
    bytes: int


def _human_bytes(value: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    size = float(value)
    for unit in units:
        if abs(size) < 1024.0 or unit == units[-1]:
            return f"{size:,.2f} {unit}"
        size /= 1024.0
    return f"{value:,} B"


def _path_key(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _scan_tree(root: Path, largest_count: int) -> dict:
    root = root.resolve()
    top_level: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    second_level: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    extensions: Counter[str] = Counter()
    extension_bytes: Counter[str] = Counter()
    largest: list[tuple[int, str]] = []
    errors: list[str] = []
    total_files = 0
    total_bytes = 0

    if not root.exists():
        return {
            "exists": False,
            "root": str(root),
            "files": 0,
            "bytes": 0,
            "top_level": {},
            "second_level": {},
            "extensions": {},
            "largest_files": [],
            "errors": [],
        }

    for current, dirnames, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        # Never traverse directory symlinks. os.walk can otherwise hand them back
        # depending on platform/filesystem behavior even with followlinks=False.
        kept_dirs: list[str] = []
        for dirname in dirnames:
            candidate = current_path / dirname
            try:
                if not candidate.is_symlink():
                    kept_dirs.append(dirname)
            except OSError as exc:
                errors.append(f"dir:{candidate}: {exc}")
        dirnames[:] = kept_dirs

        for filename in filenames:
            path = current_path / filename
            try:
                if path.is_symlink():
                    continue
                stat = path.stat()
            except OSError as exc:
                errors.append(f"file:{path}: {exc}")
                continue

            size = int(stat.st_size)
            total_files += 1
            total_bytes += size

            try:
                rel = path.relative_to(root)
                parts = rel.parts
            except ValueError:
                parts = (filename,)

            first = parts[0] if parts else "<root>"
            top_level[first][0] += 1
            top_level[first][1] += size

            second = "/".join(parts[:2]) if len(parts) >= 2 else first
            second_level[second][0] += 1
            second_level[second][1] += size

            suffix = path.suffix.lower() or "<no_extension>"
            extensions[suffix] += 1
            extension_bytes[suffix] += size

            rel_text = rel.as_posix() if "rel" in locals() else str(path)
            item = (size, rel_text)
            if largest_count > 0:
                if len(largest) < largest_count:
                    heapq.heappush(largest, item)
                elif size > largest[0][0]:
                    heapq.heapreplace(largest, item)

    def pack_buckets(values: dict[str, list[int]]) -> dict[str, dict[str, int]]:
        return {
            key: {"files": counts[0], "bytes": counts[1]}
            for key, counts in sorted(values.items(), key=lambda item: item[1][1], reverse=True)
        }

    extension_rows = {
        ext: {"files": extensions[ext], "bytes": extension_bytes[ext]}
        for ext in sorted(extension_bytes, key=extension_bytes.get, reverse=True)
    }

    largest_rows = [
        {"path": path, "bytes": size}
        for size, path in sorted(largest, reverse=True)
    ]

    return {
        "exists": True,
        "root": str(root),
        "files": total_files,
        "bytes": total_bytes,
        "top_level": pack_buckets(top_level),
        "second_level": pack_buckets(second_level),
        "extensions": extension_rows,
        "largest_files": largest_rows,
        "errors": errors[:100],
        "error_count": len(errors),
    }


def _configured_path_buckets(scan: dict, project_root: Path, configured: dict[str, Path]) -> dict[str, dict]:
    data_root = (project_root / "data").resolve()
    second_level = scan.get("second_level", {})
    top_level = scan.get("top_level", {})
    result: dict[str, dict] = {}

    for name, configured_path in configured.items():
        resolved = configured_path if configured_path.is_absolute() else (project_root / configured_path)
        resolved = resolved.resolve()
        try:
            rel = resolved.relative_to(data_root)
        except ValueError:
            result[name] = {
                "path": str(resolved),
                "inside_data_root": False,
                "files": None,
                "bytes": None,
            }
            continue

        key = rel.as_posix()
        if len(rel.parts) == 1:
            row = top_level.get(rel.parts[0], {"files": 0, "bytes": 0})
        else:
            row = second_level.get("/".join(rel.parts[:2]), {"files": 0, "bytes": 0})
        result[name] = {
            "path": str(resolved),
            "inside_data_root": True,
            "relative_to_data": key,
            "files": int(row["files"]),
            "bytes": int(row["bytes"]),
        }
    return result


def _print_bucket_table(title: str, rows: dict[str, dict], limit: int | None = None) -> None:
    print(title)
    if not rows:
        print("  <none>")
        return
    items = list(rows.items())
    if limit is not None:
        items = items[:limit]
    for name, row in items:
        files = row.get("files")
        size = row.get("bytes")
        files_text = "?" if files is None else f"{files:,}"
        size_text = "?" if size is None else _human_bytes(int(size))
        print(f"  {name:42s} files={files_text:>12s}  bytes={size_text:>12s}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only ATLAS database-migration storage inventory. Does not modify market data."
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional JSON report path. Omit for terminal-only/read-only execution.",
    )
    parser.add_argument(
        "--largest-files",
        type=int,
        default=20,
        help="Number of largest files under data/ to report (default: 20).",
    )
    parser.add_argument(
        "--top-second-level",
        type=int,
        default=40,
        help="Number of largest second-level data directories to print (default: 40).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(PROJECT_ROOT)
    data_root = (PROJECT_ROOT / "data").resolve()

    drive = shutil.disk_usage(data_root if data_root.exists() else PROJECT_ROOT)
    scan = _scan_tree(data_root, max(0, args.largest_files))

    configured = {
        name: Path(value)
        for name, value in settings.data.paths.model_dump().items()
    }
    configured_rows = _configured_path_buckets(scan, PROJECT_ROOT, configured)

    report = {
        "contract": "atlas-database-migration-storage-inventory-v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(PROJECT_ROOT.resolve()),
        "data_root": str(data_root),
        "disk": {
            "total_bytes": int(drive.total),
            "used_bytes": int(drive.used),
            "free_bytes": int(drive.free),
        },
        "data": scan,
        "configured_paths": configured_rows,
        "notes": [
            "Read-only unless --json-out is supplied; no provider/canonical/derived market data is modified.",
            "Directory symlinks and file symlinks are not followed/counted.",
            "data/ total is the primary local V1 footprint estimate; configured buckets show where it is concentrated.",
            "This inventory does not yet estimate V2. A representative Alpaca 1-minute sizing sample is the next preflight step.",
        ],
    }

    print("ATLAS Database Migration Storage Inventory")
    print("  contract:                    atlas-database-migration-storage-inventory-v1")
    print("  mode:                        READ ONLY (unless --json-out is supplied)")
    print(f"  project root:                {PROJECT_ROOT.resolve()}")
    print(f"  data root:                   {data_root}")
    print()
    print("Disk")
    print(f"  total:                       {_human_bytes(drive.total)} ({drive.total:,} bytes)")
    print(f"  used:                        {_human_bytes(drive.used)} ({drive.used:,} bytes)")
    print(f"  free:                        {_human_bytes(drive.free)} ({drive.free:,} bytes)")
    print()
    print("ATLAS data/ total")
    print(f"  files:                       {scan['files']:,}")
    print(f"  bytes:                       {_human_bytes(scan['bytes'])} ({scan['bytes']:,} bytes)")
    if scan.get("error_count"):
        print(f"  scan errors:                 {scan['error_count']:,} (first 100 retained in JSON if written)")
    print()

    _print_bucket_table("Configured ATLAS data paths", configured_rows)
    print()
    _print_bucket_table("Largest data/ top-level directories", scan.get("top_level", {}))
    print()
    _print_bucket_table(
        f"Largest data/ second-level directories (top {args.top_second_level})",
        scan.get("second_level", {}),
        limit=max(0, args.top_second_level),
    )
    print()
    _print_bucket_table("File types by bytes", scan.get("extensions", {}), limit=30)
    print()

    print(f"Largest files under data/ (top {args.largest_files})")
    for item in scan.get("largest_files", []):
        print(f"  {_human_bytes(item['bytes']):>12s}  {item['path']}")

    if args.json_out:
        output = args.json_out if args.json_out.is_absolute() else (PROJECT_ROOT / args.json_out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print()
        print(f"JSON report:                  {output.resolve()}")

    print()
    print("Result: INVENTORY CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
