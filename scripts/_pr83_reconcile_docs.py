from __future__ import annotations

from pathlib import Path


def replace_exact(text: str, old: str, new: str, label: str, expected: int = 1) -> str:
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{label}: expected {expected} occurrence(s), found {count}")
    return text.replace(old, new)


readme_path = Path("README.md")
readme = readme_path.read_text(encoding="utf-8")
readme = replace_exact(
    readme,
    r".\\.venv\\Scripts\\python.exe",
    r".\.venv\Scripts\python.exe",
    "README PowerShell escaping",
    expected=7,
)
readme = replace_exact(
    readme,
    "The next package adds only mechanisms that materially broaden the library.",
    "The successor package adds only mechanisms that materially broaden the library.",
    "README successor-family tense",
)
readme_path.write_text(readme, encoding="utf-8")

roadmap_path = Path("docs/roadmap.md")
roadmap = roadmap_path.read_text(encoding="utf-8")
roadmap = replace_exact(
    roadmap,
    "**B35 status (2026-09-13): canonical DEVELOPMENT replay CLOSED / ACCEPTED; condition/selector, retained-artifact robustness, and exact targeted minute perturbations COMPLETE / NO PROMOTION. Successor practitioner laboratory PRE-OUTCOME freeze is the active Track-B package.**",
    "**B35 status (2026-09-13): canonical DEVELOPMENT replay CLOSED / ACCEPTED; condition/selector, retained-artifact robustness, and exact targeted minute perturbations COMPLETE / NO PROMOTION. Successor PRE-OUTCOME freeze plus rule/feature implementation are complete; PR #83 source/runner contract + hash-only source verification is the active Track-B gate.**",
    "roadmap B35 active gate",
)
roadmap = replace_exact(
    roadmap,
    "Next Track-B sequence: (1) COMPLETE — the successor PRE-OUTCOME freeze contains exactly 21 economic families, four bounded B35 mechanism-level challengers, shared PIT context and separate confluence rules; (2) COMPLETE IN THIS PRE-OUTCOME IMPLEMENTATION PACKAGE — exact family/challenger rules, shared daily PIT features, closed-minute evaluators and synthetic no-lookahead tests are implemented without opening successor performance; (3) freeze the broad historical runner/source contract, bind it to the restart-safe parallel coordinator, and benchmark scientifically equivalent execution shapes on the actual workstation; (4) run the broad DEVELOPMENT/walk-forward diagnostic on permitted evidence while preserving standalone outcomes before condition gates/confluence; (5) freeze a separate untouched/prospective authority contract for any candidate that survives; and (6) never reuse the consumed master interval or silently open the future blind. Full mechanics and methodology anchors remain in `docs/b35_a36_preoutcome_conditional_evidence.md`.",
    "Next Track-B sequence: (1) COMPLETE — the successor PRE-OUTCOME freeze contains exactly 21 economic families, four bounded B35 mechanism-level challengers, shared PIT context and separate confluence rules; (2) COMPLETE — PR #82 merged exact family/challenger rules, shared daily PIT features, closed-minute evaluators and synthetic no-lookahead tests without opening successor performance; (3) CURRENT PR #83 — freeze the portable v2 source/runner contract, all 28 concrete routes, profile-independent grouping, preregistered outcome/artifact semantics, and restart-safe hash-only source verification using project-relative locators plus SHA-256; (4) after PR #83 acceptance, run the workstation hash-only preflight to bind the actual V2 source fingerprints without opening bars, signals, returns, or outcomes; (5) implement the separate outcome-opening broad evaluator/output runner on `SuccessorParallelCoordinator`, preserving standalone artifacts before conditioning/confluence and hard-rejecting consumed-master/future-blind access; (6) complete golden-output, restart, authority, and exact-equivalent workstation execution-shape acceptance; (7) only then run the broad DEVELOPMENT diagnostic on permitted evidence; (8) freeze a separate untouched/prospective authority contract for any candidate that survives; and (9) never reuse the consumed master interval or silently open the future blind. Full mechanics and methodology anchors remain in `docs/b35_a36_preoutcome_conditional_evidence.md`.",
    "roadmap Track-B sequence",
)
roadmap = replace_exact(
    roadmap,
    "The next package must freeze and test the broad historical runner/source contract and benchmark exact-equivalent worker shapes before any successor performance run is authorized.",
    "PR #83 is the current PRE-OUTCOME source/runner gate. It freezes `atlas-successor-development-runner-contract-v2-project-relative-source-binding-preoutcome-no-authority`, binds all 28 concrete policy routes to accepted V2 DEVELOPMENT source identities, freezes profile-independent grouping plus the `0/10/25/50/100` bps outcome/artifact contract, and adds restart-safe hash-only source verification using project-relative locators plus SHA-256. The preflight opens zero bar rows, signals, returns, or historical outcomes and grants no protected/future/provider/broker/PAPER/LIVE/promotion authority. After acceptance, the workstation hash-only preflight must bind the actual V2 source fingerprints; the separate outcome-opening broad runner, golden/restart/authority acceptance, and exact-equivalent workstation benchmark remain mandatory before any successor performance is opened.",
    "roadmap 19A current gate",
)
roadmap = replace_exact(
    roadmap,
    "**Status: PLANNED SUCCESSOR WORK; B35 DEVELOPMENT REPLAY, CONDITION/SELECTOR, AND RETAINED-ARTIFACT ROBUSTNESS COMPLETE; PR #79 MERGED; EXACT TARGETED PERTURBATION WORKSTATION RUN PENDING.**",
    "**Status: SUCCESSOR PRE-OUTCOME FREEZE + RULE/FEATURE IMPLEMENTATION COMPLETE; PR #83 SOURCE/RUNNER CONTRACT + HASH-ONLY SOURCE VERIFICATION IS CURRENT; NO SUCCESSOR OUTCOMES OPENED.**",
    "roadmap 19A status",
)
old_ordered = """4. **NEXT:** freeze the broad runner/source manifest and group partitioning, bind it to `SuccessorParallelCoordinator`, preserve standalone artifacts before conditioning/confluence, and add golden-output/restart/authority tests.
5. Benchmark scientifically identical 4x1/6x1/8x1-style execution shapes on the actual workstation as applicable; select the fastest stable non-throttling shape without changing scientific fingerprints.
6. Run the broad permitted DEVELOPMENT/walk-forward evidence once the runner package is accepted; evaluate standalone strategies first, then hard confirmation and confluence separately.
7. Perform at most one bounded diagnostic/calibration cycle; any favorable B35-inspired or other post-result successor requires untouched/prospective evidence and a new authority contract before promotion.
8. Promote nothing automatically; failures remain in the ledger, consumed master remains unavailable, and future blind remains unopened."""
new_ordered = """4. **CURRENT PR #83:** freeze and test the portable v2 source/runner contract, exact accepted source identities, 28 policy routes, profile-independent daily/minute grouping, standalone-before-conditioning/confluence artifact order, preregistered outcome semantics, authority zeros, and restart-safe project-relative hash-only source verification. No bar rows or outcomes are opened.
5. **AFTER PR #83 ACCEPTANCE:** run `.\\.venv\\Scripts\\python.exe scripts\\run_successor_development_preflight.py --authorize-source-verification` on the workstation to bind the actual V2 daily/minute source fingerprints. This is still source hashing only.
6. Implement the separate outcome-opening broad evaluator/output runner on `SuccessorParallelCoordinator` with atomic per-group artifacts, self-hash receipts, validated restart reuse, bounded in-flight work, heartbeat/progress/ETA, and hard consumed-master/future-blind rejection.
7. Add golden-output/restart/authority acceptance and benchmark scientifically identical 4x1/6x1/8x1-style execution shapes on the actual workstation as applicable; select the fastest stable non-throttling profile without changing scientific fingerprints.
8. Only after those gates pass, run the broad permitted DEVELOPMENT evidence once; evaluate standalone strategies first, then hard confirmation and confluence separately.
9. Perform at most one bounded diagnostic/calibration cycle; any favorable B35-inspired or other post-result successor requires untouched/prospective evidence and a new authority contract before promotion. Promote nothing automatically; failures remain in the ledger, consumed master remains unavailable, and future blind remains unopened."""
roadmap = replace_exact(roadmap, old_ordered, new_ordered, "roadmap 19A ordered work")
old_immediate = """1. Merge the accepted successor pre-outcome evaluator/feature implementation after exact-head Windows and Ubuntu CI is green. This package opens no successor historical outcomes and grants no PAPER/LIVE/promotion authority.
2. Freeze a machine-readable broad successor runner/source contract: exact source roots and date bounds, daily/intraday group partitioning, strategy-to-group routing, standalone-before-conditioning/confluence artifact order, cost/outcome semantics, authority zeros, and scientific fingerprint inputs.
3. Implement the broad runner on `SuccessorParallelCoordinator` with atomic per-group outputs, self-hash receipts, validated restart reuse, bounded in-flight work, 60-second heartbeat/progress/ETA, and hard rejection of consumed-master/future-blind reads. Shared daily features are computed once per instrument/group and reused across policies.
4. Run a bounded golden-output workstation benchmark across scientifically equivalent worker shapes; use the fastest stable non-throttling profile and keep execution telemetry outside the scientific fingerprint.
5. Only after the runner contract/tests/benchmark are accepted, run the broad successor DEVELOPMENT/walk-forward diagnostic on permitted evidence. Preserve standalone family/challenger results before any condition gate or confluence analysis and report the frozen support/cost/risk/stability diagnostics.
6. Track A Product may continue independently where evidence boundaries permit. Operational/qualifying PAPER and LIVE remain governed by separate authority gates."""
new_immediate = """1. Complete exact-head acceptance and merge PR #83 after README, roadmap, and Strategy Evidence Register reconciliation and all Windows/Ubuntu workflow groups are green. PR #83 freezes the portable v2 source/runner contract and hash-only source-verification gate only; it opens no successor historical outcomes and grants no PAPER/LIVE/promotion authority.
2. On accepted `main`, run `.\\.venv\\Scripts\\python.exe scripts\\run_successor_development_preflight.py --authorize-source-verification` on the workstation. Inspect the source/receipt summary and bind the actual accepted V2 daily/minute fingerprints; this command hashes sources only and opens no bars, signals, returns, protected/future evidence, provider/broker access, or outcomes.
3. Implement the separate outcome-opening broad evaluator/output runner on the already frozen v2 route/group/outcome contract using `SuccessorParallelCoordinator`, atomic per-group outputs, self-hash receipts, validated restart reuse, bounded in-flight work, 60-second heartbeat/progress/ETA, shared daily feature reuse, and hard consumed-master/future-blind rejection.
4. Add golden-output, restart, authority, and artifact-order acceptance; then benchmark scientifically equivalent worker shapes on the actual workstation and keep runtime telemetry outside scientific identity.
5. Only after the runner and benchmark gates are accepted, authorize and run the broad successor DEVELOPMENT diagnostic on permitted evidence. Preserve standalone family/challenger results before any condition gate or confluence analysis and report the frozen support/cost/risk/stability diagnostics.
6. Track A Product may continue independently where evidence boundaries permit. Operational/qualifying PAPER and LIVE remain governed by separate authority gates."""
roadmap = replace_exact(roadmap, old_immediate, new_immediate, "roadmap immediate next action")
roadmap = replace_exact(
    roadmap,
    "The current Track-B gate is the broad runner/source contract, restart-safe parallel integration and exact-equivalent workstation benchmark before the first successor DEVELOPMENT run.",
    "The current Track-B gate is PR #83: the portable v2 source/runner contract and restart-safe hash-only source-verification preflight. After its exact-head acceptance and workstation source binding, the separate outcome-opening broad runner, golden/restart/authority acceptance, and exact-equivalent workstation benchmark remain mandatory before the first successor DEVELOPMENT run.",
    "roadmap evidence-register handoff",
)
roadmap_path.write_text(roadmap, encoding="utf-8")
