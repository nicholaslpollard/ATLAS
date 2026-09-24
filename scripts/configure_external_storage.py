from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.external_storage import (
    ExternalStorageError,
    apply_external_storage_bindings,
    inspect_external_storage,
    snapshot_as_dict,
)


def _persist_env_root(project_root: Path, root: Path) -> None:
    env_path = project_root / ".env"
    key = "ATLAS_EXTERNAL_DATA_ROOT"
    value = root.resolve().as_posix()
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    replaced = False
    output: list[str] = []
    for line in lines:
        if line.startswith(key + "="):
            output.append(f"{key}={value}")
            replaced = True
        else:
            output.append(line)
    if not replaced:
        if output and output[-1] != "":
            output.append("")
        output.append(f"{key}={value}")
    env_path.write_text("\n".join(output) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare ATLAS secondary-data directories on an external drive while "
            "leaving the core ATLAS installation and stock database in place."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help="External ATLAS data root, e.g. F:/ATLAS_DATA",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create external directories and bind the configured project paths.",
    )
    parser.add_argument(
        "--migrate-existing",
        action="store_true",
        help=(
            "Move existing files from configured secondary project directories "
            "to the external target before binding them."
        ),
    )
    parser.add_argument(
        "--persist-env",
        action="store_true",
        help=(
            "After a successful READY setup, persist ATLAS_EXTERNAL_DATA_ROOT "
            "in the repository .env file."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Do not make an existing .env external-root value influence bootstrap inspection.
    prior = os.environ.pop("ATLAS_EXTERNAL_DATA_ROOT", None)
    try:
        settings = load_settings(PROJECT_ROOT, "development")
    finally:
        if prior is not None:
            os.environ["ATLAS_EXTERNAL_DATA_ROOT"] = prior

    root = args.root.expanduser().resolve()
    if args.apply:
        try:
            snapshot = apply_external_storage_bindings(
                settings,
                external_root=root,
                migrate_existing=bool(args.migrate_existing),
            )
        except ExternalStorageError as exc:
            print(f"EXTERNAL STORAGE SETUP FAILED: {exc}")
            return 3
        if args.persist_env:
            _persist_env_root(PROJECT_ROOT, root)
    else:
        snapshot = inspect_external_storage(settings, root_override=root)

    print("ATLAS External Secondary Storage V1")
    print(f"  external root: {root}")
    print(f"  status: {snapshot.status}")
    print("  stock database moved: false")
    print("  primary ATLAS data paths changed: false")
    for item in snapshot.bindings:
        print(
            f"  {item.name}: {item.status}\n"
            f"    project:  {item.project_path}\n"
            f"    external: {item.external_path}"
        )
    if args.persist_env and snapshot.status == "READY":
        print("  persisted: ATLAS_EXTERNAL_DATA_ROOT in .env")
    elif snapshot.status == "READY":
        print(
            "  note: add ATLAS_EXTERNAL_DATA_ROOT to .env before normal ATLAS "
            "runs if you want external-volume storage accounting enabled"
        )

    return 0 if snapshot.status == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
