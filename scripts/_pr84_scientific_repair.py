from __future__ import annotations

from pathlib import Path


def replace_exact(text: str, old: str, new: str, label: str, expected: int = 1) -> str:
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{label}: expected {expected} occurrence(s), found {count}")
    return text.replace(old, new)


engine_path = Path("packages/backtesting/successor_development_engine.py")
engine = engine_path.read_text(encoding="utf-8")
engine = replace_exact(
    engine,
    "from packages.backtesting.reference_strategy_runner import _universe_decision",
    "from packages.backtesting.reference_strategy_runner import _universe_decision, reference_signal_mask",
    "reference signal mask import",
)
engine = replace_exact(
    engine,
    "from packages.backtesting.successor_development_outcomes import (\n    SuccessorDevelopmentOutcomeError,\n    evaluate_daily_diagnostic_outcome,\n    simulate_successor_intraday_outcome,\n)",
    "from packages.backtesting.successor_development_outcomes import (\n    DEVELOPMENT_END,\n    DEVELOPMENT_START,\n    SuccessorDevelopmentOutcomeError,\n    evaluate_daily_diagnostic_outcome,\n    simulate_successor_intraday_outcome,\n)",
    "development scope imports",
)
old_daily = '''            for direction, trigger_feature, retain_reference_universe in pairs:\n                if trigger_feature not in instrument.columns:\n                    raise SuccessorDevelopmentOutcomeError(\n                        f"daily trigger feature missing: {route.policy_id}:{trigger_feature}"\n                    )\n                fired_positions = [\n                    position\n                    for position, value in enumerate(instrument[trigger_feature].tolist())\n                    if not pd.isna(value) and float(value) == 1.0\n                ]\n                for position in fired_positions:\n                    row = instrument.iloc[position]\n                    universe_eligible = True\n                    universe_reasons: tuple[str, ...] = ("SOURCE_COMMON_STOCK_PIT_IDENTITY_ACCEPTED",)\n                    if retain_reference_universe:\n                        universe_eligible, universe_reasons = _universe_decision(row)\n                    outcome = evaluate_daily_diagnostic_outcome(\n'''
new_daily = '''            for direction, trigger_feature, retain_reference_universe in pairs:\n                if trigger_feature not in instrument.columns:\n                    raise SuccessorDevelopmentOutcomeError(\n                        f"daily trigger feature missing: {route.policy_id}:{trigger_feature}"\n                    )\n                if retain_reference_universe:\n                    fired = reference_signal_mask(instrument, specification)\n                    fired_positions = fired[fired].index.tolist()\n                else:\n                    fired_positions = [\n                        position\n                        for position, value in enumerate(instrument[trigger_feature].tolist())\n                        if not pd.isna(value) and float(value) == 1.0\n                    ]\n                for position in fired_positions:\n                    row = instrument.iloc[position]\n                    signal_session = pd.Timestamp(row["session_date"]).date()\n                    if signal_session < DEVELOPMENT_START or signal_session > DEVELOPMENT_END:\n                        continue\n                    # All 18 daily routes share the accepted executable common-universe\n                    # decision. Strategy firing remains independent of this disposition.\n                    universe_eligible, universe_reasons = _universe_decision(row)\n                    outcome = evaluate_daily_diagnostic_outcome(\n'''
engine = replace_exact(engine, old_daily, new_daily, "daily firing/universe block")
engine_path.write_text(engine, encoding="utf-8")

runner_path = Path("packages/backtesting/successor_development_runner.py")
runner = runner_path.read_text(encoding="utf-8")
runner = replace_exact(
    runner,
    "from datetime import date",
    "from datetime import date, timedelta",
    "runner timedelta import",
)
runner = replace_exact(
    runner,
    "BENCHMARK_WORKER_SHAPES = (4, 6, 8)\n",
    '''BENCHMARK_WORKER_SHAPES = (4, 6, 8)\nSPY_BENCHMARK_AGGREGATION_CONTRACT = (\n    "atlas-successor-spy-benchmark-v1-accepted-minute-exact-final-regular-bar"\n)\nSPY_BENCHMARK_AGGREGATION_FINGERPRINT = canonical_sha256(\n    {\n        "contract": SPY_BENCHMARK_AGGREGATION_CONTRACT,\n        "symbol": "SPY",\n        "source": "ACCEPTED_B35_EXACT_NATIVE_MINUTE_SOURCE",\n        "session_value": "EXACT_REGULAR_CLOSE_MINUS_ONE_MINUTE_BAR_CLOSE",\n        "missing_or_duplicate_final_bar": "FAIL_CLOSED",\n        "source_start": DEVELOPMENT_START.isoformat(),\n        "source_end": DEVELOPMENT_END.isoformat(),\n        "provider_calls": 0,\n    }\n)\nSOURCE_HISTORY_POLICY = {\n    "accepted_source_start": DEVELOPMENT_START.isoformat(),\n    "evaluation_start": DEVELOPMENT_START.isoformat(),\n    "predevelopment_warmup_available": False,\n    "warmup_policy": "ACCUMULATE_INSIDE_DEVELOPMENT_NO_INVENTED_PREHISTORY",\n    "unready_features": "REMAIN_UNAVAILABLE_UNTIL_REQUIRED_HISTORY_EXISTS",\n}\n''',
    "benchmark/source-history constants",
)
runner = replace_exact(
    runner,
    '''        "grouping": {\n            "daily": "64_COMPLETE_INSTRUMENT_HISTORY_SHA256_BUCKETS",\n            "minute": "ACCEPTED_B35_EXACT_SORTED_NATIVE_PLAN_SYMBOL_TUPLE_GROUPS",\n            "execution_profile_changes_membership": False,\n        },\n''',
    '''        "grouping": {\n            "daily": "64_COMPLETE_INSTRUMENT_HISTORY_SHA256_BUCKETS",\n            "minute": "ACCEPTED_B35_EXACT_SORTED_NATIVE_PLAN_SYMBOL_TUPLE_GROUPS",\n            "execution_profile_changes_membership": False,\n        },\n        "source_history_policy": SOURCE_HISTORY_POLICY,\n        "universe_policy": {\n            "daily": "REFERENCE_COMMON_EXECUTABLE_UNIVERSE_ALL_18_ROUTES",\n            "minute": "INHERIT_ACCEPTED_B35_NATIVE_PLAN_UNIVERSE_ALL_10_ROUTES",\n            "minute_retained_baseline_universe_may_be_rewritten": False,\n        },\n        "spy_benchmark": {\n            "contract": SPY_BENCHMARK_AGGREGATION_CONTRACT,\n            "fingerprint": SPY_BENCHMARK_AGGREGATION_FINGERPRINT,\n            "source": "ACCEPTED_B35_EXACT_NATIVE_MINUTE_SOURCE",\n        },\n''',
    "run identity source policy",
)
prepare_marker = '''def prepare_successor_development_inputs(\n    settings: AtlasSettings,\n    *,\n    identity: SuccessorDevelopmentRunIdentity,\n) -> PreparedSuccessorInputs:\n'''
helper = '''def build_spy_benchmark_from_accepted_minute_source(\n    source: B35DevelopmentMinuteSource,\n    minute_plan,\n) -> tuple[pd.DataFrame, dict[str, object]]:\n    """Derive same-session SPY close only from already accepted minute units.\n\n    The common-stock research-daily generation intentionally excludes ETFs, so SPY\n    cannot be sourced from that view. The exact native minute generation was already\n    hash-verified by the accepted preflight and contains the acquisition universe.\n    """\n\n    spy_units = tuple(unit for unit in minute_plan.units if "SPY" in unit.symbols)\n    if not spy_units:\n        raise SuccessorDevelopmentRunnerError("accepted minute source contains no SPY units")\n    pieces: list[pd.DataFrame] = []\n    for binding in spy_units:\n        frame = source.load_unit(\n            binding,\n            start_session=DEVELOPMENT_START,\n            end_session=DEVELOPMENT_END,\n        )\n        if frame.empty:\n            continue\n        selected = frame.loc[\n            (frame["symbol"].astype(str) == "SPY")\n            & (frame["session_segment"].astype(str) == "regular"),\n            ["session_date", "timestamp_utc", "close"],\n        ].copy()\n        if not selected.empty:\n            pieces.append(selected)\n    if not pieces:\n        raise SuccessorDevelopmentRunnerError("accepted minute source emitted no SPY regular bars")\n\n    bars = pd.concat(pieces, ignore_index=True)\n    bars["session_date"] = pd.to_datetime(bars["session_date"], errors="raise").dt.date\n    bars["timestamp_utc"] = pd.to_datetime(bars["timestamp_utc"], utc=True, errors="raise")\n    if bars.duplicated(["session_date", "timestamp_utc"]).any():\n        raise SuccessorDevelopmentRunnerError("SPY benchmark source contains duplicate minute keys")\n\n    expected_records: list[dict[str, object]] = []\n    for session in source.calendar.sessions_in_range(DEVELOPMENT_START, DEVELOPMENT_END):\n        _regular_open, regular_close = source.calendar.regular_open_close(session)\n        expected_records.append(\n            {\n                "session_date": session,\n                "timestamp_utc": pd.Timestamp(regular_close - timedelta(minutes=1)),\n            }\n        )\n    expected = pd.DataFrame(expected_records)\n    if expected.empty:\n        raise SuccessorDevelopmentRunnerError("SPY benchmark expected session calendar is empty")\n    closing = expected.merge(\n        bars,\n        on=["session_date", "timestamp_utc"],\n        how="left",\n        validate="one_to_one",\n        sort=False,\n    )\n    closing["close"] = pd.to_numeric(closing["close"], errors="coerce").astype("float64")\n    if closing["close"].isna().any() or (closing["close"] <= 0.0).any():\n        missing = closing.loc[closing["close"].isna(), "session_date"].astype(str).tolist()\n        raise SuccessorDevelopmentRunnerError(\n            "SPY benchmark is missing/invalid exact final regular minute for session(s): "\n            + ", ".join(missing[:10])\n        )\n    benchmark = closing[["session_date", "close"]].copy()\n    if benchmark["session_date"].duplicated().any() or len(benchmark) != len(expected):\n        raise SuccessorDevelopmentRunnerError("SPY benchmark session accounting drifted")\n    benchmark = benchmark.sort_values("session_date", kind="stable").reset_index(drop=True)\n    unit_bindings = [\n        {"unit_id": unit.unit_id, "canonical_sha256": unit.canonical_sha256}\n        for unit in spy_units\n    ]\n    report = {\n        "contract": SPY_BENCHMARK_AGGREGATION_CONTRACT,\n        "contract_fingerprint": SPY_BENCHMARK_AGGREGATION_FINGERPRINT,\n        "source_fingerprint": minute_plan.source_fingerprint,\n        "unit_binding_fingerprint": canonical_sha256(unit_bindings),\n        "unit_count": len(spy_units),\n        "session_count": len(benchmark),\n        "scope": [DEVELOPMENT_START.isoformat(), DEVELOPMENT_END.isoformat()],\n        "provider_calls": 0,\n        "protected_rows_read": 0,\n        "future_blind_rows_read": 0,\n    }\n    return benchmark, report\n\n\n'''
runner = replace_exact(runner, prepare_marker, helper + prepare_marker, "SPY benchmark helper insertion")
old_prepare = '''    daily_adapter = ReferenceV2DailyLakeAdapter(settings)\n    daily_result = daily_adapter.load(DEVELOPMENT_START, DEVELOPMENT_END)\n    frame = daily_result.bars.sort_values(\n        ["instrument_id", "session_date", "timestamp_utc"], kind="stable"\n    ).reset_index(drop=True)\n    if int(daily_result.report.get("protected_master_return_rows_read", -1)) != 0:\n        raise SuccessorDevelopmentRunnerError("daily DEVELOPMENT preparation read protected master rows")\n    spy = frame.loc[frame["ticker"].astype(str) == "SPY", ["session_date", "close"]].copy()\n    spy = spy.sort_values("session_date", kind="stable").reset_index(drop=True)\n    if spy.empty or spy["session_date"].duplicated().any():\n        raise SuccessorDevelopmentRunnerError("daily DEVELOPMENT source does not provide unique SPY benchmark sessions")\n    benchmark_path = input_root / "benchmark_spy.parquet"\n    benchmark_sha = _write_parquet_atomic(benchmark_path, spy)\n\n    instrument_ids = sorted(str(value) for value in frame["instrument_id"].unique())\n'''
new_prepare = '''    minute_source = B35DevelopmentMinuteSource(settings)\n    minute_plan = minute_source.plan(DEVELOPMENT_START, DEVELOPMENT_END)\n    spy, spy_report = build_spy_benchmark_from_accepted_minute_source(\n        minute_source, minute_plan\n    )\n    benchmark_path = input_root / "benchmark_spy.parquet"\n    benchmark_sha = _write_parquet_atomic(benchmark_path, spy)\n\n    daily_adapter = ReferenceV2DailyLakeAdapter(settings)\n    daily_result = daily_adapter.load(DEVELOPMENT_START, DEVELOPMENT_END)\n    frame = daily_result.bars.sort_values(\n        ["instrument_id", "session_date", "timestamp_utc"], kind="stable"\n    ).reset_index(drop=True)\n    if int(daily_result.report.get("protected_master_return_rows_read", -1)) != 0:\n        raise SuccessorDevelopmentRunnerError("daily DEVELOPMENT preparation read protected master rows")\n    if frame.empty:\n        raise SuccessorDevelopmentRunnerError("daily DEVELOPMENT source is empty")\n    observed_start = min(pd.to_datetime(frame["session_date"], errors="raise").dt.date)\n    if observed_start != DEVELOPMENT_START:\n        raise SuccessorDevelopmentRunnerError(\n            f"accepted daily source start drifted: {observed_start} != {DEVELOPMENT_START}"\n        )\n\n    instrument_ids = sorted(str(value) for value in frame["instrument_id"].unique())\n'''
runner = replace_exact(runner, old_prepare, new_prepare, "replace invalid research-daily SPY extraction")
runner = replace_exact(
    runner,
    '''                    "row_count": len(group),\n                },\n                operational={\n                    "parquet_locator": _project_locator(project_root, path),\n                    "parquet_sha256": parquet_sha,\n                    "benchmark_locator": _project_locator(project_root, benchmark_path),\n                    "benchmark_sha256": benchmark_sha,\n''',
    '''                    "row_count": len(group),\n                    "materialized_parquet_sha256": parquet_sha,\n                    "benchmark_sha256": benchmark_sha,\n                    "benchmark_contract_fingerprint": SPY_BENCHMARK_AGGREGATION_FINGERPRINT,\n                },\n                operational={\n                    "parquet_locator": _project_locator(project_root, path),\n                    "parquet_sha256": parquet_sha,\n                    "benchmark_locator": _project_locator(project_root, benchmark_path),\n                    "benchmark_sha256": benchmark_sha,\n''',
    "daily scientific derived hashes",
)
runner = replace_exact(
    runner,
    '''    minute_source = B35DevelopmentMinuteSource(settings)\n    minute_plan = minute_source.plan(DEVELOPMENT_START, DEVELOPMENT_END)\n    minute_groups = minute_symbol_groups(minute_plan.units)\n''',
    '''    minute_groups = minute_symbol_groups(minute_plan.units)\n''',
    "remove duplicate minute planning",
)
runner = replace_exact(
    runner,
    '''                    "unit_ids": [unit.unit_id for unit in units],\n                    "source_fingerprint": minute_plan.source_fingerprint,\n''',
    '''                    "unit_ids": [unit.unit_id for unit in units],\n                    "unit_bindings_sha256": canonical_sha256(\n                        [\n                            {"unit_id": unit.unit_id, "canonical_sha256": unit.canonical_sha256}\n                            for unit in units\n                        ]\n                    ),\n                    "source_fingerprint": minute_plan.source_fingerprint,\n''',
    "minute source binding hash",
)
runner = replace_exact(
    runner,
    '''        "minute_source_units": len(minute_plan.units),\n        "benchmark_locator": _project_locator(project_root, benchmark_path),\n        "benchmark_sha256": benchmark_sha,\n''',
    '''        "minute_source_units": len(minute_plan.units),\n        "source_history_policy": SOURCE_HISTORY_POLICY,\n        "benchmark_locator": _project_locator(project_root, benchmark_path),\n        "benchmark_sha256": benchmark_sha,\n        "benchmark_report": spy_report,\n''',
    "input summary benchmark report",
)
runner = replace_exact(
    runner,
    '''    if [item.unit_id for item in units] != list(scientific["unit_ids"]):\n        raise SuccessorDevelopmentRunnerError(f"minute unit ids drifted: {unit.token}")\n    symbols = tuple(str(value) for value in scientific["symbols"])\n''',
    '''    if [item.unit_id for item in units] != list(scientific["unit_ids"]):\n        raise SuccessorDevelopmentRunnerError(f"minute unit ids drifted: {unit.token}")\n    unit_bindings_sha256 = canonical_sha256(\n        [\n            {"unit_id": item.unit_id, "canonical_sha256": item.canonical_sha256}\n            for item in units\n        ]\n    )\n    if unit_bindings_sha256 != scientific.get("unit_bindings_sha256"):\n        raise SuccessorDevelopmentRunnerError(f"minute source bindings drifted: {unit.token}")\n    symbols = tuple(str(value) for value in scientific["symbols"])\n''',
    "minute worker source binding verification",
)
runner_path.write_text(runner, encoding="utf-8")
