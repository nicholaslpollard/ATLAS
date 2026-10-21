from __future__ import annotations

"""Read one ACCEPTED April-2026 ZSL canonical unit for 20 prior PM sessions.

Offline/limited: one accepted B34 unit; exactly one symbol; the 20 exchange
sessions preceding 2026-04-30. No outcomes, news, ThetaData or broker calls.
This is NOT a backtest and raw volume ratios are NOT split-qualified signals.
"""

import argparse
from collections import defaultdict
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb

from packages.core.market_calendar import MarketCalendar
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.b34_premarket_prior20_volume_v1 import review_prior20
from packages.schemas.market import CanonicalBar
from scripts.review_b34_premarket_decision_context_v1 import (
    ROOT, _read, run_review,
)

CONTRACT = "atlas-b34-premarket-prior20-source-review-v1"
SYMBOL = "ZSL"
SAMPLE_DATE = date(2026, 4, 30)
MAX_ROWS_PRIOR = 20 * 330
MAX_CANONICAL_BYTES = 12 * 1024**3
OUTPUT_SUBDIR = "data/research/b34_premarket_context_v1"


class Prior20SourceError(RuntimeError):
    pass


def _fingerprint(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"),
                   allow_nan=False).encode("utf-8")
    ).hexdigest()


def _query_prior_premarket(
    path: Path, *, symbol: str, first: date, last_exclusive: date
) -> list[dict[str, Any]]:
    """Single bounded, source-only Parquet projection; no broad symbol scan."""
    con = duckdb.connect(":memory:")
    try:
        con.execute("SET TimeZone='UTC'")
        con.execute("PRAGMA threads=2")
        con.execute("SET memory_limit='512MB'")
        cols = [
            str(x[0]) for x in con.execute(
                "DESCRIBE SELECT * FROM read_parquet(?, hive_partitioning=false)",
                [str(path)],
            ).fetchall()
        ]
        rows = con.execute(
            """
            SELECT *
            FROM read_parquet(?, hive_partitioning=false)
            WHERE symbol = ?
                AND session_date >= ?
                AND session_date < ?
                AND session_segment = 'premarket'
            ORDER BY session_date, timestamp_utc
            """,
            [str(path), symbol, first, last_exclusive],
        ).fetchall()
        if len(rows) > MAX_ROWS_PRIOR:
            raise Prior20SourceError("PRIOR20_MINUTE_ROW_CAP_EXCEEDED")
        return [dict(zip(cols, row, strict=True)) for row in rows]
    finally:
        con.close()


def run() -> dict[str, Any]:
    # This existing reviewer hash-checks the two selected B34 source units,
    # verifies original receipts, and never opens the master protected period.
    base = run_review()
    sample = next(
        (item for item in base["samples"]
         if item["sample_class"] == "liquid_symbol_day"),
        None,
    )
    if (sample is None or sample["symbol"] != SYMBOL
            or sample["session_date"] != SAMPLE_DATE.isoformat()
            or sample["source_row_count"] != 720
            or base["provider_requests"] != 0
            or base["protected_outcomes_opened"] != 0):
        raise Prior20SourceError("B34_APRIL_SOURCE_SELECTION_NOT_ACCEPTED")

    retained = _read(
        V2Layout.beneath(ROOT / "data").validation
        / "b34_intraday_semantics_audit.json", byte_limit=4_000_000
    )
    matching = [
        row for row in retained.get("sample_classes", [])
        if isinstance(row, dict)
        and row.get("sample_class") == "liquid_symbol_day"
    ]
    if len(matching) != 1:
        raise Prior20SourceError("B34_EXACT_SOURCE_SELECTION_AMBIGUOUS")
    entry = matching[0]
    path = Path(str(entry["canonical_path"]))
    if (not path.is_file() or path.is_symlink()
            or path.stat().st_size > MAX_CANONICAL_BYTES
            or entry.get("symbol") != SYMBOL
            or entry.get("session_date") != SAMPLE_DATE.isoformat()
            or not path.name.endswith(".parquet")):
        raise Prior20SourceError("B34_SOURCE_UNIT_NOT_READABLE")
    # The original B34 reviewer already verified this exact file against its
    # canonical checkpoint SHA256. No second expensive full-file hash pass.
    expected = sample["verified_canonical_sha256"]

    calendar = MarketCalendar()
    dates = calendar.sessions_in_range(date(2026, 4, 1),
                                       date(2026, 4, 29))
    if len(dates) != 20 or dates != sorted(dates):
        raise Prior20SourceError("EXACT_20_PRIOR_EXCHANGE_SESSIONS_NOT_FOUND")

    history = _query_prior_premarket(
        path, symbol=SYMBOL, first=dates[0], last_exclusive=SAMPLE_DATE
    )
    by_date: dict[date, list[CanonicalBar]] = defaultdict(list)
    for raw in history:
        bar = CanonicalBar.model_validate(raw)
        if (bar.symbol != SYMBOL or bar.session_date not in dates
                or bar.session_segment.value != "premarket"):
            raise Prior20SourceError("PRIOR20_CANONICAL_SCOPE_VIOLATION")
        by_date[bar.session_date].append(bar)

    # All 20 date identities are retained. Sessions without any observed
    # premarket bars remain explicit empty samples, not zero-volume sessions.
    results = review_prior20(
        symbol=SYMBOL,
        current_session=SAMPLE_DATE,
        current_bars=(),  # replaced below from accepted exact source selection
        prior_sessions=dates,
        prior_bars_by_session={d: tuple(by_date[d]) for d in dates},
    )
    return results


def run_with_current() -> dict[str, Any]:
    """Use only the single accepted ZSL session, without duplicate full scans."""
    # Re-run the original bounded reviewer to hash-check accepted source identity.
    base = run_review()
    samples = [x for x in base["samples"]
               if x["sample_class"] == "liquid_symbol_day"]
    if (len(samples) != 1 or samples[0]["symbol"] != SYMBOL
            or samples[0]["session_date"] != SAMPLE_DATE.isoformat()
            or samples[0]["source_row_count"] != 720):
        raise Prior20SourceError("B34_APRIL_SOURCE_SELECTION_NOT_ACCEPTED")

    retained = _read(
        V2Layout.beneath(ROOT / "data").validation
        / "b34_intraday_semantics_audit.json", byte_limit=4_000_000
    )
    matching = [x for x in retained.get("sample_classes", [])
                if isinstance(x, dict) and x.get("sample_class") == "liquid_symbol_day"]
    if len(matching) != 1:
        raise Prior20SourceError("B34_EXACT_SOURCE_SELECTION_AMBIGUOUS")
    item = matching[0]
    path = Path(str(item["canonical_path"]))
    if (not path.is_file() or path.is_symlink()
            or path.stat().st_size > MAX_CANONICAL_BYTES
            or item.get("symbol") != SYMBOL
            or item.get("session_date") != SAMPLE_DATE.isoformat()):
        raise Prior20SourceError("B34_SOURCE_UNIT_NOT_READABLE")
    current_rows = _read_current(path)
    calendar = MarketCalendar()
    prior_sessions = calendar.sessions_in_range(
        date(2026, 4, 1), date(2026, 4, 29)
    )
    if len(prior_sessions) != 20 or prior_sessions != sorted(prior_sessions):
        raise Prior20SourceError("EXACT_20_PRIOR_EXCHANGE_SESSIONS_NOT_FOUND")
    prior_rows = _query_prior_premarket(
        path, symbol=SYMBOL, first=prior_sessions[0],
        last_exclusive=SAMPLE_DATE
    )
    by_day: dict[date, list[CanonicalBar]] = defaultdict(list)
    for raw in prior_rows:
        bar = CanonicalBar.model_validate(raw)
        if (bar.session_date not in prior_sessions or bar.symbol != SYMBOL
                or bar.session_segment.value != "premarket"):
            raise Prior20SourceError("PRIOR20_CANONICAL_SCOPE_VIOLATION")
        by_day[bar.session_date].append(bar)
    report = review_prior20(
        symbol=SYMBOL, current_session=SAMPLE_DATE,
        current_bars=current_rows,
        prior_sessions=prior_sessions,
        prior_bars_by_session={day: by_day[day] for day in prior_sessions},
    )
    return {
        "contract": CONTRACT, "source_contract": report["contract"],
        "source_accepted_b34_closeout_fingerprint": base[
            "accepted_b34_evidence_sha256"
        ],
        "source_canonical_sha256": samples[0]["verified_canonical_sha256"],
        "selected_symbol": SYMBOL, "selected_session": SAMPLE_DATE.isoformat(),
        "prior_rows_read": len(prior_rows),
        "current_sample_rows_read": len(current_rows),
        "status": "PRIOR20_SOURCE_DIAGNOSTIC_NO_SIGNAL",
        **report,
    }


def _read_current(path: Path) -> list[CanonicalBar]:
    # One exact symbol/session query, no entire-month in-memory materialization.
    from packages.data.intraday_semantics_audit import _sample_rows

    rows = _sample_rows(path, symbol=SYMBOL, session_date=SAMPLE_DATE)
    if len(rows) != 720:
        raise Prior20SourceError("B34_CURRENT_SOURCE_ROW_COUNT_CHANGED")
    return [CanonicalBar.model_validate(row) for row in rows]


def _save(report: dict[str, Any], root: Path | None = None) -> Path:
    root = ROOT / OUTPUT_SUBDIR if root is None else root
    fp = _fingerprint(report)
    output = (json.dumps({**report, "fingerprint": fp}, indent=2,
                         sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    if len(output) > 512 * 1024:
        raise Prior20SourceError("PRIOR20_REPORT_TOO_LARGE")
    root.mkdir(parents=True, exist_ok=True)
    file = root / f"b34_premarket_prior20_volume_v1_{fp[:16]}.json"
    try:
        with file.open("xb") as target:
            target.write(output)
    except FileExistsError:
        if file.read_bytes() != output:
            raise Prior20SourceError("PRIOR20_OUTPUT_COLLISION")
    return file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS B34 PINNED APRIL PREMARKET PRIOR-20 VOLUME REVIEW V1")
    print("  ZERO provider/broker/outcome calls; accepted ZSL April unit only.")
    try:
        report = run_with_current()
        print(f"  symbol={SYMBOL} session={SAMPLE_DATE} "
              f"prior_sessions=20 prior_premarket_rows={report['prior_rows_read']}")
        for row in report["snapshots"]:
            print(
                f"  cutoff={row['decision_clock_et']} "
                f"today_pm_volume={row['current_observed_premarket_volume']:g} "
                f"prior_20_observed={row['prior_sessions_with_observed_premarket']} "
                f"prior_median={row['prior_20_median_observed_premarket_volume']} "
                f"raw_ratio_diagnostic={row['raw_volume_ratio_diagnostic_only']} "
                f"eligible_for_strategy={row['volume_ratio_admissible_as_strategy_input']}"
            )
        if not args.no_write:
            print("  retained_report=" + str(_save(report)))
        print("  COMPLETE status=PRIOR20_SOURCE_DIAGNOSTIC_NO_SIGNAL "
              "provider_requests=0 protected_outcomes_opened=0")
        return 0
    except Exception as exc:
        print("  STOP error_type=" + type(exc).__name__)
        if isinstance(exc, Prior20SourceError):
            print("  reason=" + str(exc))
        print("  ZERO provider requests; accepted sources unchanged")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
