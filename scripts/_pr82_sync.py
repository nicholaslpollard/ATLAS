from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"anchor not found in {path}: {old[:120]!r}")
    if text.count(old) != 1:
        raise RuntimeError(f"anchor is not unique in {path}: {old[:120]!r}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_section(path: str, start: str, end: str, replacement: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    start_index = text.find(start)
    if start_index < 0:
        raise RuntimeError(f"section start not found in {path}: {start!r}")
    end_index = text.find(end, start_index + len(start))
    if end_index < 0:
        raise RuntimeError(f"section end not found in {path}: {end!r}")
    file_path.write_text(text[:start_index] + replacement + text[end_index:], encoding="utf-8")


# Fix the family-roster validator: SuccessorFamilySpec owns canonical_policy_ids.
replace_once(
    "packages/strategies/successor_practitioner_rules.py",
    "    new_expected = {item.policy_id for item in NEW_FAMILIES}\n",
    "    new_expected = {\n        policy_id\n        for family in NEW_FAMILIES\n        for policy_id in family.canonical_policy_ids\n    }\n",
)

# Fix the matching test assertion and add pytest for duplicate-bar fail-closed coverage.
replace_once(
    "tests/unit/test_successor_strategy_implementation.py",
    "import pandas.testing as pdt\n",
    "import pandas.testing as pdt\nimport pytest\n",
)
replace_once(
    "tests/unit/test_successor_strategy_implementation.py",
    "    assert {item.policy_id for item in NEW_POLICY_IMPLEMENTATIONS} == {\n        item.policy_id for item in NEW_FAMILIES\n    }\n",
    "    assert {item.policy_id for item in NEW_POLICY_IMPLEMENTATIONS} == {\n        policy_id\n        for family in NEW_FAMILIES\n        for policy_id in family.canonical_policy_ids\n    }\n",
)

# Duplicate one-minute stamps are ambiguous input and must fail closed before evaluation.
replace_once(
    "packages/strategies/successor_intraday_rules.py",
    "    selected = [\n        bar\n        for bar in bars\n        if bar.timeframe == Timeframe.MINUTE_1\n        and bar.session_date == session_date\n        and _closed(bar, decision)\n        and (segment is None or bar.session_segment == segment)\n    ]\n    return sorted(selected, key=lambda item: item.timestamp_utc)\n",
    "    selected = [\n        bar\n        for bar in bars\n        if bar.timeframe == Timeframe.MINUTE_1\n        and bar.session_date == session_date\n        and _closed(bar, decision)\n        and (segment is None or bar.session_segment == segment)\n    ]\n    ordered = sorted(selected, key=lambda item: item.timestamp_utc)\n    stamps = [bar.timestamp_utc for bar in ordered]\n    if len(stamps) != len(set(stamps)):\n        raise ValueError(\"duplicate closed one-minute timestamps are not permitted\")\n    return ordered\n",
)

replace_once(
    "tests/unit/test_successor_strategy_implementation.py",
    "\ndef test_vwap_reclaim_uses_only_fully_closed_bars() -> None:\n",
    "\ndef test_duplicate_closed_minute_timestamp_fails_closed() -> None:\n    session = date(2026, 9, 10)\n    duplicated = [\n        _bar(session, 9, 30, open_=10.0, high=10.2, low=9.8, close=10.0),\n        _bar(session, 9, 30, open_=10.0, high=10.3, low=9.7, close=10.1),\n    ]\n    with pytest.raises(ValueError, match=\"duplicate closed one-minute timestamps\"):\n        evaluate_vwap_reclaim_reject(\n            duplicated,\n            session_date=session,\n            decision_time_utc=_decision(session, 9, 31),\n        )\n\n\ndef test_vwap_reclaim_uses_only_fully_closed_bars() -> None:\n",
)

# README current-state reconciliation.
replace_once(
    "README.md",
    "- A separate daily reference-feature overlay supplies the exact indicator\n  transitions needed by those policies without changing the accepted 33-feature\n  core. B34 now supplies accepted minute/session semantics and the initial\n  opening/premarket evaluators; the broader successor shared-context and eleven-new-family\n  feature/evaluator layer remains the next implementation package.\n",
    "- A separate daily reference-feature overlay supplies the exact indicator\n  transitions needed by those policies without changing the accepted 33-feature\n  core. B34 supplies accepted minute/session semantics and the initial\n  opening/premarket evaluators. The successor pre-outcome implementation now adds the\n  shared daily PIT overlay, objective confirmed-pivot/chart-pattern geometry, ADX/DMI\n  and SPY-relative-strength context, closed-minute VWAP/failed-break evaluators, and\n  exact implementations for all eleven new families plus the four bounded B35\n  challengers. No successor historical performance is opened by that implementation.\n",
)
replace_once(
    "README.md",
    "The next package implements the missing family evaluators/shared PIT features and binds them to the restart-safe parallel runtime before successor performance is opened.",
    "The family evaluators and shared PIT feature layer are now implemented under the frozen pre-outcome contract. The next package binds those exact evaluators to the restart-safe broad historical runner, freezes runner/source fingerprints, benchmarks scientifically equivalent execution shapes on the workstation, and only then opens permitted DEVELOPMENT performance.",
)

# Roadmap: close stale B35/current-gate wording and record the pre-outcome implementation.
old_sequence = "Next Track-B sequence: (1) accept the successor PRE-OUTCOME freeze containing exactly 21 economic families, four bounded B35 mechanism-level challengers, shared PIT context and separate confluence rules; (2) implement and synthetically validate the missing family evaluators and shared features without opening successor performance; (3) benchmark the restart-safe parallel runner on the actual workstation and require golden-output equivalence before tuning execution shape; (4) run the broad DEVELOPMENT/walk-forward diagnostic on permitted evidence while preserving standalone outcomes before condition gates/confluence; (5) freeze a separate untouched/prospective authority contract for any candidate that survives; and (6) never reuse the consumed master interval or silently open the future blind."
new_sequence = "Next Track-B sequence: (1) COMPLETE — the successor PRE-OUTCOME freeze contains exactly 21 economic families, four bounded B35 mechanism-level challengers, shared PIT context and separate confluence rules; (2) COMPLETE IN THIS PRE-OUTCOME IMPLEMENTATION PACKAGE — exact family/challenger rules, shared daily PIT features, closed-minute evaluators and synthetic no-lookahead tests are implemented without opening successor performance; (3) freeze the broad historical runner/source contract, bind it to the restart-safe parallel coordinator, and benchmark scientifically equivalent execution shapes on the actual workstation; (4) run the broad DEVELOPMENT/walk-forward diagnostic on permitted evidence while preserving standalone outcomes before condition gates/confluence; (5) freeze a separate untouched/prospective authority contract for any candidate that survives; and (6) never reuse the consumed master interval or silently open the future blind."
replace_once("docs/roadmap.md", old_sequence, new_sequence)
replace_once(
    "docs/roadmap.md",
    "The freeze itself opens no new successor outcomes. The next implementation package must complete deterministic family evaluators/shared PIT features and synthetic/golden-output tests before any broad successor performance run is authorized.",
    "The freeze itself opens no new successor outcomes. The deterministic family/challenger evaluator and shared PIT feature implementation is now complete at the pre-outcome layer: shared daily calculations are reused once per instrument, chart-pattern pivots are explicitly confirmation-lagged, minute evaluators consume only fully closed bars and reject duplicate minute stamps, and synthetic no-lookahead/quality-gate tests cover the new mechanisms. The next package must freeze and test the broad historical runner/source contract and benchmark exact-equivalent worker shapes before any successor performance run is authorized.",
)
replace_section(
    "docs/roadmap.md",
    "### 19A.7 Ordered successor work after B35\n",
    "## 20.",
    "### 19A.7 Ordered successor work after B35\n\n1. **COMPLETE:** B35 canonical replay, condition/selector analysis, retained-artifact robustness and exact targeted perturbations are closed with no promotion. Do not rerun or retune B35 v1.\n2. **COMPLETE:** freeze the exact 21-family successor contract, four bounded B35 same-family challengers, shared PIT context, support/cost/multiplicity rules and separate confluence semantics under new fingerprints.\n3. **COMPLETE AT PRE-OUTCOME IMPLEMENTATION LAYER:** implement shared daily PIT indicators/pivots/context, all eleven new family rules and the four challenger rules; keep the two genuinely intraday families/challengers on fully closed one-minute bars; reject ambiguous duplicate minute stamps; cover the information clock with synthetic tests. No successor historical outcomes are opened.\n4. **NEXT:** freeze the broad runner/source manifest and group partitioning, bind it to `SuccessorParallelCoordinator`, preserve standalone artifacts before conditioning/confluence, and add golden-output/restart/authority tests.\n5. Benchmark scientifically identical 4x1/6x1/8x1-style execution shapes on the actual workstation as applicable; select the fastest stable non-throttling shape without changing scientific fingerprints.\n6. Run the broad permitted DEVELOPMENT/walk-forward evidence once the runner package is accepted; evaluate standalone strategies first, then hard confirmation and confluence separately.\n7. Perform at most one bounded diagnostic/calibration cycle; any favorable B35-inspired or other post-result successor requires untouched/prospective evidence and a new authority contract before promotion.\n8. Promote nothing automatically; failures remain in the ledger, consumed master remains unavailable, and future blind remains unopened.\n\n",
)
replace_section(
    "docs/roadmap.md",
    "## 21. Immediate next action\n",
    "## 22.",
    "## 21. Immediate next action\n\n1. Merge the accepted successor pre-outcome evaluator/feature implementation after exact-head Windows and Ubuntu CI is green. This package opens no successor historical outcomes and grants no PAPER/LIVE/promotion authority.\n2. Freeze a machine-readable broad successor runner/source contract: exact source roots and date bounds, daily/intraday group partitioning, strategy-to-group routing, standalone-before-conditioning/confluence artifact order, cost/outcome semantics, authority zeros, and scientific fingerprint inputs.\n3. Implement the broad runner on `SuccessorParallelCoordinator` with atomic per-group outputs, self-hash receipts, validated restart reuse, bounded in-flight work, 60-second heartbeat/progress/ETA, and hard rejection of consumed-master/future-blind reads. Shared daily features are computed once per instrument/group and reused across policies.\n4. Run a bounded golden-output workstation benchmark across scientifically equivalent worker shapes; use the fastest stable non-throttling profile and keep execution telemetry outside the scientific fingerprint.\n5. Only after the runner contract/tests/benchmark are accepted, run the broad successor DEVELOPMENT/walk-forward diagnostic on permitted evidence. Preserve standalone family/challenger results before any condition gate or confluence analysis and report the frozen support/cost/risk/stability diagnostics.\n6. Track A Product may continue independently where evidence boundaries permit. Operational/qualifying PAPER and LIVE remain governed by separate authority gates.\n\n",
)
replace_once(
    "docs/roadmap.md",
    "B35 canonical replay, strategy x condition/selector analysis, and retained-artifact robustness are complete. The current Track-B gate is the merged PR #79 targeted minute-perturbation workstation run and final B35 research disposition. Do not rerun the canonical minute replay and do not freeze condition-gated v2 rules until the targeted perturbation evidence is reviewed. The register's\ncurrent dispositions are: Gap Continuation = condition-gate/calibrate candidate;\nOpening Range Breakout = condition-gate/calibrate plus execution audit; Premarket\nRel-Vol = cost/execution-sensitive R&D candidate; Highest-Volume-Day style =\nredefine/insufficient evidence. None is promoted.\n\nAfter the targeted perturbation evidence closes B35, freeze successor strategy versions and the broader\n21-family/context/confluence package under new fingerprints.",
    "B35 canonical replay, strategy x condition/selector analysis, retained-artifact robustness, exact targeted perturbations and final research disposition are complete. Do not rerun the canonical minute replay or reopen neighboring B35 parameter rescue. The register's current dispositions remain: Gap Continuation = condition-gate/calibrate candidate; Opening Range Breakout = condition-gate/calibrate plus execution audit; Premarket Rel-Vol = cost/execution-sensitive R&D candidate; Highest-Volume-Day style = redefine/insufficient evidence. None is promoted.\n\nThe successor 21-family/context/confluence PRE-OUTCOME package is frozen under new fingerprints, and its exact new-family/challenger evaluator plus shared PIT feature implementation is complete without opening historical successor outcomes. The current Track-B gate is the broad runner/source contract, restart-safe parallel integration and exact-equivalent workstation benchmark before the first successor DEVELOPMENT run.",
)

# Strategy Evidence Register: distinguish implemented pre-outcome mechanics from evidence.
replace_once(
    "docs/strategy_evidence_register.md",
    "The next scientific action is implementation/synthetic validation of the missing successor family evaluators and shared PIT features without opening broad successor performance. Long-run execution must use the new parallel/restart-safe runtime, benchmark exact-equivalent worker shapes on the actual host, and preserve scientific fingerprints independently from execution profile. Consumed master and future blind remain unavailable.",
    "The successor family/challenger evaluator and shared PIT feature layer is now implemented at the PRE-OUTCOME level without opening broad successor performance. It reuses the accepted daily feature stream once per instrument, adds confirmation-lagged deterministic pivots/pattern geometry, Wilder ADX/DMI14, SPY-relative-strength/market context, and fully closed-minute VWAP/failed-break/ORB/quality evaluators. Duplicate closed-minute timestamps fail closed. These are implementation facts, not performance evidence. The next scientific action is to freeze and test the broad runner/source contract, bind it to the parallel/restart-safe runtime, benchmark exact-equivalent worker shapes on the actual host, and only then open permitted DEVELOPMENT outcomes. Consumed master and future blind remain unavailable.",
)
replace_once(
    "docs/strategy_evidence_register.md",
    "The successor objective is **economically viable condition coverage**, not maximum win rate. Qualification evidence must consider win rate, payoff ratio, net expectancy/net-R, cost decay, drawdown/tail loss, sample/support, fold/year stability, concentration, MFE/MAE, holding time and abstention. No favorable post-result slice validates itself; a frozen successor still requires untouched/prospective evidence before promotion.",
    "The successor objective is **economically viable condition coverage**, not maximum win rate. Qualification evidence must consider win rate, payoff ratio, net expectancy/net-R, cost decay, drawdown/tail loss, sample/support, fold/year stability, concentration, MFE/MAE, holding time and abstention. No favorable post-result slice validates itself; a frozen successor still requires untouched/prospective evidence before promotion.\n\n### 8.7 Successor exact implementation state — PRE-OUTCOME ONLY\n\nAll eleven new-family rules and the four admitted B35 same-family challengers now have deterministic implementations tied to explicit information clocks. Daily families share one PIT computation layer rather than recomputing common indicators per strategy. Intraday rules consume only fully closed left-edge one-minute bars, require complete opening ranges where specified, preserve missing minutes as absence, and reject duplicate minute timestamps. The shared context implementation covers SPY directional/volatility state, 20/63-session ticker relative strength versus SPY, higher-timeframe ticker trend, ATR-normalized extension, overnight gap, price band, realized volatility and prior-dollar-volume liquidity; intraday participation fields remain strategy/session-derived rather than fabricated from daily data.\n\nThis section records **mechanics only**. No successor opportunity/outcome count, return, win rate, expectancy, drawdown, Sharpe, selector result, confluence result or promotion claim exists yet. The implementation package authorizes zero consumed-master/future-blind/provider/broker/PAPER/LIVE/promotion access. The next evidence-opening package must first freeze the broad runner/source/grouping contract and pass exact-equivalence/restart/authority tests plus the workstation execution benchmark.",
)

# Remove this one-time helper and its workflow from the resulting commit.
Path("scripts/_pr82_sync.py").unlink(missing_ok=True)
Path(".github/workflows/pr82-sync.yml").unlink(missing_ok=True)
