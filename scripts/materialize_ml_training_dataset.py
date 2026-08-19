from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.ml.datasets import (
    ML_TRAINING_DATASET_CONTRACT_VERSION,
    ML_TRAINING_DATASET_MARKET_CONTEXT_ROLE,
    ML_TRAINING_DATASET_OBSERVATION_KEY_CONTRACT,
    ML_TRAINING_DATASET_ORDERING,
    MLTrainingDatasetMaterializer,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize or verify the immutable Phase 10 ML training dataset."
    )
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify the lineage and file hashes of the already-materialized dataset.",
    )
    return parser


def _print_manifest(manifest: object, *, reused: bool | None, wall_seconds: float) -> None:
    row_count = int(getattr(manifest, "row_count"))
    context_rows = int(getattr(manifest, "market_context_rows"))
    class_counts = dict(getattr(manifest, "class_row_counts"))
    partitions = tuple(getattr(manifest, "partitions"))
    print("ATLAS Phase 10 Gate 6 Immutable Training Dataset")
    print(f"  contract:                    {getattr(manifest, 'contract_version')}")
    print(f"  dataset id:                  {getattr(manifest, 'dataset_id')}")
    if reused is not None:
        print(f"  existing immutable dataset:  {reused}")
    print(f"  history:                     {getattr(manifest, 'history_start')} -> {getattr(manifest, 'history_end')}")
    print(f"  rows / distinct keys:        {row_count:,} / {int(getattr(manifest, 'distinct_observation_keys')):,}")
    print(f"  symbols:                     {int(getattr(manifest, 'symbol_count')):,}")
    print(f"  observation range:           {getattr(manifest, 'first_session_date')} -> {getattr(manifest, 'last_session_date')}")
    print(f"  predictors:                  {int(getattr(manifest, 'predictor_count'))}")
    print(f"  observation key:             {ML_TRAINING_DATASET_OBSERVATION_KEY_CONTRACT}")
    print(f"  ordering:                    {ML_TRAINING_DATASET_ORDERING}")
    print(f"  market context role:         {ML_TRAINING_DATASET_MARKET_CONTEXT_ROLE}")
    print(f"  market context rows:         {context_rows:,} ({(0.0 if row_count == 0 else context_rows / row_count):.2%})")
    print(
        "  classes:                     "
        f"DOWN={int(class_counts.get('DOWN', 0)):,} "
        f"NEUTRAL={int(class_counts.get('NEUTRAL', 0)):,} "
        f"UP={int(class_counts.get('UP', 0)):,}"
    )
    print(f"  lineage SHA-256:             {getattr(manifest, 'dataset_lineage_fingerprint')}")
    print(f"  partitions:                  {len(partitions)}")
    for partition in partitions:
        print(
            f"    {int(getattr(partition, 'year'))}: rows={int(getattr(partition, 'row_count')):,} "
            f"keys={int(getattr(partition, 'distinct_observation_keys')):,} "
            f"sha256={getattr(partition, 'sha256')}"
        )
    print(f"  wall time:                   {wall_seconds:.3f}s")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(PROJECT_ROOT)
    service = MLTrainingDatasetMaterializer(settings)
    started = perf_counter()
    if args.verify:
        manifest = service.verify(args.end)
        _print_manifest(manifest, reused=None, wall_seconds=perf_counter() - started)
        print("  result:                      VERIFIED")
        return 0

    manifest, reused = service.materialize(args.end)
    _print_manifest(manifest, reused=reused, wall_seconds=perf_counter() - started)
    print("  result:                      MATERIALIZED" if not reused else "  result:                      REUSED / VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
