from __future__ import annotations

"""One bounded offline B34 premarket evidence review, never a backtest.

Reuses two exact selections from the already-accepted B34 workstation report:
the liquid and DST samples. Does not rediscover units, broaden to the 815
option names, download prices/news/options, use protected outcomes or trade.
"""

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path

from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.b34_premarket_decision_context_v1 import (
    B34_LAST_SAFE_SESSION, CONTRACT, build_three_cutoffs,
)
from packages.data.intraday_semantics_audit import (
    _sample_rows, _sha256_file, validate_minute_rows,
)
from packages.schemas.market import CanonicalBar
from packages.strategies.intraday_opening_pack import B34_INTRADAY_PACK_FINGERPRINT

ROOT = Path(__file__).resolve().parents[1]
ACCEPTED_REVIEW = ROOT / "docs/evidence/b34_final_closeout_acceptance.json"
OUTPUT_DIR = ROOT / "data/research/b34_premarket_context_v1"
CONTRACT_REVIEW = "atlas-b34-premarket-accepted-samples-review-v1"
SOURCE_BYTES_MAX = 12 * 1024**3  # refuse unbounded files
SAMPLE_CLASSES = ("liquid_symbol_day", "dst_session_boundary_day")
MAX_SAMPLE_ROWS = 2000


class PremarketSourceReviewError(RuntimeError):
    pass


def _read(path: Path, *, byte_limit: int = 2_000_000) -> dict:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > byte_limit:
        raise PremarketSourceReviewError("PINNED_REPORT_UNAVAILABLE_OR_UNBOUNDED")
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise PremarketSourceReviewError("EXPECTED_JSON_OBJECT")
    return result


def _fingerprint(body: dict) -> str:
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
        .encode("utf-8")
    ).hexdigest()


def run_review(root: Path = ROOT) -> dict:
    root = root.resolve()
    accepted = _read(root / "docs/evidence/b34_final_closeout_acceptance.json")
    if (accepted.get("status") != "ACCEPTED"
            or accepted.get("opening_premarket_pack", {}).get("fingerprint")
            != B34_INTRADAY_PACK_FINGERPRINT
            or accepted.get("paper_authority") is not False
            or accepted.get("live_authority") is not False
            or accepted.get("full_minute_materialization_authority") is not False):
        raise PremarketSourceReviewError("B34_ACCEPTANCE_NOT_FROZEN_RESEARCH")

    v2 = V2Layout.beneath(root / "data")
    retained = _read(v2.validation / "b34_intraday_semantics_audit.json",
                     byte_limit=4_000_000)
    if (retained.get("contract") != "atlas-b34-intraday-source-readiness-v2-ohlcv-pack-frozen"
            or retained.get("status") != "ACCEPTED"
            or retained.get("source_readiness_accepted") is not True
            or retained.get("b34_package_ready_for_repository_acceptance") is not True
            or retained.get("provider_calls") != 0
            or retained.get("broker_reads") != 0
            or retained.get("broker_writes") != 0
            or retained.get("protected_interval", {}).get(
                "overlapping_canonical_partitions_opened") != 0
            or retained.get("opening_premarket_pack", {}).get("fingerprint")
            != B34_INTRADAY_PACK_FINGERPRINT
            or retained.get("evidence_sha256")
            != accepted.get("enhanced_evidence_sha256")):
        raise PremarketSourceReviewError("RETAINED_B34_REPORT_NOT_ACCEPTED_OR_RELOCATED")

    samples = {s["sample_class"]: s for s in retained.get("sample_classes", [])
               if isinstance(s, dict) and "sample_class" in s}
    checked_units = {
        str(u["unit_id"]): u for u in retained.get("unit_integrity", [])
        if isinstance(u, dict) and "unit_id" in u
    }
    if not all(name in samples for name in SAMPLE_CLASSES):
        raise PremarketSourceReviewError("MISSING_EXACT_B34_ACCEPTED_SAMPLES")

    result_samples = []
    for sample_class in SAMPLE_CLASSES:
        item = samples[sample_class]
        day = date.fromisoformat(str(item["session_date"]))
        if day > B34_LAST_SAFE_SESSION or not item.get("accepted"):
            raise PremarketSourceReviewError("B34_SAMPLE_PROTECTED_OR_REJECTED")
        symbol = str(item["symbol"])
        unit_id = str(item["unit_id"])
        integrity = checked_units.get(unit_id)
        if not integrity or integrity.get("accepted") is not True:
            raise PremarketSourceReviewError("MISSING_ACCEPTED_UNIT_CHECKPOINT")
        path = Path(str(item["canonical_path"]))
        if (not path.is_file() or path.is_symlink()
                or path.stat().st_size > SOURCE_BYTES_MAX
                or str(path) != str(integrity.get("canonical_path"))):
            raise PremarketSourceReviewError("CANONICAL_UNIT_PATH_OR_SIZE_CHANGED")

        checkpoint = _read(Path(str(integrity["checkpoint_path"])),
                           byte_limit=256_000)
        expected = (checkpoint.get("canonical") or {}).get("sha256")
        if (not isinstance(expected, str) or len(expected) != 64
                or _sha256_file(path) != expected):
            raise PremarketSourceReviewError("CANONICAL_UNIT_HASH_CHANGED")

        # One exact symbol/day projection, no broad source inventory or scanning.
        rows = _sample_rows(path, symbol=symbol, session_date=day)
        if len(rows) != item.get("row_count") or len(rows) > MAX_SAMPLE_ROWS:
            raise PremarketSourceReviewError("B34_SAMPLE_ROW_COUNT_CHANGED")
        observed = validate_minute_rows(
            rows, sample_class=sample_class, symbol=symbol,
            session_date=day,
        )
        if not observed.get("accepted"):
            raise PremarketSourceReviewError("B34_SAMPLE_SEMANTICS_CHANGED")
        bars = [CanonicalBar.model_validate(row) for row in rows]
        contexts = build_three_cutoffs(bars, symbol=symbol, session_date=day)
        result_samples.append({
            "sample_class": sample_class,
            "symbol": symbol,
            "session_date": day.isoformat(),
            "source_row_count": len(rows),
            "verified_canonical_sha256": expected,
            "context_snapshots": list(contexts),
        })

    return {
        "contract": CONTRACT_REVIEW,
        "premarket_context_contract": CONTRACT,
        "frozen_b34_pack_fingerprint": B34_INTRADAY_PACK_FINGERPRINT,
        "accepted_b34_evidence_sha256": accepted["enhanced_evidence_sha256"],
        "read_count_exact_canonical_partitions_max": len(SAMPLE_CLASSES),
        "provider_requests": 0,
        "broker_requests": 0,
        "protected_outcomes_opened": 0,
        "scope": "accepted_source_samples_only_no_alpha_or_performance",
        "samples": result_samples,
        "status": "PREMARKET_SOURCE_CONTEXT_OBSERVED",
    }


def _save(report: dict, directory: Path = OUTPUT_DIR) -> Path:
    fp = _fingerprint(report)
    raw = (json.dumps({**report, "fingerprint": fp}, indent=2,
                      sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ("b34_premarket_decision_context_v1_" + fp[:16] + ".json")
    try:
        with path.open("xb") as out:
            out.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise PremarketSourceReviewError("RETAINED_OUTPUT_COLLISION")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS B34 CAUSAL PREMARKET SOURCE CONTEXT REVIEW V1", flush=True)
    print("  ZERO provider or broker calls; two already-accepted historical samples.")
    try:
        report = run_review()
        for sample in report["samples"]:
            print(
                f"  sample={sample['sample_class']} symbol={sample['symbol']} "
                f"session={sample['session_date']} source_rows={sample['source_row_count']}"
            )
            for ctx in sample["context_snapshots"]:
                f = ctx["features"]
                print(
                    f"    decision={ctx['decision_et']} status={ctx['feature_status']} "
                    f"pm_minutes={f['premarket_observed_minutes']} "
                    f"pm_volume={f['premarket_cumulative_volume']:g} "
                    f"pm_last={f['premarket_last_close']} "
                    f"regular_closed_minutes={f['regular_observed_closed_minutes']} "
                    f"regular_last={f['regular_last_closed_price']}"
                )
        if not args.no_write:
            print("  retained_report=" + str(_save(report)))
        print("  COMPLETE status=PREMARKET_SOURCE_CONTEXT_OBSERVED "
              "provider_requests=0 protected_outcomes_opened=0")
        return 0
    except Exception as exc:
        print("  STOP error_type=" + type(exc).__name__)
        if isinstance(exc, PremarketSourceReviewError):
            print("  reason=" + str(exc))
        print("  Original B34 and option outcomes untouched; provider_requests=0")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
