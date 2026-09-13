from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_between(text: str, start: str, end: str, replacement: str) -> str:
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    return text[:start_index] + replacement + text[end_index:]


def update_readme() -> None:
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("**Current as of 2026-09-11 (UTC).", "**Current as of 2026-09-13 (UTC).", 1)
    start = "- **B35 exact targeted minute perturbations are MERGED / WORKSTATION RUN PENDING.**"
    end = "- **B34 intraday source readiness and the opening/premarket pack are CLOSED / ACCEPTED.**"
    replacement = """- **B35 exact targeted minute perturbations are COMPLETE / NO PROMOTION.** The frozen DEVELOPMENT-only pass completed **482/482 groups and 59,768/59,768 source units**, evaluated all **27 one-axis-at-a-time profiles**, and returned run fingerprint `dd3f6b94f9c669218512ed1eb014b33c0fd35e8ffe38484cc8967dc7a6e29f69`. Baseline equivalence is `PASS_EXACT_CANONICAL_OUTCOME_REUSE_ALL_GROUPS`; targeted fingerprint `078bdc84a18bd6e5ff401ca0a21d4feed61f7b21770a86610a42ee0fdd16374d`. Consumed-master/future-blind rows read `0/0`; provider calls `0`; broker reads/writes `0/0`; canonical replay rewrite and selector refit `false`; PAPER/LIVE/promotion authority `false/false/false`. No neighboring parameter variant rescued the four B34/B35 strategies after costs: gap delay/threshold variants remained deeply negative; ORB 14/15/16-minute and 0/1/2-minute delays were economically indistinguishable and negative; premarket rel-vol retained only a roughly 4.9-bps best gross mean that was already negative at 10 bps; HVD remained 55-59 signals and negative. B35 v1 is therefore scientifically closed; simple parameter rescue is closed as well.\n- **Successor practitioner laboratory PRE-OUTCOME freeze is implemented on the current package branch.** The machine-readable contract contains exactly **21 economic families = 10 retained + 11 new**, four bounded B35 mechanism-level challengers, shared PIT context, 504/63/63/1 walk-forward structure, 60/30/20 condition support, cost/abstention/multiplicity/confluence rules, permanent consumed-master/future-blind prohibitions, and no promotion/PAPER/LIVE authority. Long-run infrastructure is parallel-by-default, restart-safe, receipt-validated and execution-profile-independent scientifically. The B35 workstation performance experiment is retained as runtime evidence: 10x1 was faster but thermally throttled; 8x1 sustained about 1,702 units/hour without recorded thermal throttling and is the current reference for similar mixed Python/DuckDB work, not a universal hardcoded optimum.\n\n"""
    text = replace_between(text, start, end, replacement)
    text = text.replace(
        "A separate daily reference-feature overlay now supplies the exact indicator\n  transitions needed by those policies without changing the accepted 33-feature\n  core. Intraday, premarket, and opening-session features remain deferred.",
        "A separate daily reference-feature overlay supplies the exact indicator\n  transitions needed by those policies without changing the accepted 33-feature\n  core. B34 now supplies accepted minute/session semantics and the initial\n  opening/premarket evaluators; the broader successor shared-context and eleven-new-family\n  feature/evaluator layer remains the next implementation package.",
    )
    text = text.replace(
        "Native minute evidence, extended-hours semantics, and initial intraday strategy readiness are accepted by B34. **B35 DEVELOPMENT replay CLOSED / ACCEPTED (2026-09-11).**",
        "Native minute evidence, extended-hours semantics, and initial intraday strategy readiness are accepted by B34. **B35 DEVELOPMENT replay and all preregistered B35 robustness/targeted diagnostics are CLOSED / ACCEPTED-NO-PROMOTION (2026-09-13).**",
    )
    text = text.replace(
        "This closes the canonical B35 replay itself; the next Track-B work is the preregistered strategy x condition evidence and selector analysis, not another replay.",
        "The canonical replay, condition/selector analysis, retained-artifact robustness, and exact targeted perturbations are all complete. The next Track-B work is the frozen successor practitioner laboratory; B35 v1 will not be replayed or parameter-tuned again.",
    )
    old = """B35 canonical replay, condition/selector analysis, and retained-artifact robustness are complete. PR #79 is merged; the current Track-B action is the single exact targeted minute-perturbation workstation run. After its 27 diagnostic profiles are reviewed and final B35 dispositions are recorded, freeze the **21-family / eleven-new-family successor contract**, only the B35 v2 challengers justified by the completed diagnostics, the bounded shared PIT context schema, and the separate confluence/ranking schema before opening successor performance."""
    new = """B35 canonical replay, condition/selector analysis, retained-artifact robustness, and exact targeted minute perturbations are complete. The successor **21-family / eleven-new-family** PRE-OUTCOME contract is now frozen in `packages/strategies/successor_practitioner_lab.py` and `docs/successor_practitioner_lab_preoutcome.md`. Four bounded B35 mechanism-level challengers are admitted: one quality/condition long gap successor, Stocks-in-Play 5-minute ORB, 15-minute ORB close/retest, and a quality/liquidity premarket-relvol successor. HVD receives no simple width/delay challenger. The next package implements the missing family evaluators/shared PIT features and binds them to the restart-safe parallel runtime before successor performance is opened."""
    if old not in text:
        raise RuntimeError("README successor implementation-order anchor drifted")
    text = text.replace(old, new)
    text = text.replace(
        "After the accepted B35 targeted perturbation diagnostic closes, Track B proceeds to a new preregistered successor research package rather than modifying B35 v1.",
        "The accepted B35 targeted perturbation diagnostic is closed. Track B now proceeds under a new preregistered successor research package rather than modifying B35 v1.",
    )
    path.write_text(text, encoding="utf-8")


def update_roadmap() -> None:
    path = ROOT / "docs" / "roadmap.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("**Current as of 2026-09-11 (UTC).", "**Current as of 2026-09-13 (UTC).", 1)
    start = "**B35 DEVELOPMENT replay status (2026-09-11): CLOSED / ACCEPTED; condition/selector and retained-artifact robustness COMPLETE / NO PROMOTION; exact targeted perturbations CURRENT in PR #79.**"
    if start not in text:
        raise RuntimeError("roadmap B35 status anchor drifted")
    text = text.replace(
        start,
        "**B35 status (2026-09-13): canonical DEVELOPMENT replay CLOSED / ACCEPTED; condition/selector, retained-artifact robustness, and exact targeted minute perturbations COMPLETE / NO PROMOTION. Successor practitioner laboratory PRE-OUTCOME freeze is the active Track-B package.**",
        1,
    )
    old = """**B35 retained-artifact robustness is COMPLETE / NO PROMOTION; exact targeted minute perturbations are MERGED / WORKSTATION RUN PENDING.** PR #78 merged as `83d09c424a02883f7d3529a39c62294dcbaf6bc2`; workstation robustness fingerprint `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107` covers 2,079 complete XNYS test sessions. All five declared 50-bps profiles have negative mean session return and Deflated-Sharpe probability `0.0`; 13 selected-cell hypotheses produced 0 BH-FDR q=.05 rejections. The frozen selector retains positive low-cost evidence at 0/10/25 bps but is negative at 50/100 bps. PBO/CSCV ~0.01% is ranking-stability context only, not a profitability claim. PR #79 merged to `main` as `b6133d2efe8bc331a80d71bb2c0bfa47707655db`. Its DEVELOPMENT-only, restartable, hash-receipted pass contains 27 one-axis-at-a-time strategy/variant profiles. Unchanged baseline variants reuse the exact accepted canonical B35 outcomes with SHA-256 verification and exact outcome-economic parity checks; only true perturbations are recomputed. It does not refit the selector or rewrite B35 v1 and grants no promotion/PAPER/LIVE/provider/broker/master/future authority.

Next Track-B sequence: (1) run `.\\.venv\\Scripts\\python.exe scripts\\run_b35_targeted_perturbations.py --authorize-targeted-perturbations` once from current `main`; (2) review the 27 diagnostic profiles and record the final B35 research disposition without promotion or v1 rewrite; (3) freeze only justified B35 v2 challengers plus the 21-family successor/context/confluence contract under new fingerprints; (4) implement and test the successor library on permitted evidence; (5) later evaluate genuinely new prospective/future-blind evidence only under a separately frozen authority contract; and (6) never reuse the consumed master interval."""
    new = """**B35 retained-artifact robustness and exact targeted minute perturbations are COMPLETE / NO PROMOTION.** PR #78 merged as `83d09c424a02883f7d3529a39c62294dcbaf6bc2`; robustness fingerprint `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107` remains binding. PR #79 merged as `b6133d2efe8bc331a80d71bb2c0bfa47707655db`; the repaired workstation run subsequently completed 482/482 groups and 59,768/59,768 units with all 27 frozen profiles, exact canonical baseline equivalence, targeted fingerprint `078bdc84a18bd6e5ff401ca0a21d4feed61f7b21770a86610a42ee0fdd16374d`, and run fingerprint `dd3f6b94f9c669218512ed1eb014b33c0fd35e8ffe38484cc8967dc7a6e29f69`. Master/future/provider/broker reads remained zero and no authority changed. No neighboring parameter variant became economically viable: gap remained deeply negative, ORB timing/range perturbations were essentially flat and negative, premarket-relvol's best gross mean remained below 10 bps, and HVD remained sparse/negative.

Next Track-B sequence: (1) accept the successor PRE-OUTCOME freeze containing exactly 21 economic families, four bounded B35 mechanism-level challengers, shared PIT context and separate confluence rules; (2) implement and synthetically validate the missing family evaluators and shared features without opening successor performance; (3) benchmark the restart-safe parallel runner on the actual workstation and require golden-output equivalence before tuning execution shape; (4) run the broad DEVELOPMENT/walk-forward diagnostic on permitted evidence while preserving standalone outcomes before condition gates/confluence; (5) freeze a separate untouched/prospective authority contract for any candidate that survives; and (6) never reuse the consumed master interval or silently open the future blind."""
    if old not in text:
        raise RuntimeError("roadmap B35 next-sequence anchor drifted")
    text = text.replace(old, new)
    marker = "### B36 — Literature-Anchored Reference Library"
    insert = """### 19A status — Successor practitioner laboratory

**PRE-OUTCOME freeze implemented 2026-09-13.** `packages/strategies/successor_practitioner_lab.py` is the machine-readable scientific contract and `docs/successor_practitioner_lab_preoutcome.md` is its immutable human-readable specification. It freezes 10 retained + 11 new economic families, the four bounded B35 mechanism-level challengers, shared PIT context, 504/63/63/1 walk-forward design, 60/30/20 condition-support minimums, frequency-aware cost interpretation, abstention, multiplicity and confluence semantics. The consumed master and future blind remain structurally forbidden and this package has no promotion/PAPER/LIVE authority.

Runtime implementation is parallel-by-default and restart-safe. `packages/core/successor_execution_profile.py` supplies a bounded hardware-aware worker/DuckDB budget with separate successor environment overrides; `packages/backtesting/successor_parallel.py` supplies atomic group outputs, self-hash receipts, validated restart reuse, machine-readable progress, and scientific fingerprints that exclude execution profile/telemetry. The B35 targeted replay's 8x1 sustained workstation result is retained as a reference for similar workloads, but each materially different long successor workload must benchmark exact-equivalent execution shapes and choose the fastest stable non-throttling profile.

The freeze itself opens no new successor outcomes. The next implementation package must complete deterministic family evaluators/shared PIT features and synthetic/golden-output tests before any broad successor performance run is authorized.

"""
    if marker not in text:
        raise RuntimeError("roadmap B36 anchor drifted")
    text = text.replace(marker, insert + marker, 1)
    path.write_text(text, encoding="utf-8")


def update_register() -> None:
    path = ROOT / "docs" / "strategy_evidence_register.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("**Current as of 2026-09-11 (UTC).", "**Current as of 2026-09-13 (UTC).", 1)
    old = """**Final robustness component:** PR #79 merged to `main` as `b6133d2efe8bc331a80d71bb2c0bfa47707655db`; the workstation run remains pending. It implements the five frozen minute-path perturbation families in one DEVELOPMENT-only pass. There are 27 strategy/variant profiles because entry delay is applied to all four strategies and consolidation-range perturbation applies independently to premarket-relvol and HVD. Each axis changes alone. All baseline values must reproduce the canonical v1 fired/comparable/noncomparable counts in every group before a perturbed group can complete. Better variants are diagnostic successor hypotheses only; selector refit and canonical-v1 rewrite are forbidden."""
    new = """**Final robustness component: COMPLETE / NO PROMOTION.** PR #79 merged to `main` as `b6133d2efe8bc331a80d71bb2c0bfa47707655db`; the workstation run completed 482/482 groups and 59,768/59,768 source units with 27 one-axis-at-a-time profiles, targeted fingerprint `078bdc84a18bd6e5ff401ca0a21d4feed61f7b21770a86610a42ee0fdd16374d`, run fingerprint `dd3f6b94f9c669218512ed1eb014b33c0fd35e8ffe38484cc8967dc7a6e29f69`, and `PASS_EXACT_CANONICAL_OUTCOME_REUSE_ALL_GROUPS`. Consumed-master/future-blind reads, provider calls and broker reads/writes remained zero; selector refit/canonical rewrite/promotion/PAPER/LIVE remained false. No neighboring parameter variant became economically viable. This closes B35 v1 robustness and simple parameter rescue."""
    if old not in text:
        raise RuntimeError("register final robustness anchor drifted")
    text = text.replace(old, new)
    text = text.replace(
        "**Current disposition:** `CONDITION-GATE / CALIBRATE`. Preserve v1 as a negative unrestricted baseline. Candidate v2 work should prioritize economically coherent long-side/liquidity/volatility/premarket participation hypotheses and explicitly investigate the high noncomparable rate in low-liquidity names.",
        "**Current disposition:** `CONDITION-GATE / CALIBRATE`. Preserve v1 as a negative unrestricted baseline. Targeted perturbations confirm that +1/+2-minute delays and 0.9/1.0/1.1 gap-threshold multipliers improve or worsen only the degree of a still deeply negative result; none is a viable rescue. Admit one mechanism-level long-side quality/condition successor centered on preregistered liquidity, volatility, price and premarket participation, and explicitly investigate the high noncomparable rate in low-liquidity names.",
    )
    text = text.replace(
        "**Current disposition:** `CONDITION-GATE / CALIBRATE + EXECUTION AUDIT`. Candidate successor research should test signal-time, overnight-gap exhaustion, price/liquidity quality, and opening-range geometry under realistic execution assumptions. Do not hard-code the low-liquidity/unavailable-volatility cell as a permanent edge.",
        "**Current disposition:** `CONDITION-GATE / CALIBRATE + EXECUTION AUDIT`. Targeted 14/15/16-minute ranges and +0/+1/+2-minute entries are economically indistinguishable and negative, closing simple timing/range rescue. The bounded successors are Stocks-in-Play 5-minute ORB and an objective 15-minute close/retest confirmation policy. Continue to audit signal time, overnight-gap exhaustion, price/liquidity quality and opening-range geometry; do not hard-code the low-liquidity/unavailable-volatility cell as a permanent edge.",
    )
    text = text.replace(
        "**Current disposition:** `KEEP FOR R&D / COST-EXECUTION CALIBRATION`. Candidate successors may investigate liquidity, entry timing, breakout confirmation, stop/exit efficiency, and whether higher-quality participation filters can increase gross edge enough to survive conservative executable costs.",
        "**Current disposition:** `KEEP FOR R&D / COST-EXECUTION CALIBRATION`. Targeted delay, rel-vol-threshold and consolidation-width perturbations retain only a thin gross signal; the best observed gross mean is about 4.92 bps and is already negative at 10 bps, while delayed entry worsens the profile. Admit one quality/liquidity/participation successor that attempts to increase gross edge and execution quality without weakening costs or simply choosing the best observed threshold.",
    )
    text = text.replace(
        "**Current disposition:** `REDEFINE / INSUFFICIENT EVIDENCE`. Preserve v1 unchanged. A successor should reconsider the practitioner specification under a new fingerprint rather than lowering the evidence threshold after seeing only 58 signals.",
        "**Current disposition:** `REDEFINE / INSUFFICIENT EVIDENCE`. Preserve v1 unchanged. Targeted consolidation-width neighbors produced only 55/58/59 signals and remained negative; entry delays also worsened or failed to help. No simple HVD challenger is admitted this cycle. A future successor must genuinely redefine the abnormal-volume mechanism under a new fingerprint rather than lower the evidence threshold or tune width after seeing the result.",
    )
    start = "## 6. Next B35 scientific work"
    end = "## 7. Authority"
    replacement = """## 6. B35 closeout and successor handoff

**B35 is CLOSED / NO PROMOTION as of 2026-09-13.** Canonical replay, condition/selector analysis, retained-artifact robustness and the final exact targeted minute perturbations are complete. No B35 v1 replay, selector refit, nearby parameter sweep or cost weakening is justified. The four final research dispositions are recorded above and B35 v1 remains immutable historical evidence.

The successor PRE-OUTCOME contract is now implemented in `packages/strategies/successor_practitioner_lab.py` with human-readable specification `docs/successor_practitioner_lab_preoutcome.md`. It freezes exactly 21 economic families (10 retained + 11 new), four bounded B35 mechanism-level challengers, shared PIT context, walk-forward/support/cost rules, and confluence/multiplicity semantics. Because the admitted B35 challengers were inspired by DEVELOPMENT evidence, they cannot validate themselves on the same DEVELOPMENT data; untouched/prospective evidence remains mandatory before promotion.

The next scientific action is implementation/synthetic validation of the missing successor family evaluators and shared PIT features without opening broad successor performance. Long-run execution must use the new parallel/restart-safe runtime, benchmark exact-equivalent worker shapes on the actual host, and preserve scientific fingerprints independently from execution profile. Consumed master and future blind remain unavailable.

"""
    text = replace_between(text, start, end, replacement)
    text = text.replace(
        "As of this update, historical supported modern alpha remains **zero**.",
        "As of this 2026-09-13 closeout, historical supported modern alpha remains **zero**.",
        1,
    )
    text = text.replace(
        "The next major Track-B experiment targets **21 economic strategy families**: the ten retained families plus eleven distinct additions.",
        "The accepted successor PRE-OUTCOME laboratory targets **21 economic strategy families**: the ten retained families plus eleven distinct additions.",
    )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    update_readme()
    update_roadmap()
    update_register()


if __name__ == "__main__":
    main()
