from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def patch_runner() -> None:
    path = ROOT / "packages/backtesting/successor_development_runner.py"
    text = path.read_text(encoding="utf-8")
    import_anchor = "from packages.backtesting.successor_runner_contract import (\n    canonical_sha256,\n    daily_group_token,\n    minute_symbol_groups,\n    successor_policy_routes,\n)\n"
    import_new = import_anchor + "from packages.backtesting.successor_spy_benchmark_source import (\n    SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT,\n    SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT_FINGERPRINT,\n    load_accepted_spy_benchmark_source,\n)\n"
    text = replace_once(text, import_anchor, import_new, "runner source-audit import")

    start = text.index("SPY_BENCHMARK_MAX_STALENESS_MINUTES = 5\n")
    end = text.index("SOURCE_HISTORY_POLICY = {", start)
    text = text[:start] + text[end:]

    settings_anchor = "    settings = load_settings(Path(project_root).resolve())\n    split_evidence = load_b35_split_evidence(B35DevelopmentMinuteSource(settings).layout)\n"
    settings_new = (
        "    settings = load_settings(Path(project_root).resolve())\n"
        "    spy_source = load_accepted_spy_benchmark_source(settings, preflight=preflight)\n"
        "    split_evidence = load_b35_split_evidence(B35DevelopmentMinuteSource(settings).layout)\n"
    )
    text = replace_once(text, settings_anchor, settings_new, "runner identity source audit")

    old_spy_payload = '''        "spy_benchmark": {\n            "contract": SPY_BENCHMARK_AGGREGATION_CONTRACT,\n            "fingerprint": SPY_BENCHMARK_AGGREGATION_FINGERPRINT,\n            "source": "ACCEPTED_B35_EXACT_NATIVE_MINUTE_SOURCE",\n        },\n'''
    new_spy_payload = '''        "spy_benchmark": {\n            "contract": SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT,\n            "contract_fingerprint": SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT_FINGERPRINT,\n            "source": "ACCEPTED_SPY_SOURCE_AUDIT_MINUTE_PRIMARY_PRE2026_DAILY_REPAIR",\n            "source_audit_scientific_fingerprint": spy_source.scientific_fingerprint,\n            "benchmark_sha256": spy_source.benchmark_sha256,\n        },\n'''
    text = replace_once(text, old_spy_payload, new_spy_payload, "runner identity spy payload")

    fn_start = text.index("def build_spy_benchmark_from_accepted_minute_source(\n")
    fn_end = text.index("def prepare_successor_development_inputs(\n", fn_start)
    text = text[:fn_start] + text[fn_end:]

    old_prepare = '''    minute_source = B35DevelopmentMinuteSource(settings)\n    minute_plan = minute_source.plan(DEVELOPMENT_START, DEVELOPMENT_END)\n    spy, spy_report = build_spy_benchmark_from_accepted_minute_source(\n        minute_source, minute_plan\n    )\n    benchmark_path = input_root / "benchmark_spy.parquet"\n    benchmark_sha = _write_parquet_atomic(benchmark_path, spy)\n\n    daily_adapter = ReferenceV2DailyLakeAdapter(settings)\n'''
    new_prepare = '''    spy_source = load_accepted_spy_benchmark_source(settings, preflight=identity.preflight)\n    identity_spy = identity.contract.get("spy_benchmark")\n    if not isinstance(identity_spy, dict):\n        raise SuccessorDevelopmentRunnerError("run identity has no SPY benchmark binding")\n    if (\n        identity_spy.get("source_audit_scientific_fingerprint")\n        != spy_source.scientific_fingerprint\n        or identity_spy.get("benchmark_sha256") != spy_source.benchmark_sha256\n    ):\n        raise SuccessorDevelopmentRunnerError("SPY benchmark source audit changed after run identity construction")\n    benchmark_path = spy_source.benchmark_path\n    benchmark_sha = spy_source.benchmark_sha256\n    spy_report = spy_source.scientific\n\n    minute_source = B35DevelopmentMinuteSource(settings)\n    minute_plan = minute_source.plan(DEVELOPMENT_START, DEVELOPMENT_END)\n\n    daily_adapter = ReferenceV2DailyLakeAdapter(settings)\n'''
    text = replace_once(text, old_prepare, new_prepare, "runner prepare spy source")

    text = text.replace(
        '"benchmark_contract_fingerprint": SPY_BENCHMARK_AGGREGATION_FINGERPRINT,',
        '"benchmark_contract_fingerprint": SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT_FINGERPRINT,',
    )
    text = text.replace(
        "scientific.get(\"benchmark_contract_fingerprint\") != SPY_BENCHMARK_AGGREGATION_FINGERPRINT",
        "scientific.get(\"benchmark_contract_fingerprint\") != SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT_FINGERPRINT",
    )
    if "SPY_BENCHMARK_AGGREGATION_" in text or "build_spy_benchmark_from_accepted_minute_source" in text:
        raise RuntimeError("runner still contains obsolete minute-only SPY benchmark contract")
    path.write_text(text, encoding="utf-8")


def patch_runner_tests() -> None:
    path = ROOT / "tests/test_successor_development_runner.py"
    text = path.read_text(encoding="utf-8")
    start = text.index("def test_spy_benchmark_uses_exact_final_regular_minute() -> None:\n")
    end = text.index("def test_scientific_input_fingerprint_binds_derived_hashes", start)
    text = text[:start] + text[end:]
    path.write_text(text, encoding="utf-8")


def patch_docs() -> None:
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    old = (
        "No successor benchmark performance was opened by the failed attempt. "
        "Consumed-master/future-blind/provider/broker/PAPER/LIVE/promotion authority remains zero/false."
    )
    new = (
        "No successor benchmark performance was opened by that failed attempt. A second preparation attempt then proved the gap is material rather than a one-minute edge case: SPY's last accepted minute on 2019-08-12 is 15:31 ET, 28 minutes before the scheduled final minute. The minute-only repair is therefore retired. The next gate is a separate source-only SPY audit: accepted B35 minute data remains primary; an exact same-session split-adjusted V2 daily close may repair an unusable minute session only through 2025; 2026 split-daily partitions are forbidden so the consumed May-August 2026 master cannot be opened indirectly. The audit must resolve the complete DEVELOPMENT calendar and produce a hash-bound benchmark-source receipt before the 4x1/6x1/8x1 benchmark may run. No successor benchmark performance has been opened. Consumed-master/future-blind/provider/broker/PAPER/LIVE/promotion authority remains zero/false."
    )
    text = replace_once(text, old, new, "README second SPY incident")
    readme.write_text(text, encoding="utf-8")

    roadmap = ROOT / "docs/roadmap.md"
    text = roadmap.read_text(encoding="utf-8")
    addition = '''\n\n### 20.1 Second preparation finding and source-only repair gate\n\nThe repaired <=5-minute same-session minute rule was exercised on the workstation and failed before any benchmark profile ran: `2019-08-12` has a last accepted SPY regular minute at `19:31:00Z` / 15:31 ET, **28 minutes** before the scheduled final minute. Increasing the tolerance to 30 minutes is rejected because that would redefine a stale intraday observation as a daily close.\n\nThe successor benchmark source is therefore re-gated through `run_successor_spy_source_audit.py`. The accepted B35 minute source remains primary. When a DEVELOPMENT session is missing/invalid or more than five minutes stale, the audit may use the exact same-session SPY close from the already-lineaged V2 split-adjusted daily source **only for years <= 2025**. It may not open a 2026 split-daily partition; any unresolved 2026 minute session fails the audit. The audit scans the complete DEVELOPMENT calendar in one pass, records every repair, creates a hash-bound benchmark Parquet/receipt, opens no strategy outcomes, and grants no provider/broker/PAPER/LIVE/promotion authority. The 4x1/6x1/8x1 outcome benchmark remains blocked until this source-only receipt is accepted and recorded.\n'''
    if "### 20.1 Second preparation finding and source-only repair gate" not in text:
        text += addition
    roadmap.write_text(text, encoding="utf-8")

    register = ROOT / "docs/strategy_evidence_register.md"
    text = register.read_text(encoding="utf-8")
    addition = '''\n\n### 8.1 Second SPY preparation finding — minute-only close reconstruction retired\n\nA second authorized benchmark attempt on 2026-09-13 again stopped during input preparation, before any 4x1/6x1/8x1 profile executed. The accepted minute source shows `2019-08-12` ending at `19:31:00Z` / 15:31 ET for SPY, **28 minutes stale** versus the scheduled final regular minute. No successor performance was opened.\n\nATLAS will not widen the minute tolerance to disguise this source gap. A new source-only audit is required instead. Minute data remains the primary benchmark source; only a minute session that is missing, invalid, or >5 minutes stale may be repaired from the exact same-session split-adjusted V2 daily SPY close, and daily repair is hard-limited to years <=2025. The 2026 split-daily partition is forbidden so no consumed-master rows can be touched indirectly. The audit must resolve every DEVELOPMENT XNYS session, bind exact source/file hashes into a receipt, and preserve consumed-master/future/provider/broker reads at 0 with PAPER/LIVE/promotion false. Broad successor outcomes remain unopened.\n'''
    if "### 8.1 Second SPY preparation finding" not in text:
        text += addition
    register.write_text(text, encoding="utf-8")


def main() -> None:
    patch_runner()
    patch_runner_tests()
    patch_docs()
    # Temporary patch machinery is removed in the same permanent commit.
    (ROOT / "scripts/_pr86_wire_spy_source_audit.py").unlink(missing_ok=True)
    (ROOT / ".github/workflows/pr86-wire-spy-source-audit.yml").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
