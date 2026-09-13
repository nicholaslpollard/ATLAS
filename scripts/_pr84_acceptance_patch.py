from __future__ import annotations

from pathlib import Path


def replace_exact(text: str, old: str, new: str, label: str, expected: int = 1) -> str:
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{label}: expected {expected} occurrence(s), found {count}")
    return text.replace(old, new)


runner_path = Path("packages/backtesting/successor_development_runner.py")
runner = runner_path.read_text(encoding="utf-8")
runner = replace_exact(
    runner,
    '''        parquet = _resolve_project_locator(project, str(operational["parquet_locator"]))\n        benchmark = _resolve_project_locator(project, str(operational["benchmark_locator"]))\n        if _sha256_file(parquet) != str(operational["parquet_sha256"]):\n            raise SuccessorDevelopmentRunnerError(f"daily operational input hash drifted: {unit.token}")\n        if _sha256_file(benchmark) != str(operational["benchmark_sha256"]):\n            raise SuccessorDevelopmentRunnerError("SPY benchmark operational input hash drifted")\n''',
    '''        parquet = _resolve_project_locator(project, str(operational["parquet_locator"]))\n        benchmark = _resolve_project_locator(project, str(operational["benchmark_locator"]))\n        if str(operational.get("parquet_sha256") or "") != str(\n            scientific.get("materialized_parquet_sha256") or ""\n        ):\n            raise SuccessorDevelopmentRunnerError(\n                f"daily scientific/operational parquet binding drifted: {unit.token}"\n            )\n        if str(operational.get("benchmark_sha256") or "") != str(\n            scientific.get("benchmark_sha256") or ""\n        ):\n            raise SuccessorDevelopmentRunnerError(\n                f"daily scientific/operational benchmark binding drifted: {unit.token}"\n            )\n        if scientific.get("benchmark_contract_fingerprint") != SPY_BENCHMARK_AGGREGATION_FINGERPRINT:\n            raise SuccessorDevelopmentRunnerError(\n                f"daily benchmark contract drifted: {unit.token}"\n            )\n        if _sha256_file(parquet) != str(operational["parquet_sha256"]):\n            raise SuccessorDevelopmentRunnerError(f"daily operational input hash drifted: {unit.token}")\n        if _sha256_file(benchmark) != str(operational["benchmark_sha256"]):\n            raise SuccessorDevelopmentRunnerError("SPY benchmark operational input hash drifted")\n''',
    "daily scientific operational hash binding",
)
runner = replace_exact(
    runner,
    '''    root = root.resolve()\n    root.mkdir(parents=True, exist_ok=True)\n    _write_json(root / "run_contract.json", identity.contract)\n    invalidated = invalidate_corrupt_standalone_reuse(\n''',
    '''    root = root.resolve()\n    root.mkdir(parents=True, exist_ok=True)\n    _write_json(root / "run_contract.json", identity.contract)\n    source_input_manifest_path = inputs.input_root / "input_manifest.json"\n    if not source_input_manifest_path.is_file():\n        raise SuccessorDevelopmentRunnerError(\n            f"prepared input manifest is missing: {source_input_manifest_path}"\n        )\n    input_manifest = json.loads(source_input_manifest_path.read_text(encoding="utf-8"))\n    if not isinstance(input_manifest, dict):\n        raise SuccessorDevelopmentRunnerError("prepared input manifest is not a JSON object")\n    declared_input_fingerprint = str(input_manifest.get("fingerprint") or "")\n    unsigned_input_manifest = dict(input_manifest)\n    unsigned_input_manifest.pop("fingerprint", None)\n    actual_input_fingerprint = canonical_sha256(unsigned_input_manifest)\n    if (\n        declared_input_fingerprint != inputs.input_manifest_fingerprint\n        or actual_input_fingerprint != inputs.input_manifest_fingerprint\n    ):\n        raise SuccessorDevelopmentRunnerError("prepared input manifest fingerprint drifted")\n    _write_json(root / "input_manifest.json", input_manifest)\n    invalidated = invalidate_corrupt_standalone_reuse(\n''',
    "bind input manifest into run root",
)
runner_path.write_text(runner, encoding="utf-8")


test_path = Path("tests/test_successor_development_engine.py")
test = test_path.read_text(encoding="utf-8")
test = replace_exact(
    test,
    '''        else:\n            implementation = engine._IMPLEMENTATIONS[route.policy_id]\n            for trigger in implementation.trigger_features:\n                base[trigger] = 0.0\n    base.loc[0, "sma_cross_50_200_up"] = 1.0\n''',
    '''        else:\n            implementation = engine._IMPLEMENTATIONS[route.policy_id]\n            for trigger in implementation.trigger_features:\n                base[trigger] = 0.0\n    base["history_sessions"] = 300.0\n    for route in engine._DAILY_ROUTES:\n        if route.evaluator_contract_id != "accepted_reference_daily_v1":\n            continue\n        spec = engine.REFERENCE_STRATEGY_CATALOG.get(route.policy_id)\n        for required in spec.signal.required_features:\n            if required not in base.columns:\n                base[required] = 1.0\n    base.loc[0, "sma_cross_50_200_up"] = 1.0\n''',
    "reference-mask test readiness",
)
test_path.write_text(test, encoding="utf-8")
