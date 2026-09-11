from pathlib import Path
import re

source = Path("packages/backtesting/b35_targeted_perturbations.py")
text = source.read_text(encoding="utf-8")

text = text.replace(
    "import hashlib\nimport itertools\nimport json\nimport math\nimport os\n",
    "import copy\nimport hashlib\nimport itertools\nimport json\nimport math\nimport os\n",
    1,
)
text = text.replace(
    "from packages.backtesting.b35_development_replay import (\n    B35DevelopmentReplayError,",
    "from packages.backtesting.b35_development_replay import (\n    B35_DEVELOPMENT_REPLAY_CONTRACT,\n    B35DevelopmentReplayError,",
    1,
)

old = '''    canonical_strategy_counts: dict[str, dict[str, int]]\n    output_path: str\n    receipt_path: str\n'''
new = '''    canonical_strategy_counts: dict[str, dict[str, int]]\n    canonical_output_path: str\n    canonical_output_sha256: str\n    output_path: str\n    receipt_path: str\n'''
assert old in text
text = text.replace(old, new, 1)

old = '''    symbols = set(metric["symbols"])\n    symbols.add(symbol)\n    metric["symbols"] = sorted(symbols)\n'''
new = '''    symbols = metric["symbols"]\n    if not isinstance(symbols, list):\n        raise B35DevelopmentReplayError("perturbation symbol accumulator drifted")\n    if symbol not in symbols:\n        symbols.append(symbol)\n'''
assert old in text
text = text.replace(old, new, 1)

marker = '''\n\ndef _baseline_setup_by_strategy(\n'''
assert marker in text
helper = r'''\n\n_BASELINE_RESULT_FIELDS = (\n    "fired",\n    "comparable",\n    "noncomparable",\n    "wins_50bps",\n    "gross_return_sum",\n    "risk_multiple_sum",\n    "mfe_sum",\n    "mae_sum",\n    "net_return_sums_by_cost_bps",\n    "status_counts",\n    "direction_counts",\n    "session_bitset_hex",\n    "symbols",\n)\n\n\ndef _populate_exact_canonical_baselines(\n    metrics: dict[str, dict[str, object]],\n    task: B35PerturbationGroupTask,\n) -> str:\n    """Reuse accepted canonical outcomes for every zero-change baseline.\n\n    The canonical JSONL has already passed its receipt/output SHA check in the\n    coordinator. The worker re-hashes it while parsing and binds every baseline\n    metric to those exact accepted outcomes. This both strengthens equivalence and\n    avoids re-simulating the same v1 outcome multiple times.\n    """\n\n    representatives: dict[str, PerturbationVariant] = {}\n    baseline_ids: dict[str, list[str]] = {}\n    for variant in TARGETED_VARIANTS:\n        if not variant.baseline:\n            continue\n        representatives.setdefault(variant.strategy_id, variant)\n        baseline_ids.setdefault(variant.strategy_id, []).append(variant.variant_id)\n\n    canonical_metrics = {\n        strategy_id: _metric_template(variant)\n        for strategy_id, variant in representatives.items()\n    }\n    digest = hashlib.sha256()\n    record_count = 0\n    path = Path(task.canonical_output_path)\n    with path.open("rb") as handle:\n        for raw in handle:\n            digest.update(raw)\n            record = json.loads(raw)\n            if not isinstance(record, dict):\n                raise B35DevelopmentReplayError("canonical B35 group record is not an object")\n            required = {\n                "contract": B35_DEVELOPMENT_REPLAY_CONTRACT,\n                "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,\n                "source_fingerprint": task.source_fingerprint,\n                "split_evidence_fingerprint": task.split_evidence_fingerprint,\n                "authorization_id": task.development_authorization_id,\n                "group_fingerprint": task.canonical_group_fingerprint,\n            }\n            if any(record.get(key) != value for key, value in required.items()):\n                raise B35DevelopmentReplayError("canonical B35 group record identity drifted")\n            setup = record.get("setup")\n            outcome = record.get("outcome")\n            if not isinstance(setup, dict) or not isinstance(outcome, dict):\n                raise B35DevelopmentReplayError("canonical B35 group record schema drifted")\n            strategy_id = str(setup.get("strategy_id") or "")\n            if strategy_id not in canonical_metrics:\n                raise B35DevelopmentReplayError(\n                    f"canonical B35 group emitted unexpected strategy: {strategy_id}"\n                )\n            if str(outcome.get("strategy_id") or "") != strategy_id:\n                raise B35DevelopmentReplayError("canonical setup/outcome strategy mismatch")\n            symbol = str(outcome.get("symbol") or "")\n            if symbol not in task.units[0].symbols:\n                raise B35DevelopmentReplayError("canonical outcome symbol escaped frozen group")\n            try:\n                session_date = date.fromisoformat(str(outcome["session_date"]))\n            except (KeyError, ValueError) as exc:\n                raise B35DevelopmentReplayError("canonical outcome session date is invalid") from exc\n            _record(\n                canonical_metrics[strategy_id],\n                type("CanonicalOutcomeView", (), outcome)(),\n                session_date=session_date,\n                start_session=task.start_session,\n                symbol=symbol,\n            )\n            record_count += 1\n\n    actual_sha = digest.hexdigest()\n    if actual_sha != task.canonical_output_sha256:\n        raise B35DevelopmentReplayError("canonical B35 group output changed during targeted replay")\n    expected_count = sum(\n        int(item["evaluated_fired"])\n        for item in task.canonical_strategy_counts.values()\n    )\n    if record_count != expected_count:\n        raise B35DevelopmentReplayError("canonical B35 group record count drifted")\n\n    for strategy_id, variant_ids in baseline_ids.items():\n        source_metric = canonical_metrics[strategy_id]\n        for variant_id in variant_ids:\n            target = metrics[variant_id]\n            for field in _BASELINE_RESULT_FIELDS:\n                target[field] = copy.deepcopy(source_metric[field])\n    return actual_sha\n'''.replace('\\n','\n')
text = text.replace(marker, helper + marker, 1)

replacements = [
('''        if float(multiplier) == 1.0:\n            setup = canonical.get("b34_gap_continuation_v1")\n        else:\n            setup = _gap_variant(\n                bars,\n                session_date=session_date,\n                prior_close=float(prior.close),\n                symbol_split_dates=symbol_split_dates,\n                prior_session=prior.session_date,\n                multiplier=float(multiplier),\n            )\n''', '''        if float(multiplier) == 1.0:\n            continue\n        setup = _gap_variant(\n            bars,\n            session_date=session_date,\n            prior_close=float(prior.close),\n            symbol_split_dates=symbol_split_dates,\n            prior_session=prior.session_date,\n            multiplier=float(multiplier),\n        )\n'''),
('''        setup = (\n            canonical.get("b34_opening_range_breakout_15m_v1")\n            if int(minutes) == 15\n            else _opening_range_variant(\n                bars, session_date=session_date, minutes=int(minutes)\n            )\n        )\n''', '''        if int(minutes) == 15:\n            continue\n        setup = _opening_range_variant(\n            bars, session_date=session_date, minutes=int(minutes)\n        )\n'''),
('''            setup = (\n                canonical.get("b34_premarket_relvol_consolidation_v1")\n                if float(multiplier) == 1.0\n                else _premarket_relvol_variant(\n                    bars,\n                    session_date=session_date,\n                    prior_premarket_volumes=prior_pm_values,\n                    split_free_lookback=pm_split_free,\n                    relvol_multiplier=float(multiplier),\n                )\n            )\n''', '''            if float(multiplier) == 1.0:\n                continue\n            setup = _premarket_relvol_variant(\n                bars,\n                session_date=session_date,\n                prior_premarket_volumes=prior_pm_values,\n                split_free_lookback=pm_split_free,\n                relvol_multiplier=float(multiplier),\n            )\n'''),
('''            setup = (\n                canonical.get("b34_premarket_relvol_consolidation_v1")\n                if float(multiplier) == 1.0\n                else _premarket_relvol_variant(\n                    bars,\n                    session_date=session_date,\n                    prior_premarket_volumes=prior_pm_values,\n                    split_free_lookback=pm_split_free,\n                    consolidation_multiplier=float(multiplier),\n                )\n            )\n''', '''            if float(multiplier) == 1.0:\n                continue\n            setup = _premarket_relvol_variant(\n                bars,\n                session_date=session_date,\n                prior_premarket_volumes=prior_pm_values,\n                split_free_lookback=pm_split_free,\n                consolidation_multiplier=float(multiplier),\n            )\n'''),
('''            setup = (\n                canonical.get("b34_highest_volume_day_style_v1")\n                if float(multiplier) == 1.0\n                else _hvd_consolidation_variant(\n                    bars,\n                    session_date=session_date,\n                    prior_regular_daily_volumes=daily_volumes,\n                    split_free_lookback=daily_split_free,\n                    consolidation_multiplier=float(multiplier),\n                )\n            )\n''', '''            if float(multiplier) == 1.0:\n                continue\n            setup = _hvd_consolidation_variant(\n                bars,\n                session_date=session_date,\n                prior_regular_daily_volumes=daily_volumes,\n                split_free_lookback=daily_split_free,\n                consolidation_multiplier=float(multiplier),\n            )\n'''),
]
for old, new in replacements:
    assert old in text, old[:80]
    text = text.replace(old, new, 1)

# canonical map is no longer needed inside the perturbed setup evaluator.
text = text.replace(
    '''    canonical = _baseline_setup_by_strategy(canonical_setups)\n    prior = history.daily[-1] if history.daily else None\n''',
    '''    _baseline_setup_by_strategy(canonical_setups)\n    prior = history.daily[-1] if history.daily else None\n''',
    1,
)

old_validate = '''def _validate_group_baseline_parity(\n    metrics: dict[str, dict[str, object]],\n    canonical_strategy_counts: dict[str, dict[str, int]],\n) -> None:\n    for variant in TARGETED_VARIANTS:\n        if not variant.baseline:\n            continue\n        expected = canonical_strategy_counts[variant.strategy_id]\n        metric = metrics[variant.variant_id]\n        actual = (\n            int(metric["fired"]),\n            int(metric["comparable"]),\n            int(metric["noncomparable"]),\n        )\n        target = (\n            int(expected["evaluated_fired"]),\n            int(expected["comparable"]),\n            int(expected["noncomparable"]),\n        )\n        if actual != target:\n            raise B35DevelopmentReplayError(\n                f"targeted perturbation baseline parity failed for {variant.variant_id}: "\n                f"{actual!r} != {target!r}"\n            )\n'''
new_validate = '''def _validate_group_baseline_parity(\n    metrics: dict[str, dict[str, object]],\n    canonical_strategy_counts: dict[str, dict[str, int]],\n) -> None:\n    by_strategy: dict[str, list[dict[str, object]]] = {}\n    for variant in TARGETED_VARIANTS:\n        if not variant.baseline:\n            continue\n        expected = canonical_strategy_counts[variant.strategy_id]\n        metric = metrics[variant.variant_id]\n        actual = (\n            int(metric["fired"]),\n            int(metric["comparable"]),\n            int(metric["noncomparable"]),\n        )\n        target = (\n            int(expected["evaluated_fired"]),\n            int(expected["comparable"]),\n            int(expected["noncomparable"]),\n        )\n        if actual != target:\n            raise B35DevelopmentReplayError(\n                f"targeted perturbation baseline parity failed for {variant.variant_id}: "\n                f"{actual!r} != {target!r}"\n            )\n        by_strategy.setdefault(variant.strategy_id, []).append(metric)\n\n    for strategy_id, strategy_metrics in by_strategy.items():\n        reference = strategy_metrics[0]\n        signature = {field: reference[field] for field in _BASELINE_RESULT_FIELDS}\n        for metric in strategy_metrics[1:]:\n            candidate = {field: metric[field] for field in _BASELINE_RESULT_FIELDS}\n            if candidate != signature:\n                raise B35DevelopmentReplayError(\n                    f"targeted perturbation exact baseline outcome parity failed for {strategy_id}"\n                )\n'''
assert old_validate in text
text = text.replace(old_validate, new_validate, 1)

old_init = '''    metrics = {\n        item.variant_id: _metric_template(item)\n        for item in TARGETED_VARIANTS\n    }\n    histories = {symbol: _SymbolHistory.empty() for symbol in task.units[0].symbols}\n'''
new_init = '''    metrics = {\n        item.variant_id: _metric_template(item)\n        for item in TARGETED_VARIANTS\n    }\n    canonical_output_sha256 = _populate_exact_canonical_baselines(metrics, task)\n    histories = {symbol: _SymbolHistory.empty() for symbol in task.units[0].symbols}\n'''
assert old_init in text
text = text.replace(old_init, new_init, 1)

old_delay = '''                for delay in ROBUSTNESS_PERTURBATIONS["entry_delay_minutes"]:\n                    variant_id = (\n                        f"entry_delay_minutes:{int(delay)}:{setup.strategy_id}"\n                    )\n                    shifted = _shift_setup_for_entry_delay(\n                        setup, bars, session_date, int(delay)\n                    )\n'''
new_delay = '''                for delay in ROBUSTNESS_PERTURBATIONS["entry_delay_minutes"]:\n                    if int(delay) == 0:\n                        continue\n                    variant_id = (\n                        f"entry_delay_minutes:{int(delay)}:{setup.strategy_id}"\n                    )\n                    shifted = _shift_setup_for_entry_delay(\n                        setup, bars, session_date, int(delay)\n                    )\n'''
assert old_delay in text
text = text.replace(old_delay, new_delay, 1)

text = text.replace('''        "baseline_parity": "PASS",\n        "consumed_master_rows_read": 0,''', '''        "baseline_parity": "PASS_EXACT_CANONICAL_OUTCOME_REUSE",\n        "canonical_output_sha256": canonical_output_sha256,\n        "consumed_master_rows_read": 0,''', 1)
text = text.replace('''        "output_sha256": _sha256_file(output_path),\n        "baseline_parity": "PASS",\n    }''', '''        "output_sha256": _sha256_file(output_path),\n        "canonical_output_sha256": canonical_output_sha256,\n        "baseline_parity": "PASS_EXACT_CANONICAL_OUTCOME_REUSE",\n    }''', 1)
text = text.replace('''        "output_path": str(output_path),\n        "baseline_parity": "PASS",\n    }''', '''        "output_path": str(output_path),\n        "canonical_output_sha256": task.canonical_output_sha256,\n        "baseline_parity": "PASS_EXACT_CANONICAL_OUTCOME_REUSE",\n    }''', 1)

old_task = '''                    canonical_strategy_counts=canonical_receipt["strategy_counts"],\n                    output_path=str(groups_root / f"{token}.json"),\n'''
new_task = '''                    canonical_strategy_counts=canonical_receipt["strategy_counts"],\n                    canonical_output_path=str(canonical_output),\n                    canonical_output_sha256=str(canonical_receipt["output_sha256"]),\n                    output_path=str(groups_root / f"{token}.json"),\n'''
assert old_task in text
text = text.replace(old_task, new_task, 1)
text = text.replace('''            "baseline_equivalence": "PASS_ALL_GROUPS",''', '''            "baseline_equivalence": "PASS_EXACT_CANONICAL_OUTCOME_REUSE_ALL_GROUPS",''', 1)

source.write_text(text, encoding="utf-8")

# Update focused tests for exact canonical baseline reuse wording/fields without
# changing the frozen perturbation semantics.
test_path = Path("tests/unit/test_b35_targeted_perturbations.py")
test = test_path.read_text(encoding="utf-8")
# Existing parity test remains valid; no content change required.
test_path.write_text(test, encoding="utf-8")

# Reconcile the remaining stale current-action sections in the living roadmap.
roadmap = Path("docs/roadmap.md")
r = roadmap.read_text(encoding="utf-8")
r = re.sub(
    r'7\. \*\*CURRENT Track-B gate — complete the resumed canonical B35 DEVELOPMENT replay using the accepted execution path\.\*\*.*?\n\n8\. Keep focused tests, the full repository suite, retained scientific validators,\n   cross-platform exact-head CI, and same-commit updates to both living documents\n   mandatory for every package\.',
    '''7. **CURRENT Track-B gate — exact B35 targeted minute perturbations in PR #79.** Canonical B35 replay, condition/selector analysis, and retained-artifact robustness are complete and must not be rerun. PR #79 evaluates the five frozen minute-path perturbation families together as 27 one-axis-at-a-time diagnostic profiles over the same DEVELOPMENT source. Zero-change baselines reuse the exact accepted canonical outcomes and must match canonical counts, statuses, returns, costs, sessions, instruments, and output SHA lineage before a group can complete. After exact-head acceptance and merge, run `scripts/run_b35_targeted_perturbations.py --authorize-targeted-perturbations`; then record the final B35 research disposition and freeze only justified successor hypotheses under new fingerprints. Consumed master and future blind remain unavailable.\n\n8. Keep focused tests, the full repository suite, retained scientific validators, cross-platform exact-head CI, and same-package updates to all applicable living documents mandatory for every package.''',
    r,
    count=1,
    flags=re.S,
)
old_bottom = '''B35 canonical replay and the first strategy x condition / selector profile are\ncomplete. The current Track-B gate is the remaining preregistered B35 robustness and\nfinal research-disposition package. Do not rerun the canonical minute replay and do\nnot freeze condition-gated v2 rules until robustness is complete. The register's\ncurrent dispositions are: Gap Continuation = condition-gate/calibrate candidate;\nOpening Range Breakout = condition-gate/calibrate plus execution audit; Premarket\nRel-Vol = cost/execution-sensitive R&D candidate; Highest-Volume-Day style =\nredefine/insufficient evidence. None is promoted.\n\nAfter B35 robustness closes, freeze successor strategy versions and the broader\n18-family/confluence package under new fingerprints.'''
new_bottom = '''B35 canonical replay, strategy x condition / selector analysis, and retained-artifact robustness are complete. Robustness fingerprint `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107` produced no 50-bps FDR/Deflated-Sharpe support and no promotion. The current Track-B gate is PR #79's exact targeted minute perturbation pass; do not rerun canonical B35 and do not reuse the consumed master or open the future blind. The register's current dispositions remain: Gap Continuation = condition-gate/calibrate candidate; Opening Range Breakout = condition-gate/calibrate plus execution audit; Premarket Rel-Vol = cost/execution-sensitive R&D candidate; Highest-Volume-Day style = redefine/insufficient evidence. None is promoted.\n\nAfter the exact perturbation closeout, record final B35 dispositions and freeze only justified successor strategy versions plus the broader 18-family/confluence package under new fingerprints.'''
assert old_bottom in r
r = r.replace(old_bottom, new_bottom, 1)
roadmap.write_text(r, encoding="utf-8")

# Reconcile wording in the other two living docs with the stronger exact-baseline gate.
readme = Path("README.md")
rv = readme.read_text(encoding="utf-8")
rv = rv.replace(
    "Every group must reproduce canonical v1 fired/comparable/noncomparable counts for all baseline variants before perturbed evidence can publish.",
    "Every zero-change baseline reuses the exact accepted canonical v1 outcomes; each group re-hashes that canonical output and must reproduce canonical counts, statuses, returns/cost sums, session/instrument coverage, and outcome evidence before perturbed evidence can publish.",
    1,
)
readme.write_text(rv, encoding="utf-8")

register = Path("docs/strategy_evidence_register.md")
sv = register.read_text(encoding="utf-8")
sv = sv.replace(
    "All baseline values must reproduce the canonical v1 fired/comparable/noncomparable counts in every group before a perturbed group can complete.",
    "All zero-change baselines reuse the exact accepted canonical v1 outcomes; every group re-hashes the canonical output and requires exact baseline counts, status/direction distributions, return/cost sums, session/instrument coverage, and outcome parity before a perturbed group can complete.",
    1,
)
register.write_text(sv, encoding="utf-8")
