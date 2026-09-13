from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one exact match, found {count}")
    return text.replace(old, new, 1)


def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    starts = text.count(start)
    ends = text.count(end)
    if starts != 1 or ends < 1:
        raise SystemExit(f"{label}: start matches={starts}, end matches={ends}")
    left = text.index(start)
    right = text.index(end, left)
    return text[:left] + replacement + text[right:]


# README: replace the stale PR83-current bullet with the accepted-preflight + PR84 boundary.
readme_path = Path("README.md")
readme = readme_path.read_text(encoding="utf-8")
readme = replace_between(
    readme,
    "- **Successor practitioner laboratory PRE-OUTCOME rules/features are merged; PR #83 is the source/runner-contract and hash-only source-verification gate.**",
    "- **B34 intraday source readiness",
    '''- **Successor source verification is ACCEPTED; PR #84 implements the separately gated DEVELOPMENT outcome runner without opening successor performance during repository acceptance.** PR #82 merged as `26ddd08952454c9b1251df15fe5bfcc8ccdad16a`, implementing the frozen **21 economic families = 10 retained + 11 new**, four bounded B35 mechanism-level challengers, shared PIT context, deterministic daily/minute evaluators, and information-clock/no-lookahead tests. PR #83 merged as `5bcc80d72d1203394525c69ba21f07193b4d6272` and froze `atlas-successor-development-runner-contract-v2-project-relative-source-binding-preoutcome-no-authority`: all **28 concrete policy routes = 18 daily + 10 minute**, accepted V2 DEVELOPMENT source identities, profile-independent grouping, standalone-before-conditioning/confluence artifact order, and the `0/10/25/50/100` bps diagnostic outcome contract. The accepted workstation hash-only preflight then completed **493/493 source groups and 59,768 minute units** under runner-contract fingerprint `d2fb4b36ce9aafa1d807c915c15e15f8b52aa2fb11f5b7db742e0d7ecfe6d81c` and source-verification run fingerprint `a5662843dcce50a15bbdc1158c020ef58437592652654e4f6a00f73cf07c86c3`, using 8 workers x 1 DuckDB thread while opening zero strategy outcomes, protected/future rows, provider calls, or broker access. PR #84 adds the separately authorized DEVELOPMENT runner: exact accepted-preflight validation, one shared daily feature pass, exact retained-reference firing masks, a common daily executable-universe decision, exact B35-native minute grouping for all ten minute routes, SPY benchmark reconstruction from the already accepted native minute source, common next-open 1/5/20-session daily diagnostics, conservative structural-stop/fixed-2R intraday diagnostics, atomic standalone artifacts, validated receipt restart/reuse, and a fixed 4x1/6x1/8x1 exact-equivalence benchmark. The accepted source begins on `2016-01-04`; no earlier history is invented, so lookback-dependent features remain unavailable until enough DEVELOPMENT history accumulates. The full 493-group run requires a second explicit CLI gate and remains prohibited until the workstation benchmark is accepted. Consumed-master/future-blind reads, provider/broker access, PAPER/LIVE authority, and promotion remain zero/false throughout this package.\n\n''',
    "README successor current-state bullet",
)
readme_path.write_text(readme, encoding="utf-8")


roadmap_path = Path("docs/roadmap.md")
roadmap = roadmap_path.read_text(encoding="utf-8")
roadmap = replace_once(
    roadmap,
    "**B35 status (2026-09-13): canonical DEVELOPMENT replay CLOSED / ACCEPTED; condition/selector, retained-artifact robustness, and exact targeted minute perturbations COMPLETE / NO PROMOTION. Successor PRE-OUTCOME freeze plus rule/feature implementation are complete; PR #83 source/runner contract + hash-only source verification is the active Track-B gate.**",
    "**B35 status (2026-09-13): canonical DEVELOPMENT replay CLOSED / ACCEPTED; condition/selector, retained-artifact robustness, and exact targeted minute perturbations COMPLETE / NO PROMOTION. Successor PRE-OUTCOME freeze, rule/feature implementation, PR #83 source/runner contract, and the workstation hash-only source verification are complete; PR #84 is the separately gated DEVELOPMENT outcome-runner acceptance package and the workstation equivalence benchmark is the next outcome-opening gate after merge.**",
    "roadmap B35 status",
)
roadmap = replace_between(
    roadmap,
    "Next Track-B sequence:",
    "Full mechanics and methodology anchors remain in `docs/b35_a36_preoutcome_conditional_evidence.md`.",
    '''Next Track-B sequence: (1) COMPLETE — the successor PRE-OUTCOME freeze contains exactly 21 economic families, four bounded B35 mechanism-level challengers, shared PIT context and separate confluence rules; (2) COMPLETE — PR #82 merged exact family/challenger rules, shared daily PIT features, closed-minute evaluators and synthetic no-lookahead tests without opening successor performance; (3) COMPLETE — PR #83 merged the portable v2 source/runner contract, all 28 concrete routes, profile-independent grouping, preregistered outcome/artifact semantics, and restart-safe hash-only source verification; (4) COMPLETE — the workstation preflight verified 493/493 groups and 59,768 minute units under runner-contract fingerprint `d2fb4b36ce9aafa1d807c915c15e15f8b52aa2fb11f5b7db742e0d7ecfe6d81c` and source-verification run fingerprint `a5662843dcce50a15bbdc1158c020ef58437592652654e4f6a00f73cf07c86c3`, with zero outcomes/protected/future/provider/broker access; (5) PR #84 implements the separate outcome-opening evaluator/output runner on `SuccessorParallelCoordinator`, preserving standalone artifacts before conditioning/confluence, binding derived inputs and receipts by hash, and hard-rejecting consumed-master/future-blind access; (6) after PR #84 exact-head acceptance/merge, run only the frozen workstation 4x1/6x1/8x1 exact-equivalence benchmark and require scientific identity across shapes plus acceptable thermal/OS headroom; (7) only after benchmark acceptance authorize the second-gated full standalone DEVELOPMENT diagnostic; (8) analyze standalone evidence before any conditioning/confluence layer; (9) freeze a separate untouched/prospective authority contract for any candidate that survives; and (10) never reuse the consumed master interval or silently open the future blind. ''',
    "roadmap track-B sequence",
)
roadmap = replace_once(
    roadmap,
    "**Status: SUCCESSOR PRE-OUTCOME FREEZE + RULE/FEATURE IMPLEMENTATION COMPLETE; PR #83 SOURCE/RUNNER CONTRACT + HASH-ONLY SOURCE VERIFICATION IS CURRENT; NO SUCCESSOR OUTCOMES OPENED.**",
    "**Status: SUCCESSOR PRE-OUTCOME FREEZE + RULE/FEATURE IMPLEMENTATION + PR #83 SOURCE VERIFICATION COMPLETE; PR #84 DEVELOPMENT OUTCOME RUNNER IMPLEMENTED FOR ACCEPTANCE; NO SUCCESSOR PERFORMANCE HAS BEEN OPENED.**",
    "roadmap 19A status",
)
roadmap = replace_between(
    roadmap,
    "The freeze itself opens no new successor outcomes.",
    "### B36 — Literature-Anchored Reference Library",
    '''The freeze itself opened no new successor outcomes. PR #83 subsequently merged the portable source/runner contract, and the workstation hash-only preflight completed 493/493 source groups and 59,768 minute units with zero historical outcomes, protected/future reads, provider calls or broker access. The accepted runner-contract fingerprint is `d2fb4b36ce9aafa1d807c915c15e15f8b52aa2fb11f5b7db742e0d7ecfe6d81c`; the accepted source-verification run fingerprint is `a5662843dcce50a15bbdc1158c020ef58437592652654e4f6a00f73cf07c86c3`.\n\nPR #84 implements the separate DEVELOPMENT outcome-opening package but repository CI does not itself open performance. The runner validates the exact accepted preflight before use; derives one hash-bound SPY session-close benchmark from the already accepted native minute acquisition universe because the later `research_daily` view intentionally contains common stocks only; computes shared daily features once per instrument; preserves exact retained-reference signal masks; applies one common executable-universe disposition across all 18 daily routes; and evaluates all 10 minute routes on the exact accepted B35 native-plan grouping. The accepted source begins on `2016-01-04`; earlier warm-up history is unavailable and is never invented. Standalone artifacts are atomically published and hash-bound to self-validating receipts before conditioning/confluence can proceed. Restart reuse fails closed on input, receipt or external-artifact drift.\n\nThe command surface separates authority deliberately: any DEVELOPMENT outcome access requires `--authorize-development-outcomes`; the full 493-group standalone run additionally requires `--authorize-full-standalone`. Before that broad gate may be used, the actual workstation must run the frozen 4x1/6x1/8x1 benchmark subset and prove exact scientific equivalence across execution shapes while retaining acceptable thermal/OS headroom. Runtime profile remains outside scientific identity. No consumed-master/future-blind/provider/broker/PAPER/LIVE/promotion authority is created.\n\n### B36 — Literature-Anchored Reference Library''',
    "roadmap 19A status body",
)
roadmap = replace_between(
    roadmap,
    "### 19A.7 Ordered successor work after B35",
    "## 20.",
    '''### 19A.7 Ordered successor work after B35\n\n1. **COMPLETE:** B35 canonical replay, condition/selector analysis, retained-artifact robustness and exact targeted perturbations are closed with no promotion. Do not rerun or retune B35 v1.\n2. **COMPLETE:** freeze the exact 21-family successor contract, four bounded B35 same-family challengers, shared PIT context, support/cost/multiplicity rules and separate confluence semantics under new fingerprints.\n3. **COMPLETE:** implement shared daily PIT indicators/pivots/context, all eleven new family rules and the four challenger rules with explicit information clocks and no successor outcome access.\n4. **COMPLETE:** PR #83 freezes the portable v2 source/runner contract, exact accepted source identities, 28 policy routes, profile-independent grouping, standalone-before-conditioning/confluence artifact order, diagnostic outcome semantics and restart-safe project-relative source hashing.\n5. **COMPLETE:** workstation hash-only preflight verifies 493/493 groups and 59,768 minute units under accepted runner/source-verification fingerprints, with zero historical outcomes or protected/future/provider/broker access.\n6. **PR #84 ACCEPTANCE PACKAGE:** implement and test the separately authorized DEVELOPMENT evaluator/output runner with exact preflight binding, shared daily feature reuse, exact retained masks, common daily universe, exact B35 minute grouping, accepted-native-minute SPY benchmark, atomic standalone artifacts, self-hash receipts, validated restart reuse, input/artifact hash binding and no conditioning/confluence before standalone completion.\n7. **NEXT WORKSTATION GATE AFTER PR #84 MERGE:** run the frozen 4x1/6x1/8x1 benchmark subset with `--authorize-development-outcomes --mode benchmark`; require exact scientific equivalence and choose the fastest stable non-throttling shape. This is permitted DEVELOPMENT evidence on a bounded benchmark subset, not the full broad diagnostic.\n8. **ONLY AFTER BENCHMARK ACCEPTANCE:** use the second explicit full-standalone gate for the complete permitted DEVELOPMENT run. Preserve standalone family/challenger outputs before condition or confluence analysis.\n9. Perform at most one bounded diagnostic/calibration cycle; any favorable DEVELOPMENT-inspired successor requires untouched/prospective evidence and a new authority contract before promotion. Promote nothing automatically; failures remain in the ledger, consumed master remains unavailable, and future blind remains unopened.\n\n## 20.''',
    "roadmap ordered successor work",
)
roadmap = replace_between(
    roadmap,
    "## 21. Immediate next action",
    "## 22.",
    '''## 21. Immediate next action\n\n1. Finish exact-head Windows/Ubuntu acceptance and merge PR #84. Repository acceptance itself opens no successor performance and grants no PAPER/LIVE/promotion authority.\n2. On accepted `main`, run only `.\\.venv\\Scripts\\python.exe scripts\\run_successor_development.py --authorize-development-outcomes --mode benchmark` on the workstation. This bounded benchmark evaluates the frozen subset under 4x1/6x1/8x1 execution shapes and must produce exact scientific equivalence before runtime selection.\n3. Inspect the benchmark result for identical run/artifact fingerprints and record the fastest shape that also preserves thermal and OS headroom. Do not use raw speed alone if throttling is observed.\n4. Only after benchmark acceptance may the second-gated full standalone DEVELOPMENT command be authorized. Preserve all standalone results before any condition gate or confluence analysis.\n5. Consumed master and future blind remain structurally prohibited. Provider/broker access remains zero, and PAPER/LIVE/promotion authority remains false.\n6. Track A Product may continue independently where evidence boundaries permit. Operational/qualifying PAPER and LIVE remain governed by separate authority gates.\n\n## 22.''',
    "roadmap immediate next action",
)
roadmap_path.write_text(roadmap, encoding="utf-8")


register_path = Path("docs/strategy_evidence_register.md")
register = register_path.read_text(encoding="utf-8")
register = replace_between(
    register,
    "PR #83 now freezes the next pre-outcome boundary:",
    "## 7. Authority",
    '''PR #83 merged the portable pre-outcome boundary as `5bcc80d72d1203394525c69ba21f07193b4d6272`: `packages/backtesting/successor_runner_contract.py` binds all 28 concrete routes to accepted V2 daily/minute DEVELOPMENT sources, freezes profile-independent grouping and the `0/10/25/50/100` bps outcome contract, and preregisters standalone-before-conditioning/confluence artifact order. `scripts/run_successor_development_preflight.py` then completed on the workstation as a hash-only, restart-safe source-verification gate on `SuccessorParallelCoordinator`: **493/493 groups, 59,768 minute units, runner-contract fingerprint `d2fb4b36ce9aafa1d807c915c15e15f8b52aa2fb11f5b7db742e0d7ecfe6d81c`, source-verification run fingerprint `a5662843dcce50a15bbdc1158c020ef58437592652654e4f6a00f73cf07c86c3`**. The accepted preflight used 8 workers x 1 DuckDB thread and opened zero strategy outcomes, consumed-master rows, future-blind rows, provider calls or broker access.\n\nPR #84 is the separate DEVELOPMENT outcome-runner package. It binds outcome access to those exact accepted preflight artifacts; implements common next-open 1/5/20-session daily diagnostics and conservative structural-stop/fixed-2R intraday diagnostics; evaluates exact retained daily signal masks plus the frozen successor rules; applies a single executable-universe disposition across all 18 daily routes; and preserves the exact B35 native-plan grouping for all 10 minute routes. Because `research_daily` intentionally excludes ETFs, SPY-relative-strength/market context is sourced from the already accepted native minute acquisition universe by requiring the exact final regular-session SPY minute for every DEVELOPMENT session. The native acquisition plan itself was frozen from active + inactive Alpaca assets plus corporate-action literals before the later common-stock research view was formed, so this does not widen the accepted source boundary.\n\nThe accepted V2 source starts on `2016-01-04`; no pre-DEVELOPMENT warm-up is available or invented. Lookback-dependent features therefore remain unavailable until sufficient in-DEVELOPMENT history exists. Derived daily group files, the SPY benchmark, native minute-unit bindings, the prepared input manifest, per-group outputs and external standalone artifacts are hash-bound; corrupt or drifted reuse fails closed. Conditioning and confluence remain forbidden until every standalone group receipt validates. Any DEVELOPMENT outcome access requires `--authorize-development-outcomes`, while the full 493-group standalone run additionally requires `--authorize-full-standalone`. The next permitted evidence gate after PR #84 merge is only the frozen 4x1/6x1/8x1 exact-equivalence workstation benchmark. No broad successor DEVELOPMENT result exists yet.\n\n## 7. Authority''',
    "register PR83/84 boundary",
)
register = replace_between(
    register,
    "### 8.7 Successor exact implementation state — PRE-OUTCOME ONLY",
    "\n## 9.",
    '''### 8.7 Successor exact implementation and source state — BROAD PERFORMANCE UNOPENED\n\nAll eleven new-family rules and the four admitted B35 same-family challengers have deterministic implementations tied to explicit information clocks. Daily families share one PIT computation layer rather than recomputing common indicators per strategy. Intraday rules consume only fully closed left-edge one-minute bars, require complete opening ranges where specified, preserve missing minutes as absence, and reject duplicate minute timestamps. Shared context covers SPY directional/volatility state, 20/63-session ticker relative strength versus SPY, higher-timeframe ticker trend, ATR-normalized extension, overnight gap, price band, realized volatility and prior-dollar-volume liquidity; intraday participation fields remain strategy/session-derived rather than fabricated from daily data.\n\nThe hash-only source gate is accepted: 493/493 groups and 59,768 minute units under runner-contract fingerprint `d2fb4b36ce9aafa1d807c915c15e15f8b52aa2fb11f5b7db742e0d7ecfe6d81c` and source-verification run fingerprint `a5662843dcce50a15bbdc1158c020ef58437592652654e4f6a00f73cf07c86c3`. It opened zero historical outcomes. PR #84 adds the separately gated outcome engine, restart-safe parallel runner, exact input/artifact binding, standalone-before-conditioning/confluence boundary and workstation benchmark harness. Repository tests may validate mechanics but do not themselves constitute strategy performance evidence.\n\nNo broad successor opportunity/outcome count, return, win rate, expectancy, drawdown, Sharpe, selector result, confluence result or promotion claim exists yet. The next accepted sequence is: exact-head PR #84 CI and merge; bounded workstation 4x1/6x1/8x1 benchmark under `--authorize-development-outcomes --mode benchmark`; exact scientific-equivalence plus thermal/OS-headroom acceptance; and only then a separately authorized full standalone DEVELOPMENT run. Consumed master and future blind remain unavailable, provider/broker/PAPER/LIVE/promotion authority remains zero/false, and no favorable DEVELOPMENT result can self-qualify a DEVELOPMENT-inspired challenger.\n\n## 9.''',
    "register 8.7 state",
)
register_path.write_text(register, encoding="utf-8")
