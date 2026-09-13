from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 exact match, found {count}")
    return text.replace(old, new, 1)


def replace_before(text: str, start: str, end: str, replacement: str, label: str) -> str:
    if text.count(start) != 1:
        raise SystemExit(f"{label}: start count={text.count(start)}")
    left = text.index(start)
    right = text.index(end, left)
    return text[:left] + replacement + text[right:]


README = Path("README.md")
text = README.read_text(encoding="utf-8")
text = replace_before(
    text,
    "- **Successor practitioner laboratory PRE-OUTCOME rules/features are merged; PR #83 is the source/runner-contract and hash-only source-verification gate.**",
    "- **B34 intraday source readiness",
    """- **Successor source verification is ACCEPTED; PR #84 implements the separately gated DEVELOPMENT outcome runner without opening broad successor performance during repository acceptance.** PR #82 merged as `26ddd08952454c9b1251df15fe5bfcc8ccdad16a`, implementing the frozen **21 economic families = 10 retained + 11 new**, four bounded B35 mechanism-level challengers, shared PIT context, and deterministic no-lookahead evaluators. PR #83 merged as `5bcc80d72d1203394525c69ba21f07193b4d6272` and froze all **28 concrete routes = 18 daily + 10 minute**, accepted V2 DEVELOPMENT source identities, profile-independent grouping, standalone-before-conditioning/confluence artifact order, and the `0/10/25/50/100` bps diagnostic contract. The workstation hash-only preflight then completed **493/493 groups and 59,768 minute units** under runner-contract fingerprint `d2fb4b36ce9aafa1d807c915c15e15f8b52aa2fb11f5b7db742e0d7ecfe6d81c` and source-verification fingerprint `a5662843dcce50a15bbdc1158c020ef58437592652654e4f6a00f73cf07c86c3`, using 8 workers x 1 DuckDB thread while opening zero strategy outcomes, protected/future rows, provider calls, or broker access. PR #84 adds exact accepted-preflight validation, one shared daily feature pass, exact retained-reference signal masks, a common daily executable-universe disposition, exact B35-native grouping for all ten minute routes, SPY benchmark reconstruction from the already accepted native minute source, next-open 1/5/20-session daily diagnostics, conservative structural-stop/fixed-2R intraday diagnostics, atomic standalone artifacts, hash-validated restart/reuse, and a fixed 4x1/6x1/8x1 exact-equivalence benchmark. The accepted source begins on `2016-01-04`; earlier history is never invented. The full 493-group run requires a second explicit CLI gate and remains prohibited until the workstation benchmark is accepted. Consumed-master/future-blind/provider/broker/PAPER/LIVE/promotion authority remains zero/false.\n\n""",
    "README successor state",
)
README.write_text(text, encoding="utf-8")

ROADMAP = Path("docs/roadmap.md")
text = ROADMAP.read_text(encoding="utf-8")
text = replace_once(
    text,
    "**B35 status (2026-09-13): canonical DEVELOPMENT replay CLOSED / ACCEPTED; condition/selector, retained-artifact robustness, and exact targeted minute perturbations COMPLETE / NO PROMOTION. Successor PRE-OUTCOME freeze plus rule/feature implementation are complete; PR #83 source/runner contract + hash-only source verification is the active Track-B gate.**",
    "**B35 status (2026-09-13): canonical DEVELOPMENT replay CLOSED / ACCEPTED; condition/selector, retained-artifact robustness, and exact targeted minute perturbations COMPLETE / NO PROMOTION. Successor PRE-OUTCOME freeze, rule/feature implementation, PR #83 source/runner contract, and the workstation hash-only source verification are complete; PR #84 is the separately gated DEVELOPMENT outcome-runner acceptance package, with the workstation equivalence benchmark next after merge.**",
    "roadmap B35 status",
)
text = replace_before(
    text,
    "Next Track-B sequence:",
    "Full mechanics and methodology anchors remain in `docs/b35_a36_preoutcome_conditional_evidence.md`.",
    """Next Track-B sequence: (1) COMPLETE — freeze 21 economic families, four bounded B35 same-family challengers, shared PIT context and confluence rules; (2) COMPLETE — PR #82 merged exact rules/features without performance; (3) COMPLETE — PR #83 merged the portable source/runner contract and 28 routes; (4) COMPLETE — workstation preflight verified 493/493 groups and 59,768 minute units under runner fingerprint `d2fb4b36ce9aafa1d807c915c15e15f8b52aa2fb11f5b7db742e0d7ecfe6d81c` and source-verification fingerprint `a5662843dcce50a15bbdc1158c020ef58437592652654e4f6a00f73cf07c86c3`, with zero outcomes/protected/future/provider/broker access; (5) PR #84 implements the separate outcome-opening evaluator/output runner on `SuccessorParallelCoordinator`, preserving standalone artifacts before conditioning/confluence and hard-rejecting consumed-master/future-blind access; (6) after exact-head PR #84 acceptance/merge, run only the frozen 4x1/6x1/8x1 workstation exact-equivalence benchmark and require identical science plus acceptable thermal/OS headroom; (7) only after benchmark acceptance authorize the second-gated full standalone DEVELOPMENT diagnostic; (8) analyze standalone evidence before condition/confluence; (9) any survivor still requires untouched/prospective authority evidence; and (10) never reuse the consumed master or silently open the future blind. """,
    "roadmap Track-B sequence",
)
text = replace_before(
    text,
    "The freeze itself opens no new successor outcomes.",
    "### B36 — Literature-Anchored Reference Library",
    """The freeze itself opened no successor outcomes. PR #83 subsequently merged the portable source/runner contract, and the workstation hash-only preflight completed 493/493 groups and 59,768 minute units with zero outcomes, protected/future reads, provider calls, or broker access. The accepted runner-contract fingerprint is `d2fb4b36ce9aafa1d807c915c15e15f8b52aa2fb11f5b7db742e0d7ecfe6d81c`; the accepted source-verification fingerprint is `a5662843dcce50a15bbdc1158c020ef58437592652654e4f6a00f73cf07c86c3`.\n\nPR #84 implements the separate DEVELOPMENT outcome-opening package, while repository CI itself opens no performance. The runner validates the exact accepted preflight; reconstructs a hash-bound SPY session-close benchmark from the already accepted native minute acquisition source because `research_daily` intentionally contains common stocks only; computes shared daily features once per instrument; preserves exact retained-reference signal masks; applies one common executable-universe disposition across all 18 daily routes; and evaluates all 10 minute routes on the accepted B35 native-plan grouping. The accepted source starts on `2016-01-04`; no earlier warm-up history is invented. Atomic standalone artifacts and receipts are hash-bound, and drift/corruption fails closed before reuse.\n\nAny DEVELOPMENT outcome access requires `--authorize-development-outcomes`; the full 493-group standalone run additionally requires `--authorize-full-standalone`. Before that broad gate may be used, the workstation must run the frozen 4x1/6x1/8x1 benchmark subset and prove exact scientific equivalence while preserving thermal/OS headroom. Runtime profile stays outside scientific identity. No consumed-master/future-blind/provider/broker/PAPER/LIVE/promotion authority is created.\n\n""",
    "roadmap successor status body",
)
text = replace_before(
    text,
    "### 19A.7 Ordered successor work after B35",
    "## 20. Phase/package cadence and progress reporting",
    """### 19A.7 Ordered successor work after B35\n\n1. **COMPLETE:** B35 replay/selector/robustness/targeted perturbations are closed with no promotion.\n2. **COMPLETE:** freeze the 21-family successor contract, four same-family challengers, shared PIT context and confluence semantics.\n3. **COMPLETE:** implement shared daily PIT features plus all new/challenger rules with explicit information clocks.\n4. **COMPLETE:** PR #83 freezes the portable source/runner contract, 28 routes, profile-independent grouping, outcome semantics and restart-safe source hashing.\n5. **COMPLETE:** workstation hash-only preflight verifies 493/493 groups and 59,768 minute units with zero outcome/protected/future/provider/broker access.\n6. **PR #84 ACCEPTANCE PACKAGE:** separately authorized DEVELOPMENT evaluator/output runner with exact preflight binding, shared daily feature reuse, exact retained masks, common daily universe, accepted B35 minute grouping, accepted-native-minute SPY benchmark, atomic standalone artifacts, self-hash receipts, validated restart reuse, input/artifact binding, and no conditioning/confluence before standalone completion.\n7. **NEXT WORKSTATION GATE AFTER PR #84 MERGE:** run the frozen 4x1/6x1/8x1 benchmark subset with `--authorize-development-outcomes --mode benchmark`; require exact scientific equivalence and choose the fastest stable non-throttling shape.\n8. **ONLY AFTER BENCHMARK ACCEPTANCE:** authorize the second-gated complete standalone DEVELOPMENT run; preserve standalone family/challenger outputs before condition/confluence analysis.\n9. Any favorable DEVELOPMENT-inspired successor requires untouched/prospective evidence under a new authority contract before promotion. Consumed master stays unavailable and future blind stays unopened.\n\n""",
    "roadmap ordered successor work",
)
text = replace_before(
    text,
    "## 21. Immediate next action",
    "## 22. Retained exact historical validator statements",
    """## 21. Immediate next action\n\n1. Finish exact-head Windows/Ubuntu acceptance and merge PR #84. Repository acceptance opens no successor performance and grants no PAPER/LIVE/promotion authority.\n2. On accepted `main`, run only `.\\.venv\\Scripts\\python.exe scripts\\run_successor_development.py --authorize-development-outcomes --mode benchmark` on the workstation. This bounded benchmark evaluates the frozen subset under 4x1/6x1/8x1 shapes and must prove exact scientific equivalence before runtime selection.\n3. Record the fastest shape that also preserves thermal and OS headroom; raw speed does not override throttling.\n4. Only after benchmark acceptance may the second-gated full standalone DEVELOPMENT command be authorized. Preserve all standalone results before condition/confluence analysis.\n5. Consumed master and future blind remain prohibited; provider/broker access remains zero; PAPER/LIVE/promotion remains false.\n6. Track A may continue independently under its separate authority gates.\n\n""",
    "roadmap immediate action",
)
old_tail = """The successor 21-family/context/confluence PRE-OUTCOME package is frozen under new fingerprints, and its exact new-family/challenger evaluator plus shared PIT feature implementation is complete without opening historical successor outcomes. The current Track-B gate is PR #83: the portable v2 source/runner contract and restart-safe hash-only source-verification preflight. After its exact-head acceptance and workstation source binding, the separate outcome-opening broad runner, golden/restart/authority acceptance, and exact-equivalent workstation benchmark remain mandatory before the first successor DEVELOPMENT run. The long-term router should\nactivate/deactivate strategy specialties using trailing point-in-time evidence and\nabstain when no specialty clears support, cost, robustness, risk, and authority\ngates. Continuous market coverage is desirable; forced continuous trading is not."""
new_tail = """The successor 21-family/context/confluence package, exact rules/features, PR #83 portable source/runner contract, and hash-only workstation source binding are complete. PR #84 is the current Track-B implementation/acceptance gate for the separately authorized DEVELOPMENT outcome runner. After merge, the next permitted evidence action is only the frozen 4x1/6x1/8x1 workstation benchmark; the complete 493-group standalone run remains second-gated until benchmark equivalence and thermal/OS-headroom acceptance. The long-term router should\nactivate/deactivate strategy specialties using trailing point-in-time evidence and\nabstain when no specialty clears support, cost, robustness, risk, and authority\ngates. Continuous market coverage is desirable; forced continuous trading is not."""
text = replace_once(text, old_tail, new_tail, "roadmap evidence-register handoff")
ROADMAP.write_text(text, encoding="utf-8")

REGISTER = Path("docs/strategy_evidence_register.md")
text = REGISTER.read_text(encoding="utf-8")
text = replace_before(
    text,
    "PR #83 now freezes the next pre-outcome boundary:",
    "## 7. Authority",
    """PR #83 merged the portable pre-outcome boundary as `5bcc80d72d1203394525c69ba21f07193b4d6272`: all 28 routes are bound to accepted V2 DEVELOPMENT daily/minute sources, profile-independent grouping and the `0/10/25/50/100` bps diagnostic contract are frozen, and standalone-before-conditioning/confluence artifact order is preregistered. The workstation hash-only preflight then completed **493/493 groups and 59,768 minute units** under runner-contract fingerprint `d2fb4b36ce9aafa1d807c915c15e15f8b52aa2fb11f5b7db742e0d7ecfe6d81c` and source-verification fingerprint `a5662843dcce50a15bbdc1158c020ef58437592652654e4f6a00f73cf07c86c3`. It used 8 workers x 1 DuckDB thread and opened zero strategy outcomes, consumed-master rows, future-blind rows, provider calls, or broker access.\n\nPR #84 is the separate DEVELOPMENT outcome-runner package. It binds outcome access to those exact accepted preflight artifacts; implements next-open 1/5/20-session daily diagnostics and conservative structural-stop/fixed-2R intraday diagnostics; evaluates exact retained daily signal masks plus frozen successor rules; applies a single executable-universe disposition across all 18 daily routes; and preserves the accepted B35 native-plan grouping for all 10 minute routes. Because `research_daily` intentionally excludes ETFs, SPY relative-strength/market context is reconstructed from the already accepted native minute acquisition universe by requiring the exact final regular SPY minute for every DEVELOPMENT session; the native acquisition universe was frozen before the later common-stock research projection, so this does not widen source authority.\n\nThe accepted source starts on `2016-01-04`; no earlier warm-up is available or invented. Derived daily groups, SPY benchmark, minute-unit bindings, prepared input manifest, per-group outputs and external standalone artifacts are hash-bound; drift/corruption fails closed. Conditioning/confluence is forbidden until all standalone receipts validate. Any DEVELOPMENT outcome access requires `--authorize-development-outcomes`; the full 493-group run additionally requires `--authorize-full-standalone`. After PR #84 merge, only the fixed 4x1/6x1/8x1 benchmark subset is permitted next. No broad successor DEVELOPMENT result exists yet.\n\n""",
    "register PR83/84 handoff",
)
start = "### 8.7 Successor exact implementation state — PRE-OUTCOME ONLY"
if text.count(start) != 1:
    raise SystemExit(f"register 8.7 start count={text.count(start)}")
left = text.index(start)
text = text[:left] + """### 8.7 Successor exact implementation and source state — BROAD PERFORMANCE UNOPENED\n\nAll eleven new-family rules and the four admitted B35 same-family challengers have deterministic implementations tied to explicit information clocks. Daily families share one PIT computation layer. Intraday rules consume only fully closed left-edge one-minute bars, require complete opening ranges where specified, preserve missing minutes as absence, and reject duplicate timestamps. Shared context covers SPY direction/volatility, 20/63-session ticker relative strength, higher-timeframe trend, ATR-normalized extension, overnight gap, price band, realized volatility and prior-dollar-volume liquidity; intraday participation remains session-derived rather than fabricated.\n\nThe source-only gate is accepted: **493/493 groups and 59,768 minute units**, runner-contract fingerprint `d2fb4b36ce9aafa1d807c915c15e15f8b52aa2fb11f5b7db742e0d7ecfe6d81c`, source-verification fingerprint `a5662843dcce50a15bbdc1158c020ef58437592652654e4f6a00f73cf07c86c3`. It opened zero historical outcomes. PR #84 adds the separately gated outcome engine, restart-safe parallel runner, exact input/artifact binding, standalone-before-conditioning/confluence boundary and workstation benchmark harness. Repository tests validate mechanics but are not performance evidence.\n\nNo broad successor opportunity count, return, win rate, expectancy, drawdown, Sharpe, selector result, confluence result or promotion claim exists yet. The accepted sequence is: exact-head PR #84 CI and merge; bounded workstation 4x1/6x1/8x1 benchmark under `--authorize-development-outcomes --mode benchmark`; exact scientific equivalence plus thermal/OS-headroom acceptance; and only then a separately authorized full standalone DEVELOPMENT run. Consumed master and future blind remain unavailable, provider/broker/PAPER/LIVE/promotion authority remains zero/false, and no favorable DEVELOPMENT result can self-qualify a DEVELOPMENT-inspired challenger.\n"""
REGISTER.write_text(text, encoding="utf-8")
