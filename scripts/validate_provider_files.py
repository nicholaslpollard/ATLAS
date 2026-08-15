from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.enums import IngestionStatus
from packages.core.settings import load_settings
from packages.ingestion.manifest import DirectoryManifestStore
from packages.ingestion.staging import FlatFileValidator
from packages.providers.massive.flat_files import MassiveFlatFileProvider
from packages.providers.massive.normalizer import parse_stock_dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate already-downloaded Massive provider files tracked by ATLAS.")
    parser.add_argument("--dataset", required=True)
    args = parser.parse_args(argv)

    settings = load_settings(PROJECT_ROOT)
    dataset = parse_stock_dataset(args.dataset)
    manifest = DirectoryManifestStore(settings.resolved_path(settings.data.paths.manifests) / "ingestion")
    # Provider is used only for configuration/header definitions here. Building it
    # would require credentials, so use config directly instead.
    expected_columns = settings.massive.flat_files.datasets[dataset.value].expected_columns
    validator = FlatFileValidator(
        validate_gzip_crc=settings.massive.flat_files.validate_gzip_crc,
        count_rows=settings.massive.flat_files.count_rows_during_validation,
    )

    failures = 0
    checked = 0
    for record in manifest.list_records():
        if record.dataset != dataset or record.status not in {IngestionStatus.VALIDATED, IngestionStatus.COMPLETE}:
            continue
        result = validator.validate(record.local_path, expected_columns=expected_columns, expected_size_bytes=record.size_bytes, expected_sha256=record.sha256)
        checked += 1
        if not result.is_valid:
            failures += 1
            print(f"FAIL {record.trading_date}: {record.local_path} -> {result.errors}")
        else:
            print(f"PASS {record.trading_date}: {record.local_path}")

    print(f"Checked {checked} file(s); failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
