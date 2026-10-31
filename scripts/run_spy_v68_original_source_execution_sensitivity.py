from __future__ import annotations

"""V68: immutable, offline, six-policy SPY quote-reference execution sensitivity.

Post-hoc *diagnostic* only. Replays the exact accepted V67 June 9–20 option
source archives using the pre-existing V55 latency/price-drift policies. It
does not infer fills, optimize a held-out strategy, place broker orders,
manufacture missing quotes, or trigger redundant provider requests.
"""

import argparse
from collections import Counter
from decimal import Decimal
from datetime import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v55_closed_bar_option_replay import replay_source
from scripts.run_spy_v59_offline_quote_forensics import _local_cache_only

ROOT = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")
CONTRACT = "atlas-v68-six-policy-spy-original-quote-execution-sensitivity-v1"
PARENT_V67 = "atlas-v67-source-acquire-and-independent-replay-joint-acceptance-v1"
PARENT_V65 = "atlas-v65-full-horizon-spy-closed-bar-offline-source-gate-v1"
PARENT_V67_SHA = "cdc01c98f6ce8c53d85c90e9ed8cb4d13342fc927b24c64eb099eb0f8b5be417"
PARENT_V65_SHA = "94b5eb507fb18fecb781d827aa3be672c16ebc5c832b894a609c16540c3edd9f"
POLICIES = ((1, "0.5"), (1, "1"), (1, "2"), (3, "0.5"), (3, "1"), (3, "2"))
SIX_SIGNALS = (
    "2025-06-09", "2025-06-11", "2025-06-13",
    "2025-06-16", "2025-06-18", "2025-06-20",
)


class V68Error(ValueError):
    pass


def announce(message):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {message}", flush=True)


def signed(obj):
    return {**obj, "fingerprint": _fingerprint(obj)}


def read_signed(path, *, contract, expected_sha):
    if path.is_symlink() or not path.is_file():
        raise V68Error("V68_PARENT_MISSING_OR_UNSAFE")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(doc, dict)
            or doc.get("contract") != contract
            or doc.get("fingerprint") != expected_sha
            or doc["fingerprint"] != _fingerprint({
                k: v for k, v in doc.items() if k != "fingerprint"
            })):
        raise V68Error("V68_PARENT_OR_FINGERPRINT_CHANGED")
    return doc


def accepted_input(v67, v65):
    if (v67.get("status") != "COMPLETE_SOURCE_AND_OFFLINE_CENSUS"
            or v67.get("v65_refreshed_fingerprint") != v65.get("fingerprint")
            or v67.get("v65_refreshed_source_counts") != {"ARCHIVED": 6}
            or v67.get("v66_result_counts") != {"SOURCE_ARCHIVED_AND_REVERIFIED": 3}
            or v65.get("start") != "2025-06-09"
            or v65.get("end") != "2025-06-20"
            or v65.get("weekdays_in_calendar_scope") != 10
            or v65.get("provider_requests") != 0
            or v65.get("broker_orders") != 0
            or len(v65.get("session_reports", [])) != 10):
        raise V68Error("V68_PARENT_SOURCE_COVERAGE_UNQUALIFIED")
    rows = v65["session_reports"]
    if len({x["session"] for x in rows}) != 10:
        raise V68Error("V68_DUPLICATE_SESSION")
    if sorted(x["session"] for x in rows if x["selected_contract"]) != list(SIX_SIGNALS):
        raise V68Error("V68_SIGNAL_SELECTION_CHANGED")
    for row in rows:
        if row["fingerprint"] != _fingerprint({
            k: v for k, v in row.items() if k != "fingerprint"
        }):
            raise V68Error("V68_V65_SESSION_FINGERPRINT_CHANGED")
        original = row["standalone_replay_report"]
        if original["fingerprint"] != _fingerprint({
            k: v for k, v in original.items() if k != "fingerprint"
        }):
            raise V68Error("V68_V65_STANDALONE_REPLAY_FINGERPRINT_CHANGED")
        if original.get("actual_fills") != 0 or not original.get("quote_reference_not_broker_execution"):
            raise V68Error("V68_ORIGINAL_EXECUTION_AUTHORITY_CHANGED")
        if row["selected_contract"]:
            receipt = row.get("exact_option_receipt")
            requirement = row.get("exact_option_requirement")
            if (not isinstance(receipt, dict)
                    or receipt.get("state") != "ARCHIVED"
                    or not isinstance(requirement, dict)
                    or receipt.get("query_id") != _fingerprint(requirement)
                    or original.get("source_query_id") != receipt["query_id"]
                    or original.get("source_sha256") != receipt["archive_sha256"]):
                raise V68Error("V68_ARCHIVED_SOURCE_RECEIPT_CHANGED")
    return rows


def write_gzip_once(path, doc):
    raw = (json.dumps(doc, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    with path.open("xb") as stream:
        with gzip.GzipFile(filename="", mode="wb", compresslevel=6,
                           mtime=0, fileobj=stream) as packed:
            packed.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    with path.open("rb") as stream:
        h = hashlib.sha256()
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def run(
    v67_summary, refreshed_v65, outdir, *,
    settings_fn=load_settings, cache_read=_local_cache_only,
    replay=replay_source, progress=announce,
):
    # Verify both immutable reports, all session/signature links and six source
    # requirements before touching the output directory.
    v67 = read_signed(v67_summary, contract=PARENT_V67, expected_sha=PARENT_V67_SHA)
    v65 = read_signed(refreshed_v65, contract=PARENT_V65, expected_sha=PARENT_V65_SHA)
    rows = accepted_input(v67, v65)
    if outdir.exists() or outdir.is_symlink():
        raise V68Error("V68_IMMUTABLE_OUTPUT_ALREADY_EXISTS")
    settings = settings_fn(ROOT, "development")
    sources = {}
    for row in rows:
        requirement = row["exact_option_requirement"]
        if requirement is None:
            continue
        qid = row["exact_option_receipt"]["query_id"]
        acquired = cache_read(settings, qid)
        source = acquired.get("source")
        if (acquired.get("cache_evidence") != "CACHE_HIT"
                or not isinstance(source, dict)
                or source.get("query_id") != qid
                or source.get("exact_requirement") != requirement
                or source.get("source_sha256") != row["exact_option_receipt"]["archive_sha256"]):
            raise V68Error("V68_SOURCE_ACQUISITION_REQUIRED_OR_SHA_INVALID")
        sources[row["session"]] = source
    if len(sources) != 6:
        raise V68Error("V68_EXPECTED_ALL_SIX_EXACT_SOURCES")

    outdir.mkdir(parents=True, exist_ok=False)
    progress("START V68 6 execution policies x 10 sessions; 60 audit cases "
             "6 original source hashes verified; paid_requests=0 broker_orders=0")
    manifest = []
    total = len(POLICIES) * len(rows)
    done = 0
    milestone = 10
    for lag, adverse in POLICIES:
        policy_id = f"lag{lag}s_limit{adverse.replace('.', 'p')}pct"
        cases = []
        counts = Counter()
        reasons = Counter()
        closed_sum = Decimal("0")
        baseline_confirmations = 0
        for row in rows:
            day = row["session"]
            scenario = replay(
                row["standalone_replay_report"]["signal"],
                sources.get(day),
                starting_cash="25000", lag_seconds=lag,
                max_adverse_pct=adverse,
            )
            if scenario.get("fingerprint") != _fingerprint({
                k: v for k, v in scenario.items() if k != "fingerprint"
            }):
                raise V68Error("V68_REPLAY_FINGERPRINT_INVALID")
            if (scenario.get("actual_fills") != 0
                    or scenario.get("publication_verified") is not False
                    or scenario.get("valid_historical_alpha") is not False
                    or scenario.get("session") != day
                    or scenario.get("source_query_id") !=
                        row["standalone_replay_report"]["source_query_id"]
                    or scenario.get("source_sha256") !=
                        row["standalone_replay_report"]["source_sha256"]):
                raise V68Error("V68_REPLAY_SOURCE_OR_AUTHORITY_DRIFT")
            if lag == 1 and adverse == "1":
                if scenario["fingerprint"] != row["standalone_replay_report"]["fingerprint"]:
                    raise V68Error("V68_ORIGINAL_1S_1PCT_REPLAY_NOT_REPRODUCED")
                baseline_confirmations += 1
            counts[scenario["status"]] += 1
            reasons[scenario["censor_reason"] or "RESOLVED_OR_NOT_REQUIRED"] += 1
            if scenario["status"] == "CLOSED_QUOTE_REFERENCE":
                if scenario["trade_net_pnl"] is None:
                    raise V68Error("V68_CLOSED_TRADE_HAS_NO_PNL")
                closed_sum += Decimal(scenario["trade_net_pnl"])
            # Full, unabridged original observations/reasons/events are
            # retained for every policy, including censor or no-entry cases.
            cases.append({
                "session": day,
                "source_sha256": sources[day]["source_sha256"] if day in sources else None,
                "replay": scenario,
            })
            done += 1
            while milestone <= 100 and 100 * done >= milestone * total:
                progress(f"PROGRESS_{milestone}PCT V68 cases={done}/{total} "
                         f"last_day={day} policy={policy_id} provider_calls=0")
                milestone += 10
        document = signed({
            "contract": CONTRACT, "policy_id": policy_id,
            "lag_seconds": lag, "max_adverse_pct": adverse,
            "original_v67_fingerprint": v67["fingerprint"],
            "original_v65_fingerprint": v65["fingerprint"],
            "status_counts": dict(sorted(counts.items())),
            "censor_reason_counts": dict(sorted(reasons.items())),
            "closed_trade_pnl_sum_not_cumulative_account": str(closed_sum.quantize(Decimal(".01"))),
            "baseline_replay_fingerprints_reproduced": baseline_confirmations,
            "session_reports": cases, "provider_requests": 0,
            "broker_orders": 0, "historical_fills_verified": False,
            "posthoc_sensitivity_not_out_of_sample_alpha": True,
            "cash_chaining_disallowed_when_any_open_position_unresolved": True,
        })
        file_name = f"scenario_{policy_id}.json.gz"
        gzip_sha = write_gzip_once(outdir / file_name, document)
        manifest.append({
            "policy_id": policy_id, "file": file_name,
            "gzip_sha256": gzip_sha, "report_fingerprint": document["fingerprint"],
            "status_counts": document["status_counts"],
            "censor_reason_counts": document["censor_reason_counts"],
            "closed_trade_pnl_sum_not_cumulative_account":
                document["closed_trade_pnl_sum_not_cumulative_account"],
            "baseline_replay_fingerprints_reproduced": baseline_confirmations,
        })
        progress(f"STAGE_PASS V68 policy={policy_id} statuses={dict(counts)} "
                 f"censored={dict(reasons)} file={file_name}")
    summary = signed({
        "contract": CONTRACT, "status": "COMPLETE_OFFLINE_SENSITIVITY_CENSUS",
        "original_v67_fingerprint": v67["fingerprint"],
        "original_v65_fingerprint": v65["fingerprint"],
        "verified_original_option_sources": len(sources),
        "policies": manifest, "policy_count": len(POLICIES),
        "scenario_session_replays": done,
        "default_1s_1pct_replay_exactly_reproduced": True,
        "hypotheses_not_holdout_tested": True,
        "provider_requests": 0, "broker_orders": 0,
        "actual_fills": 0, "historical_profitability_validated": False,
        "posthoc_source_window_not_model_selection_authority": True,
        "unresolved_position_must_not_be_assigned_zero_pnl": True,
    })
    with (outdir / "summary.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    progress(f"COMPLETE V68 scenarios={done} option_sources={len(sources)} "
             f"output={outdir / 'summary.json'} paid_requests=0 alpha_proven=False")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v67-summary", required=True, type=Path)
    parser.add_argument("--refreshed-v65", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        run(args.v67_summary, args.refreshed_v65, args.output_dir)
        return 0
    except Exception as exc:
        announce(f"STOPPED V68 error_class={type(exc).__name__} "
                 "no_provider_requests=True no_broker_orders=True")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
