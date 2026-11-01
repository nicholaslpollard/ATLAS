from __future__ import annotations

"""V101: causal, source-linked news-activity filters and offline V99 CALL replay.

Uses original signed V84/V86 quote outcomes, recycles original V90 account math,
never issues a provider or broker request; May-Aug 2026 news partitions sealed.
"""
import argparse
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
import gzip
import hashlib
import json
import os
from pathlib import Path

CONTRACT = "atlas-v101-accepted-pit-news-metadata-filtered-v99-quote-replay-v1"
GATES = ("NEWS_24H_AT_LEAST_1", "NEWS_7D_AT_LEAST_3", "NEWS_24H_ZERO")
NEWS_PERIODS = ("2021_full", "2022_full", "2023_full", "2024_full", "2025_h2", "2026_janapr")

class V101Error(ValueError):
    pass


def accepted_news_to_april_2026(settings, *, progress=None):
    """SHA-validate/read Dec 2020-Apr 2026 only; do not open protected months."""
    import duckdb
    from packages.data.offline_multiyear_news_context_v1 import (
        OfflineMultiYearNewsContext, verified_news_partition_paths,
        effective_pit_available_at, _timestamp, _symbol_list,
    )
    from packages.data.offline_news_context_v1 import OfflineNewsContext

    cutoff = date(2026, 4, 1)
    paths, lineage = verified_news_partition_paths(
        settings, last_month=cutoff, progress=progress)
    if (lineage.get("months") != 65
            or lineage.get("last_source_day") != cutoff.isoformat()):
        raise V101Error("V101_PIT_NEWS_SOURCE_PARTITION_CUTOFF_INVALID")
    chosen = {}
    scanned = 0
    relevant = 0
    con = duckdb.connect(database=":memory:")
    try:
        con.execute("PRAGMA threads=4")
        con.execute("SELECT article_id, created_at, updated_at, symbols_json "
                    "FROM read_parquet(?, hive_partitioning=false)", [paths])
        while batch := con.fetchmany(8192):
            for article_id, created, updated, symbols_json in batch:
                scanned += 1
                if not isinstance(article_id, str) or not article_id:
                    raise V101Error("V101_NEWS_ARTICLE_ID_INVALID")
                effective = effective_pit_available_at(
                    _timestamp(created), _timestamp(updated))
                if "SPY" not in _symbol_list(symbols_json):
                    continue
                relevant += 1
                candidate = (effective, ("SPY",))
                if article_id not in chosen or candidate > chosen[article_id]:
                    chosen[article_id] = candidate
    finally:
        con.close()
    timestamps = [effective for effective, _ in chosen.values()]
    return OfflineMultiYearNewsContext(
        OfflineNewsContext({"SPY": timestamps}, lineage, scanned),
        coverage_end=date(2026, 4, 30),
        duplicate_article_rows=relevant-len(chosen),
    )


def gate_decision(period, decision_at_et, source_query_id, context):
    from scripts.run_spy_v99_49_call_variant_quote_economics import COHORTS
    instant = datetime.fromisoformat(decision_at_et)
    bounds = {name: (start, end) for name, start, end in COHORTS}
    if (instant.tzinfo is None or period not in bounds
            or not bounds[period][0] <= instant.date().isoformat() <= bounds[period][1]):
        raise V101Error("V101_SIGNAL_CLOCK_INVALID")
    if instant.date() < date(2021, 1, 1) or period not in NEWS_PERIODS:
        return {"status": "NEWS_SOURCE_OUTSIDE_VERIFIED_YEAR_SCOPE",
                "counts": None, "source_query_id": source_query_id}
    utc = instant.astimezone(UTC)
    result = context.prior_counts("SPY", decision_utc=utc)
    if (result.get("coverage_status") != "VERIFIED_SOURCE_COVERAGE_AT_DECISION"
            or result.get("decision_cutoff_utc") != utc.isoformat()
            or result.get("authority", {}).get("provider_requests") != 0
            or result.get("authority", {}).get("news_text_or_sentiment_alpha") is not False):
        return {"status": "NEWS_SOURCE_NOT_ASOF_QUALIFIED",
                "counts": None, "source_query_id": source_query_id}
    a, b = (result.get("unique_articles_available_prior_24h"),
            result.get("unique_articles_available_prior_7d"))
    if any(type(v) is not int or v < 0 for v in (a, b)) or b < a:
        raise V101Error("V101_INCONSISTENT_NEWS_COUNT")
    return {"status": "QUALIFIED_NEWS_METADATA", "counts": {"24h": a, "7d": b},
            "source_query_id": source_query_id, "decision_cutoff_utc": utc.isoformat()}


def passes(gate, record):
    if gate not in GATES:
        raise V101Error("V101_UNREGISTERED_NEWS_GATE")
    if record["status"] != "QUALIFIED_NEWS_METADATA":
        return None
    counts = record["counts"]
    return (counts["24h"] >= 1 if gate == "NEWS_24H_AT_LEAST_1"
            else counts["7d"] >= 3 if gate == "NEWS_7D_AT_LEAST_3"
            else counts["24h"] == 0)


def verify_journal(source_root, item, v100, v99):
    path = source_root / item["relative_path"]
    if not path.is_file() or path.is_symlink():
        raise V101Error("V101_ORIGINAL_TRIAL_JOURNAL_MISSING")
    compressed = path.read_bytes()
    if (len(compressed) != item["compressed_bytes"]
            or hashlib.sha256(compressed).hexdigest() != item["compressed_sha256"]):
        raise V101Error("V101_ORIGINAL_COMPRESSED_TRIAL_SHA_CHANGED")
    original = gzip.decompress(compressed)
    if len(original) != item["raw_bytes"]:
        raise V101Error("V101_ORIGINAL_RAW_TRIAL_BYTES_CHANGED")
    doc = v100.check(json.loads(original), v99+"-source-linked-quote-trials-v1")
    if (doc["fingerprint"] != item["source_trial_sha"]
            or doc["original_source_query_id"] != item["query_id"]
            or doc["original_source_sha256"] is None
            or doc["provider_requests"] != 0 or doc["broker_orders"] != 0):
        raise V101Error("V101_TRIAL_SOURCE_PARENT_SHA_CHANGED")
    return doc


def original_pairs(doc, *, v100):
    pairs = {}
    groups = doc["original_24_variant_economic_trials"]
    if len(groups) != 6:
        raise V101Error("V101_ORIGINAL_POLICY_LAG_GRID_DRIFT")
    for group in groups:
        trial = v100.check(group["original_v84_trial"])
        if len(group["original_v86_exit_rechecks"]) != 4:
            raise V101Error("V101_ORIGINAL_EXIT_DWELL_GRID_DRIFT")
        for outcome in group["original_v86_exit_rechecks"]:
            v100.check(outcome)
            if (outcome["original_trial_sha"] != trial["fingerprint"]
                    or outcome["session"] != trial["session"]
                    or outcome["strategy"] != trial["strategy"]
                    or outcome["policy"] != trial["policy"]
                    or outcome["lag_seconds"] != trial["lag_seconds"]
                    or trial["actual_broker_fills"] != 0
                    or outcome["actual_broker_fills"] != 0):
                raise V101Error("V101_ORIGINAL_EXIT_PARENT_OR_CLOCK_DRIFT")
            key = (trial["policy"], trial["lag_seconds"], outcome["limit_rest_seconds"])
            if key in pairs:
                raise V101Error("V101_DUPLICATE_EXECUTION_VARIANT")
            pairs[key] = (trial, outcome)
    if len(pairs) != 24:
        raise V101Error("V101_ORIGINAL_24_QUOTE_VARIANTS_MISSING")
    return pairs


def audit_v90_cash(book):
    """Reconcile original V90 cash events without inventing unresolved equity."""
    try:
        def cash(value):
            v = Decimal(str(value))
            if not v.is_finite():
                raise ValueError("nonfinite cash")
            return v

        pnl = cash(book["closed_trade_stressed_quote_pnl_usd"])
        weekly = sum((cash(v) for v in book["stressed_week_pnl_usd"].values()), Decimal(0))
        monthly = sum((cash(v) for v in book["stressed_month_pnl_usd"].values()), Decimal(0))
        start = cash(book["starting_cash_usd"])
        end = cash(book["ending_stressed_quote_cash_usd"])
        debit = Decimal(0)
        credit = Decimal(0)
        unknown = 0
        latest_entry = None
        latest_unknown_debit = None
        for event in book["all_considered_and_blocked_events"]:
            kind = event["event"]
            if kind == "ENTRY_ASK_REFERENCE_ONLY":
                value = cash(event["debit_usd"])
                if value <= 0:
                    raise ValueError("invalid entry debit")
                debit += value
                latest_entry = value
            elif kind == "MODELED_EXIT_QUOTE_CREDIT":
                value = cash(event["two_pct_haircut_credit_usd"])
                if value < 0:
                    raise ValueError("invalid exit credit")
                credit += value
                latest_entry = None
            elif kind == "UNKNOWN_EXPIRY_OR_EXERCISE_CASH":
                unknown += 1
                latest_unknown_debit = latest_entry
        unresolved = book["unresolved_exercise_or_expiry_cash"]
        terminal = book["terminal_equity_known_if_flat_usd"]
        if (type(unresolved) is not bool or pnl != weekly or pnl != monthly
                or end - start != credit - debit):
            raise ValueError("weekly/monthly or debit/credit flow mismatch")
        if unresolved:
            if (unknown != 1 or latest_unknown_debit is None or terminal is not None
                    or pnl - (end - start) != latest_unknown_debit):
                raise ValueError("unresolved option premium reconciliation mismatch")
        elif (unknown != 0 or terminal is None or cash(terminal) != end
              or end - start != pnl):
            raise ValueError("flat cash reconciliation mismatch")
        return {"unresolved": unresolved, "remaining_entry_premium_usd":
                str(latest_unknown_debit) if unresolved else None}
    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
        raise V101Error("V101_GATED_CASH_ARITHMETIC_INVALID") from exc


def filtered_cash(pairs, *, missing, coverage_known, simulate, scope, policy, lag, dwell):
    if not coverage_known:
        return {"status": "NEWS_COVERAGE_UNQUALIFIED", "cash_equity_known": False,
                "quote_pnl_usd": None, "original_account_sha": None,
                "original_missing_source_candidates": len(missing)}
    book = simulate(pairs, scope=scope, policy=policy,
                    lag_seconds=lag, dwell_seconds=dwell)
    from packages.simulation.spy_v90_six_family_capital_ledger import verified as verified90
    if not verified90(book) or book["actual_broker_orders"] != 0:
        raise V101Error("V101_SOURCE_LINKED_REPLAY_LEDGER_INVALID")
    # Original V90 counts debits for an unresolved option; that premium is
    # not a realized loss, so net cash != closed-trade PnL until flat.
    cash_audit = audit_v90_cash(book)
    complete = not missing and not book["unresolved_exercise_or_expiry_cash"]
    return {"status": "COMPLETE_QUOTE_CASH" if complete else "SOURCE_OR_SETTLEMENT_CENSORED",
            "cash_equity_known": complete,
            "quote_pnl_usd": str(pnl) if complete else None,
            "original_missing_source_candidates": len(missing),
            "original_account_sha": book["fingerprint"],
            "unresolved_open_entry_premium_usd": cash_audit["remaining_entry_premium_usd"],
            "account": book, "original_quote_pairs_considered": len(pairs)}


def signed_write(path, item, v100):
    record = {**item, "fingerprint": v100._fingerprint(item)}
    payload = (json.dumps(record, sort_keys=True, separators=(",", ":"),
                          allow_nan=False)+"\n").encode("utf-8")
    if path.suffix == ".gz":
        payload = gzip.compress(payload, compresslevel=6, mtime=0)
    with path.open("xb") as out:
        out.write(payload)
        out.flush()
        os.fsync(out.fileno())
    return {"sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload), "signed_fingerprint": record["fingerprint"]}


def run(v99_dir, output_dir, *, reporter=print):
    from packages.core.settings import load_settings
    from packages.simulation.spy_v90_six_family_capital_ledger import simulate
    from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
    from scripts import run_spy_v100_v99_independent_wfo_audit as v100
    from scripts.run_spy_v97b_49_variant_call_source_union_preview import params, BASELINES
    from scripts.run_spy_v99_49_call_variant_quote_economics import DEFINITIONS, CONTRACT as V99

    if output_dir.exists() or output_dir.is_symlink() or not v99_dir.is_dir():
        raise V101Error("V101_INVALID_INPUT_OR_OUTPUT_DIRECTORY")
    summary = v100.source(v99_dir/"summary.json", V99)
    matrix = v100.source(v99_dir/"eight_period_exploratory_matrix.json",
                         V99+"-eight-period-account-robustness-v1")
    manifest = v100.source(v99_dir/"trial_archive_manifest.json",
                           V99+"-signed-trial-archive-manifest-v1")
    _, audit = v100.verify_every_ledger(v99_dir, summary, matrix, manifest, full_journals=True)
    if (audit["account_scenarios_sha_verified"] != 10800
            or audit["signed_source_archive_provenance"]["archive_sha_checked"] != 630
            or len(DEFINITIONS) != 24):
        raise V101Error("V101_ORIGINAL_V99_AUDIT_POPULATION_CHANGED")
    settings = load_settings(Path(__file__).resolve().parents[1], "development")
    news = accepted_news_to_april_2026(settings)
    if (news.lineage.get("months") != 65
            or news.lineage.get("accepted_v2_fingerprint") is None):
        raise V101Error("V101_ACCEPTED_NEWS_CORPUS_LINEAGE_UNQUALIFIED")
    grid = params()
    if len(grid) != 49:
        raise V101Error("V101_REGISTERED_49_CALL_ENTRY_VARIANTS_CHANGED")
    baseline = {}
    for var in grid:
        if tuple(var["parameters"]) == BASELINES[var["strategy"]]:
            if var["strategy"] in baseline:
                raise V101Error("V101_DUPLICATE_FAMILY_BASELINE")
            baseline[var["strategy"]] = var["trial_id"]
    if len(baseline) != 6:
        raise V101Error("V101_ALL_SIX_FAMILY_BASELINES_REQUIRED")
    trial_scope = {var["trial_id"]: var["strategy"] for var in grid}
    if (len(manifest["source_tape_family_journals"]) != 630
            or any(row["cohort"] not in set(v100.ALL_PERIODS)
                   for row in manifest["source_tape_family_journals"])):
        raise V101Error("V101_UNKNOWN_HISTORICAL_SOURCE_COHORT")

    opportunities = []
    bucket = defaultdict(list)
    decision_index = {}
    gate_stats = Counter()
    unknown_coverage = set()
    for item in manifest["source_tape_family_journals"]:
        doc = verify_journal(v99_dir, item, v100, V99)
        dec = v100.check(doc["original_asof_bullish_derived_decision"])
        if (dec["direction"] != "CALL" or dec["session"] > "2026-04-30"
                or dec["news_signal_used"] is not False
                or dec["strategy_id"] != item["family"]
                or dec["original_stock_source_sha256"] is None):
            raise V101Error("V101_NONCAUSAL_OR_NONCALL_ORIGINAL_DECISION")
        cohort = item["cohort"]
        if cohort not in NEWS_PERIODS:
            continue
        instant = dec["decision_at_et"]
        key = (item["query_id"], dec["strategy_id"], dec["session"], instant)
        if key not in decision_index:
            decision_index[key] = gate_decision(cohort, instant, item["query_id"], news)
        context = decision_index[key]
        variants = doc["variant_trial_ids"]
        if (not variants or len(set(variants)) != len(variants)
                or any(trial_scope.get(x) != dec["strategy_id"] for x in variants)):
            raise V101Error("V101_ORIGINAL_VARIANT_FAMILY_BINDING_CHANGED")
        original = original_pairs(doc, v100=v100)
        for gate in GATES:
            accept = passes(gate, context)
            gate_stats[(cohort, gate, "ACCEPT" if accept else
                        "REJECT" if accept is False else "NEWS_UNKNOWN")] += len(variants)
            if accept is None:
                for trial_id in variants:
                    unknown_coverage.add((cohort, gate, trial_id))
            opportunities.append({
                "cohort": cohort, "date": dec["session"],
                "decision_at_et": instant, "trial_ids": variants,
                "strategy": dec["strategy_id"], "source_query_id": item["query_id"],
                "original_source_sha256": doc["original_source_sha256"],
                "original_quote_journal_sha": doc["fingerprint"],
                "gate": gate, "gate_status": context["status"],
                "counts": context.get("counts"), "included": accept,
                "reason": ("PIT_NEWS_FILTER_PASSED" if accept else
                           "PIT_NEWS_FILTER_REJECTED" if accept is False else
                           "NEWS_SOURCE_NOT_QUALIFIED"),
            })
            if accept:
                for trial_id in variants:
                    for policy, lag, dwell in DEFINITIONS:
                        bucket[(cohort, gate, trial_id, policy, lag, dwell)].append(
                            original[(policy, lag, dwell)])

    original_rows = {}
    for name in NEWS_PERIODS:
        doc = v100.source(v99_dir/f"{name}_capital_scenarios.json",
                          V99+"-1200-scenarios-cohort-v1")
        original_rows[name] = {
            (x["trial_id"], x["policy"], x["lag_seconds"], x["limit_rest_seconds"]): x
            for x in doc["capital_scenarios"]}
        if len(original_rows[name]) != 1200:
            raise V101Error("V101_ORIGINAL_ACCOUNT_SCENARIO_GRID_DRIFT")

    output_dir.mkdir(parents=True, exist_ok=False)
    results = defaultdict(dict)
    files = []
    for cohort in NEWS_PERIODS:
        for gate in GATES:
            scenarios = []
            for trial_id in list(trial_scope)+["V99_BASELINE_ALL_SIX_CALL_ONLY"]:
                scope = trial_scope.get(trial_id, "all_six_new_families")
                for policy, lag, dwell in DEFINITIONS:
                    if trial_id in trial_scope:
                        selected = bucket[(cohort, gate, trial_id, policy, lag, dwell)]
                    else:
                        selected = [pair for base_id in baseline.values()
                                    for pair in bucket[(cohort, gate, base_id, policy, lag, dwell)]]
                    original = original_rows[cohort][(trial_id, policy, lag, dwell)]
                    missing = original["qualified"]["unqualified_causal_candidate_sources"]
                    if any(x["session"] > "2026-04-30" for x in missing):
                        raise V101Error("V101_PROTECTED_MASTER_HOLDOUT_SOURCE")
                    coverage_known = not any(
                        (cohort, gate, base_id) in unknown_coverage
                        for base_id in (baseline.values() if trial_id not in trial_scope
                                        else (trial_id,)))
                    result = filtered_cash(
                        selected, missing=missing, coverage_known=coverage_known,
                        simulate=simulate, scope=scope, policy=policy, lag=lag, dwell=dwell)
                    scenarios.append({"trial_id": trial_id, "gate": gate,
                                      "strategy": scope, "policy": policy,
                                      "lag_seconds": lag, "limit_rest_seconds": dwell,
                                      "result": result})
                    if result["cash_equity_known"]:
                        results[(gate, trial_id, policy, lag, dwell)][cohort] = result["quote_pnl_usd"]
            if len(scenarios) != 1200:
                raise V101Error("V101_SOURCE_LINKED_NEWS_ACCOUNT_GRID_NOT_RECTANGULAR")
            path = output_dir/f"{cohort}_{gate}_scenario_ledgers.json.gz"
            info = signed_write(path, {
                "contract": CONTRACT+"-cohort-1200-gated-original-scenarios-v1",
                "original_v99_summary_sha": summary["fingerprint"],
                "cohort": cohort, "gate": gate, "scenarios": scenarios,
                "provider_requests": 0, "broker_orders": 0,
            }, v100)
            files.append({"relative_path": path.name, **info})
            reporter(f"V101 {cohort} {gate} original_ledgers=1200 "
                     f"complete={sum(x['result']['cash_equity_known'] for x in scenarios)} "
                     "provider_calls=0 broker_orders=0")
    scenarios_matrix = []
    for gate in GATES:
        for trial_id in list(trial_scope)+["V99_BASELINE_ALL_SIX_CALL_ONLY"]:
            for policy, lag, dwell in DEFINITIONS:
                row = results[(gate, trial_id, policy, lag, dwell)]
                complete = len(row) == len(NEWS_PERIODS)
                total = sum((Decimal(v) for v in row.values()), Decimal(0))
                scenarios_matrix.append({
                    "gate": gate, "trial_id": trial_id,
                    "policy": policy, "lag_seconds": lag,
                    "limit_rest_seconds": dwell,
                    "pnl_by_complete_cohort": {k: row[k] for k in NEWS_PERIODS if k in row},
                    "missing_or_censored_cohorts": [x for x in NEWS_PERIODS if x not in row],
                    "complete_six_cohorts": complete,
                    "nominal_six_period_pnl_usd_if_complete": str(total) if complete else None,
                    "positive_in_all_six": complete and all(Decimal(v) > 0 for v in row.values()),
                })
    comparison = signed_write(output_dir/"scenario_comparison.json", {
        "contract": CONTRACT+"-six-news-covered-cohort-comparison-v1",
        "original_v99_summary_sha": summary["fingerprint"],
        "news_lineage": news.lineage,
        "gates": list(GATES), "historical_periods": list(NEWS_PERIODS),
        "scenarios": scenarios_matrix,
        "source_incomplete_not_zero_quote_profit": True,
        "2020_and_pre2021_news_unavailable_not_labeled_zero": True,
        "not_an_unseen_holdout_or_independently_validated_alpha": True,
        "provider_requests": 0, "broker_orders": 0,
    }, v100)
    files.append({"relative_path": "scenario_comparison.json", **comparison})
    event_file = signed_write(output_dir/"opportunity_news_gate_decisions.json.gz", {
        "contract": CONTRACT+"-all-source-ready-opportunity-news-filter-decisions-v1",
        "original_v99_trial_manifest_sha": manifest["fingerprint"],
        "news_lineage": news.lineage, "events": opportunities,
        "provider_requests": 0, "broker_orders": 0,
    }, v100)
    files.append({"relative_path": "opportunity_news_gate_decisions.json.gz", **event_file})
    signed_write(output_dir/"summary.json", {
        "contract": CONTRACT,
        "original_V99_summary_sha": summary["fingerprint"],
        "original_V99_trial_manifest_sha": manifest["fingerprint"],
        "original_V99_eightperiod_matrix_sha": matrix["fingerprint"],
        "v100_audited_original_cash_ledgers": audit["account_scenarios_sha_verified"],
        "v100_audited_original_trial_journals":
            audit["signed_source_archive_provenance"]["archive_sha_checked"],
        "accepted_news_lineage_sha": _fingerprint(news.lineage),
        "news_source_covered_qualifying_years": list(NEWS_PERIODS),
        "news_gate_counts": {"|".join(k): v for k, v in sorted(gate_stats.items())},
        "news_gated_50_x_24_x_3_x_6_replayed_accounts": len(NEWS_PERIODS)*len(GATES)*1200,
        "full_six_period_complete_configurations":
            sum(x["complete_six_cohorts"] for x in scenarios_matrix),
        "positive_in_all_six_if_complete": sum(x["positive_in_all_six"] for x in scenarios_matrix),
        "files_with_original_byte_sha": files,
        "no_master_holdout_access": True,
        "historical_quote_reference_not_verified_order_fills": True,
        "not_an_unseen_holdout_or_independently_validated_alpha": True,
        "provider_requests": 0, "broker_orders": 0,
    }, v100)
    reporter("V101 COMPLETE PIT-news original quote replay "
             f"new_filtered_account_ledgers={len(NEWS_PERIODS)*len(GATES)*1200} "
             "provider_calls=0 broker_orders=0")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v99-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        run(args.v99_dir, args.output_dir)
        return 0
    except (OSError, ValueError, TypeError, KeyError, EOFError) as exc:
        print(f"STOP V101 {type(exc).__name__} detail={str(exc)[:220]} "
              "provider_requests=0 broker_orders=0", flush=True)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
