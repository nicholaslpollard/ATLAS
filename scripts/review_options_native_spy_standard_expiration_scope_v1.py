from __future__ import annotations

"""Classify the expiration and quote-clock scope of ONE pinned 2025 SPY canary.

Zero ThetaData or broker calls. No outcome data, retries, new market queries,
historical option replay, silent row removal, source acceptance or trading.
Original source bytes are read only after the accepted SHA-bound replay.
"""

from collections import Counter, defaultdict
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_thetadata_quote_qualification_v1 import (
    RAW_RESPONSE_CAP, REQUIRED_FIELDS,
)
from scripts.audit_options_native_spy_standard_one_quote_v1 import (
    RETAINED_REL, audit_saved_quote,
)

CONTRACT = "atlas-options-native-spy-standard-2025-expiration-scope-diagnostic-v1"
PINNED_BODY_SHA = "cbe1b2d9a48b6812448a6b0a2f394fab21a9ca04dec550e67558a33b155e8ecf"
PINNED_SCHEMA_AUDIT = "8aefd5e9a3612160"
PINNED_SESSION = date(2025, 6, 9)
FROZEN_MAX_DTE = 45
FROZEN_CLOCK = datetime(2025, 6, 9, 10, 0, tzinfo=ZoneInfo("America/New_York"))
MAX_ROWS = 10_000


def _parse_expiration(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_quote_clock(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return None
    return timestamp.astimezone(FROZEN_CLOCK.tzinfo)


def inspect_saved_expiration_scope(
    report_path: Path, *, write_report: bool = False,
) -> dict:
    # Existing source validator independently checks original summary/query,
    # SHA-256 body provenance, canonical JSON, and the reproduced rejection.
    prior = audit_saved_quote(report_path, write=False)
    if (
        prior["replay"] != "REPRODUCED"
        or prior["replay_reason"] != "OUT_OF_SCOPE_OPTION_EXPIRATION"
        or prior["fingerprint"][:16] != PINNED_SCHEMA_AUDIT
        or prior["original_sha256"] != PINNED_BODY_SHA
        or prior["rows"] != 264
        or prior["rights"] != {"CALL": 132, "PUT": 132}
        or prior["missing_required"] != []
        or prior["provider_requests"] != 0
    ):
        raise ValueError("PINNED_2025_SOURCE_AUDIT_NOT_MATCHED")
    data_path = report_path.parent / "raw" / "single_quote.json"
    if (
        data_path.is_symlink() or not data_path.is_file()
        or not 0 < data_path.stat().st_size <= RAW_RESPONSE_CAP
    ):
        raise ValueError("ORIGINAL_2025_QUOTE_BYTES_UNAVAILABLE")
    raw = data_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PINNED_BODY_SHA:
        raise ValueError("ORIGINAL_2025_QUOTE_SHA_DRIFT")
    rows = json.loads(raw)
    if not isinstance(rows, list) or len(rows) != 264 or len(rows) > MAX_ROWS:
        raise ValueError("ORIGINAL_2025_QUOTE_ROW_COUNT_DRIFT")

    expiration_summary = defaultdict(lambda: {
        "call_rows": 0, "put_rows": 0, "other_right_rows": 0,
        "distinct_strikes": set(), "pairs": defaultdict(set),
    })
    bucket = Counter()
    anomalies = Counter()
    clock_observed: list[datetime] = []
    first_out_of_scope: dict | None = None
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("ORIGINAL_2025_QUOTE_ROW_TYPE_DRIFT")
        if set(REQUIRED_FIELDS) - set(row):
            anomalies["missing_required_per_row"] += 1
        exp = _parse_expiration(row.get("expiration"))
        if exp is None:
            bucket["invalid_expiration"] += 1
            anomalies["invalid_expiration"] += 1
            continue
        dte = (exp - PINNED_SESSION).days
        if dte < 0:
            scope = "expired_before_decision"
        elif dte > FROZEN_MAX_DTE:
            scope = "over_max_dte"
        else:
            scope = "within_requested_dte"
        bucket[scope] += 1
        if first_out_of_scope is None and scope != "within_requested_dte":
            first_out_of_scope = {
                "index": idx, "expiration": exp.isoformat(),
                "dte_calendar_days": dte, "scope": scope,
            }
        key = (exp.isoformat(), dte, scope)
        item = expiration_summary[key]
        right = str(row.get("right", "")).lower()
        if right in ("call", "put"):
            item[right + "_rows"] += 1
        else:
            item["other_right_rows"] += 1
            anomalies["unknown_right"] += 1
        strike = row.get("strike")
        if isinstance(strike, (int, float)) and not isinstance(strike, bool):
            item["distinct_strikes"].add(strike)
            if right in ("call", "put"):
                item["pairs"][str(strike)].add(right)
        else:
            anomalies["unparseable_strike"] += 1
        clock = _parse_quote_clock(row.get("timestamp"))
        if clock is None:
            anomalies["missing_or_naive_quote_clock"] += 1
        else:
            clock_observed.append(clock)
            if clock.date() != PINNED_SESSION:
                anomalies["different_market_date_clock"] += 1
            if clock > FROZEN_CLOCK:
                anomalies["quote_after_decision_clock"] += 1
        bid, ask = row.get("bid"), row.get("ask")
        if not all(isinstance(x, (float, int)) and not isinstance(x, bool) for x in (bid, ask)):
            anomalies["non_numeric_bid_or_ask"] += 1
        elif bid > 0 and ask > 0 and ask < bid:
            anomalies["crossed_quote"] += 1

    by_expiration = []
    for (exp, dte, scope), item in sorted(
        expiration_summary.items(),
        key=lambda e: (e[0][1], e[0][0]),
    ):
        by_expiration.append({
            "expiration": exp, "dte_calendar_days": dte,
            "scope": scope, "calls": item["call_rows"],
            "puts": item["put_rows"], "other_rights": item["other_right_rows"],
            "distinct_strikes": len(item["distinct_strikes"]),
            "shared_call_put_strikes": sum(
                s == {"call", "put"} for s in item["pairs"].values()
            ),
        })
    report = {
        "contract": CONTRACT,
        "status": "SOURCE_EXPIRATION_SCOPE_DIAGNOSTIC_ONLY",
        "source_sha256": PINNED_BODY_SHA,
        "prior_schema_audit_fingerprint": prior["fingerprint"],
        "query_fingerprint": prior["original_report_fingerprint"],
        "decision_session": PINNED_SESSION.isoformat(),
        "decision_time_et": FROZEN_CLOCK.isoformat(),
        "requested_max_dte": FROZEN_MAX_DTE,
        "raw_rows": len(rows),
        "expiration_buckets": dict(sorted(bucket.items())),
        "distinct_expiration_count": len(by_expiration),
        "per_expiration": by_expiration,
        "first_out_of_scope_original_order": first_out_of_scope,
        "other_schema_and_clock_anomalies": dict(sorted(anomalies.items())),
        "parsed_timestamp_count": len(clock_observed),
        "first_quote_time_et": (
            min(clock_observed).isoformat() if clock_observed else None
        ),
        "last_quote_time_et": (
            max(clock_observed).isoformat() if clock_observed else None
        ),
        "all_returned_rows_within_requested_dte": (
            bucket.get("within_requested_dte", 0) == len(rows)
        ),
        "provider_requests": 0, "broker_requests": 0,
        "protected_outcomes_read": 0, "option_outcomes_read": 0,
        "source_accepted": False, "split_subset_strategy_admissible": False,
        "further_paid_requests_authorized": False,
        "note": "Do not silently filter or relax max_dte. Entire original "
                "provider response is still unqualified. No performance run.",
    }
    report["fingerprint"] = _fingerprint(report)
    if write_report:
        path = report_path.parent / (
            "offline_expiration_scope_v1_" + report["fingerprint"][:16] + ".json"
        )
        blob = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
        if path.is_symlink() or (path.exists() and path.read_text("utf-8") != blob):
            raise ValueError("EXPIRATION_SCOPE_REPORT_TARGET_CONFLICT")
        if not path.exists():
            atomic_write_text(path, blob, fsync=True)
        report["saved_report"] = str(path)
    return report


def main() -> int:
    print("ATLAS STANDARD SPY 2025 RETAINED EXPIRATION SCOPE REVIEW V1", flush=True)
    print("  Only the previously accepted 264-row SHA-pinned quote source; no provider calls.", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        report = inspect_saved_expiration_scope(
            settings.resolved_path(RETAINED_REL), write_report=True
        )
        print(f"  sha256={report['source_sha256']} rows={report['raw_rows']} "
              f"requested_dte=[0,{report['requested_max_dte']}]", flush=True)
        print(f"  expiration_buckets={report['expiration_buckets']} "
              f"unique_expirations={report['distinct_expiration_count']}", flush=True)
        print(f"  first_offending={report['first_out_of_scope_original_order']}", flush=True)
        for item in report["per_expiration"]:
            print(
                f"  expiration={item['expiration']} dte={item['dte_calendar_days']} "
                f"scope={item['scope']} C={item['calls']} P={item['puts']} "
                f"shared_strikes={item['shared_call_put_strikes']}",
                flush=True,
            )
        print(f"  other_anomalies={report['other_schema_and_clock_anomalies']}", flush=True)
        print(f"  earliest_quote={report['first_quote_time_et']} "
              f"latest_quote={report['last_quote_time_et']}", flush=True)
        print(f"  retained_diagnostic={report['saved_report']}", flush=True)
        print("  COMPLETE status=ORIGINAL_SOURCE_ONLY_NOT_ACCEPTED "
              "provider_requests=0 protected_outcomes_read=0", flush=True)
        return 0
    except Exception as exc:
        print(f"  STOP category={type(exc).__name__} "
              "no provider reads or original-file modifications", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
